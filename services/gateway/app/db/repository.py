"""
File Overview: PostgreSQL data access layer with pooling, vector storage, and similarity utilities for HelixStream.
Responsibilities:
- Provide pooled connections and context-managed repository instances.
- Upsert embedding metadata and vectors into model-specific pgvector tables; serialize JSON fields.
- Run pgvector similarity search, accession lookups with model fallback, and bulk summaries.
- Precompute and store neighbor edges plus positional/coverage checks for graph features.
Data Flow:
- Inputs: vectors, sequence hashes, metadata dicts, accession/model queries, k/limit parameters.
- Outputs: committed rows in embedding_metadata/vectors/graph tables and structured query results.
System Integration:
- Central DB layer for FastAPI services; interacts with pgvector operators, graph_positions, and graph_edges tables.
Technical Details:
- Uses psycopg2 SimpleConnectionPool (1-20), sql.Identifier for dynamic table names, and distance-to-similarity conversion for edges.
- Supports both 650M and 8M vector tables; handles JSON decoding for pdb_ids/binding_sites on read.
Future Considerations:
- Add transaction scopes for multi-step writes, pool config validation, and indexing tuned to search filters.
"""

import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
import json
import os

class DatabasePool:
    _pool = None

    @classmethod
    def get_pool(cls, db_url):
        if cls._pool is None:
            cls._pool = psycopg2.pool.SimpleConnectionPool(1, 20, db_url)
        return cls._pool

class DatabaseContext:
    def __init__(self, db_url):
        self.pool = DatabasePool.get_pool(db_url)
        self.conn = None
    def __enter__(self):
        self.conn = self.pool.getconn()
        return EmbeddingRepository(self.conn)
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.pool.putconn(self.conn)

class EmbeddingRepository:
    def __init__(self, conn):
        self.conn = conn

    def store_rich_embedding(self, seq_hash, model_id, vector_data, biological_data, confidence_score, is_fallback=False):
        vector_list = json.loads(vector_data) if isinstance(vector_data, str) else vector_data
        accession = biological_data.get('accession')
        
        with self.conn.cursor() as cur:
            # Try to insert or update based on unique (accession, model)
            query_meta = """
                INSERT INTO embedding_metadata 
                (sequence_hash, model_id, confidence_score, is_fallback, sequence_text, 
                 primary_accession, protein_name, organism, function_text, binding_sites, pdb_ids)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (primary_accession) DO UPDATE 
                SET sequence_hash = EXCLUDED.sequence_hash,
                    model_id = EXCLUDED.model_id,
                    confidence_score = EXCLUDED.confidence_score,
                    is_fallback = EXCLUDED.is_fallback,
                    protein_name = EXCLUDED.protein_name,
                    pdb_ids = EXCLUDED.pdb_ids,
                    binding_sites = EXCLUDED.binding_sites,
                    sequence_text = EXCLUDED.sequence_text,
                    organism = EXCLUDED.organism,
                    function_text = EXCLUDED.function_text
                RETURNING id;
            """
            cur.execute(query_meta, (
                seq_hash, model_id, confidence_score, is_fallback, biological_data['sequence'],
                accession, biological_data.get('name'),
                biological_data.get('organism'), biological_data.get('function'),
                json.dumps(biological_data.get('annotations', [])),
                json.dumps(biological_data.get('pdb_ids', []))
            ))
            meta_id = cur.fetchone()[0]
            
            table_name = 'vectors_esm2_8m' if '8M' in model_id else 'vectors_esm2_650m'
            query_vec = sql.SQL("INSERT INTO {} (metadata_id, vector) VALUES (%s, %s) ON CONFLICT (metadata_id) DO UPDATE SET vector = EXCLUDED.vector;").format(sql.Identifier(table_name))
            cur.execute(query_vec, (meta_id, vector_list))
            self.conn.commit()

    def find_similar(self, vector, model_id, limit=5):
        table_name = 'vectors_esm2_650m' if '650M' in model_id else 'vectors_esm2_8m'
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = sql.SQL("""
                SELECT m.primary_accession, m.protein_name, m.organism, m.is_fallback,
                       (v.vector <=> %s::vector) as distance
                FROM {} v
                JOIN embedding_metadata m ON v.metadata_id = m.id
                WHERE m.model_id = %s
                ORDER BY distance ASC LIMIT %s
            """).format(sql.Identifier(table_name))
            cur.execute(query, (vector, model_id, limit))
            return cur.fetchall()

    def get_embedding_by_accession(self, accession: str, model_id: str):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # First try exact model match, then fallback to any model
            cur.execute("""
                SELECT * FROM embedding_metadata 
                WHERE primary_accession = %s AND model_id = %s 
                LIMIT 1
            """, (accession, model_id))
            row = cur.fetchone()
            
            if not row:
                # Fallback- get any model for this accession
                cur.execute("""
                    SELECT * FROM embedding_metadata 
                    WHERE primary_accession = %s 
                    LIMIT 1
                """, (accession,))
                row = cur.fetchone()
            
            if not row: 
                return None
            
            # Fix json loading
            for key in ['pdb_ids', 'binding_sites']:
                if row.get(key) and isinstance(row[key], str):
                    row[key] = json.loads(row[key])
            return row
            
    def get_all_summaries(self, limit=1000):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    m.primary_accession, 
                    m.protein_name, 
                    m.organism, 
                    m.is_fallback, 
                    m.model_id, 
                    m.confidence_score,
                    COALESCE(v650.vector, v8.vector) as vector
                FROM embedding_metadata m
                LEFT JOIN vectors_esm2_650m v650 ON m.id = v650.metadata_id
                LEFT JOIN vectors_esm2_8m v8 ON m.id = v8.metadata_id
                WHERE v650.vector IS NOT NULL OR v8.vector IS NOT NULL
                LIMIT %s
            """, (limit,))
            return cur.fetchall()

    # --- // PERFORMANCE OPTIMIZATION METHODS    

    def precompute_neighbors_for_protein(self, accession: str, model_id: str, k: int = 10):
        # Pre compute and store KNN neighbors for a  protein. Uses Postgres HNSW index for fast similarity search
        import logging
        logger = logging.getLogger(__name__)
        
        # Get the vector for this protein
        table_name = 'vectors_esm2_650m' if '650M' in model_id else 'vectors_esm2_8m'
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Fetch vector
            query_vector = sql.SQL("""
                SELECT v.vector
                FROM {} v
                JOIN embedding_metadata m ON v.metadata_id = m.id
                WHERE m.primary_accession = %s AND m.model_id = %s
            """).format(sql.Identifier(table_name))
            
            cur.execute(query_vector, (accession, model_id))
            row = cur.fetchone()
            
            if not row or not row['vector']:
                logger.warning(f"No vector found for {accession} ({model_id})")
                return 0
            
            vector = row['vector']
            
            # Find top K+1 similar proteins (including self, which we'll filter)
            neighbors = self.find_similar(vector, model_id, limit=k+1)
            
            # Store edges in graph_edges table
            stored_count = 0
            rank = 1
            
            for neighbor in neighbors:
                # Skip self
                if neighbor['primary_accession'] == accession:
                    continue
                
                # Calculate similarity from distance (distance ∈ [0,2], similarity ∈ [0,1])
                similarity = 1.0 - float(neighbor['distance'])
                
                try:
                    cur.execute("""
                        INSERT INTO graph_edges 
                        (source_accession, target_accession, similarity, rank, model_id)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (source_accession, target_accession, model_id)
                        DO UPDATE SET 
                            similarity = EXCLUDED.similarity,
                            rank = EXCLUDED.rank,
                            created_at = NOW()
                    """, (accession, neighbor['primary_accession'], similarity, rank, model_id))
                    
                    rank += 1
                    stored_count += 1
                    
                    if stored_count >= k:
                        break
                        
                except Exception as e:
                    logger.error(f"Failed to store edge {accession} -> {neighbor['primary_accession']}: {e}")
                    continue
            
            self.conn.commit()
            logger.debug(f"Stored {stored_count} neighbors for {accession}")
            return stored_count
    
    def precompute_all_neighbors(self, model_id: str, k: int = 10):
        # Batch pre compute neighbors for all proteins in a model
        # This is typically run once during initialization or after bulk ingestion

        import logging
        logger = logging.getLogger(__name__)
        
        # Get all accessions for this model
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT primary_accession 
                FROM embedding_metadata 
                WHERE model_id = %s AND primary_accession IS NOT NULL
            """, (model_id,))
            
            accessions = [row[0] for row in cur.fetchall()]
        
        if not accessions:
            logger.warning(f"No proteins found for model {model_id}")
            return 0
        
        logger.info(f"Pre-computing neighbors for {len(accessions)} proteins (k={k})...")
        
        total_edges = 0
        for i, accession in enumerate(accessions):
            try:
                count = self.precompute_neighbors_for_protein(accession, model_id, k)
                total_edges += count
                
                if (i + 1) % 10 == 0:
                    logger.info(f"  Progress: {i+1}/{len(accessions)} proteins processed")
                    
            except Exception as e:
                logger.error(f"Failed to compute neighbors for {accession}: {e}")
                continue
        
        logger.info(f"✓ Neighbor pre-computation complete: {total_edges} edges created")
        return total_edges
    
    def get_precomputed_neighbors(self, accession: str, model_id: str, limit: int = 10):
        # Retrieve pre-computed neighbors from graph_edges table

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    m.primary_accession,
                    m.protein_name,
                    m.organism,
                    m.confidence_score,
                    m.is_fallback,
                    e.similarity,
                    e.rank
                FROM graph_edges e
                JOIN embedding_metadata m ON e.target_accession = m.primary_accession
                WHERE e.source_accession = %s 
                  AND e.model_id = %s
                ORDER BY e.rank ASC
                LIMIT %s
            """, (accession, model_id, limit))
            
            return cur.fetchall()
    
    def get_all_accessions(self, model_id: str):
        # Get list of all accessions for a model
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT primary_accession 
                FROM embedding_metadata 
                WHERE model_id = %s AND primary_accession IS NOT NULL
            """, (model_id,))
            return [row[0] for row in cur.fetchall()]
    
    def get_vector_by_accession(self, accession: str, model_id: str):
        # Get raw vector for an accession
        table_name = 'vectors_esm2_650m' if '650M' in model_id else 'vectors_esm2_8m'
        
        with self.conn.cursor() as cur:
            query = sql.SQL("""
                SELECT v.vector
                FROM {} v
                JOIN embedding_metadata m ON v.metadata_id = m.id
                WHERE m.primary_accession = %s AND m.model_id = %s
            """).format(sql.Identifier(table_name))
            
            cur.execute(query, (accession, model_id))
            row = cur.fetchone()
            return row[0] if row else None
    
    def check_positions_exist(self, model_id: str, method: str = 'umap') -> int:
        # Check if 3D positions are computed for this model
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) 
                FROM graph_positions 
                WHERE model_id = %s AND method = %s
            """, (model_id, method))
            return cur.fetchone()[0]
    
    def check_edges_exist(self, model_id: str) -> int:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(DISTINCT source_accession) 
                FROM graph_edges 
                WHERE model_id = %s
            """, (model_id,))
            return cur.fetchone()[0]
    
    def get_proteins_without_positions(self, model_id: str = "esm2_t33_650M_UR50D") -> int:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(DISTINCT m.primary_accession)
                FROM embedding_metadata m
                JOIN vectors_esm2_650m v ON m.id = v.metadata_id
                LEFT JOIN graph_positions gp ON m.primary_accession = gp.accession 
                    AND gp.model_id = %s
                WHERE gp.accession IS NULL 
                    AND m.model_id = %s
                    AND v.vector IS NOT NULL
            """, (model_id, model_id))
            return cur.fetchone()[0]
    
    def get_proteins_without_edges(self, model_id: str = "esm2_t33_650M_UR50D") -> int:
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(DISTINCT gp.accession)
                FROM graph_positions gp
                LEFT JOIN graph_edges ge ON gp.accession = ge.source_accession 
                    AND ge.model_id = %s
                WHERE gp.model_id = %s 
                    AND ge.source_accession IS NULL
            """, (model_id, model_id))
            return cur.fetchone()[0]