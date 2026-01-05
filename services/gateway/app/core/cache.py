"""
File Overview: In memory two tier cache for protein pair similarity scores used by HelixStream services.
Responsibilities:
- Generate deterministic cache keys for accession pairs per model and track hit/miss statistics.
- Serve similarity from in-process LRU, fall back to PostgreSQL cache table, else compute via pgvector distance.
- Persist freshly computed similarities back to the database and refresh the LRU.
Data Flow:
- Inputs: repository connection, accession IDs (acc1, acc2), model_id; optional existing cache entries.
- Outputs: similarity score in [0,1] with cache-hit flag; optional DB writes on miss.
System Integration:
- Queries pgvector-backed similarity_cache and embedding tables via the shared repository connection.
- Used by SimilarityService/ComparisonService to accelerate FastAPI endpoints.
Technical Details:
- Uses pgvector cosine distance operator `<=>` against model-specific vector tables; converts to similarity and clamps range.
- FIFOstyle LRU dict
Future Considerations:
- Make cache size and TTL configurable; consider true LRU OrderedDict and background warmups.
"""

# In memory LRU cache for protein similarity scores.
import logging
from functools import lru_cache
from typing import Optional, Tuple
import hashlib

logger = logging.getLogger(__name__)


class SimilarityCache:
    # LRU cache shared across all instances
    _lru_cache = {}
    _cache_size = 1000
    _cache_hits = 0
    _cache_misses = 0
    
    @classmethod
    def _make_cache_key(cls, acc1: str, acc2: str, model_id: str) -> str:
        ordered = tuple(sorted([acc1, acc2]))
        key = f"{ordered[0]}:{ordered[1]}:{model_id}"
        return key
    
    @classmethod
    def get_similarity(
            cls, 
            repo, 
            acc1: str, 
            acc2: str, 
            model_id: str
        ) -> Tuple[float, bool]:

        # Get similarity score with two-tier caching
        protein_a, protein_b = sorted([acc1, acc2])
        cache_key = cls._make_cache_key(acc1, acc2, model_id)
        
        # Check LRU first
        if cache_key in cls._lru_cache:
            cls._cache_hits += 1
            logger.debug(f"LRU cache HIT: {cache_key} (hit rate: {cls._get_hit_rate():.1%})")
            return cls._lru_cache[cache_key], True
        
        cls._cache_misses += 1
        
        # Check database cache
        with repo.conn.cursor() as cur:
            cur.execute("""
                SELECT similarity FROM similarity_cache 
                WHERE protein_a = %s AND protein_b = %s AND model_id = %s
            """, (protein_a, protein_b, model_id))
            
            row = cur.fetchone()
            if row:
                similarity = float(row[0])
                # Populate LRU cache
                cls._add_to_lru(cache_key, similarity)
                logger.debug(f"DB cache HIT: {cache_key}")
                return similarity, True
        
        # Cache miss, compute using pgvector
        logger.info(f"Cache MISS: {cache_key} - computing similarity")
        similarity = cls._compute_similarity(repo, protein_a, protein_b, model_id)
        
        if similarity is not None:
            # Store in both caches
            cls._store_in_db(repo, protein_a, protein_b, similarity, model_id)
            cls._add_to_lru(cache_key, similarity)
            return similarity, False
        
        # Fallback if computation failed
        logger.warning(f"Similarity computation failed for {protein_a} <-> {protein_b}")
        return 0.0, False
    
    @classmethod
    def _compute_similarity(
            cls, 
            repo, 
            acc1: str, 
            acc2: str, 
            model_id: str
        ) -> Optional[float]:
        
        # Compute similarity using PostgreSQL pgvector cosine distance.
        table_name = 'vectors_esm2_650m' if '650M' in model_id else 'vectors_esm2_8m'
        try:
            with repo.conn.cursor() as cur:
                # Use pgvector's optimized cosine distance operator (<=>)
                query = f"""
                    SELECT (v1.vector <=> v2.vector) as distance
                    FROM {table_name} v1
                    JOIN embedding_metadata m1 ON v1.metadata_id = m1.id
                    JOIN {table_name} v2 ON TRUE
                    JOIN embedding_metadata m2 ON v2.metadata_id = m2.id
                    WHERE m1.primary_accession = %s 
                      AND m2.primary_accession = %s
                      AND m1.model_id = %s
                      AND m2.model_id = %s
                """
                cur.execute(query, (acc1, acc2, model_id, model_id))
                
                row = cur.fetchone()
                if row and row[0] is not None:
                    distance = float(row[0])
                    similarity = 1.0 - distance  # Convert distance to similarity
                    return max(0.0, min(1.0, similarity))  # Clamp to [0, 1]
                
                return None
                
        except Exception as e:
            logger.error(f"Similarity computation failed: {e}", exc_info=True)
            return None
    
    @classmethod
    def _store_in_db(
            cls, 
            repo, 
            protein_a: str, 
            protein_b: str, 
            similarity: float,
            model_id: str
        ) -> None:

        # Store similarity in database cache
        try:
            with repo.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO similarity_cache (protein_a, protein_b, similarity, model_id)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (protein_a, protein_b, model_id) 
                    DO UPDATE SET 
                        similarity = EXCLUDED.similarity,
                        computed_at = NOW()
                """, (protein_a, protein_b, similarity, model_id))
            repo.conn.commit()
        except Exception as e:
            logger.error(f"Failed to store similarity in DB: {e}")
    
    @classmethod
    def _add_to_lru(cls, key: str, value: float) -> None:
        if len(cls._lru_cache) >= cls._cache_size:
            oldest_key = next(iter(cls._lru_cache))
            del cls._lru_cache[oldest_key]
        
        cls._lru_cache[key] = value
    
    @classmethod
    def _get_hit_rate(cls) -> float:
        total = cls._cache_hits + cls._cache_misses
        return cls._cache_hits / total if total > 0 else 0.0
    
    @classmethod
    def clear_cache(cls) -> None:
        cls._lru_cache.clear()
        cls._cache_hits = 0
        cls._cache_misses = 0
        logger.info("Similarity cache cleared")
    
    @classmethod
    def get_stats(cls) -> dict:
        return {
            "cache_size": len(cls._lru_cache),
            "max_size": cls._cache_size,
            "hits": cls._cache_hits,
            "misses": cls._cache_misses,
            "hit_rate": cls._get_hit_rate()
        }
