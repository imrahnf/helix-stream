# services/gateway/app/db/repository.py

"""
================================================================================
MODULE: DatabasePool, DatabaseContext, EmbeddingRepository
PURPOSE: Abstraction layer for PostgreSQL operations with connection pooling,
         HNSW vector similarity search, and transactional consistency.

KEY RESPONSIBILITIES:
  - Manage reusable PostgreSQL connection pool (1-20 concurrent connections)
  - Store embeddings + metadata with ON CONFLICT logic (unique on
    primary_accession + model_id)
  - Execute HNSW cosine distance queries for nearest-neighbor search
  - Handle JSON serialization for pdb_ids and binding_sites
  - Fallback accession lookup (exact model match → any model)
  - Batch retrieval for dashboard initialization (get_all_summaries)

DATA FLOW:
  INPUT:
    - store_rich_embedding: seq_hash, model_id, vector (1280-D float list),
      biological_data (dict), confidence_score, is_fallback flag
    - find_similar: query vector, model_id, limit (K)
    - get_embedding_by_accession: accession string, model_id
  OUTPUT:
    - Persisted rows in vectors_esm2_650m or vectors_esm2_8m (HNSW indexed)
    - Search results: accession, protein_name, organism, is_fallback, distance
    - Metadata summaries: accession, name, organism, model_id

INFRASTRUCTURE ROLE:
  The persistent data layer. Maintains the ground truth of all ingested
  proteins, their embeddings, and 3D structure links. Connection pooling ensures
  the macOS Gateway can handle concurrent ingest/search requests without
  connection exhaustion.

ERROR HANDLING STRATEGY:
  - ON CONFLICT Logic: Handles duplicate accession&model ingestions by
    updating
  - Fallback Queries: If exact model_id not found, retrieve any model for
    the accession (graceful degradation for cross-model lookups)
  - Connection Pool: Raises exception if pool exhausted (set pool max=20)
  - SQL Injection Prevention: Use psycopg2.sql.Identifier for dynamic table
    names; parameterized queries for all user input

PERFORMANCE NOTES:
  - HNSW Indexes: Created with m=16, ef_construction=128 for 1280-D vectors
  - Unique Constraint: (primary_accession, model_id) allows multiple accessions
    per sequence but prevents duplicate embeddings for same protein+model
  - Partial Indexes: Organism-based B-tree indexes for quick organism filters
================================================================================
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
            # Try to insert or update based on unique constraint (accession, model)
            query_meta = """
                INSERT INTO embedding_metadata 
                (sequence_hash, model_id, confidence_score, is_fallback, sequence_text, 
                 primary_accession, protein_name, organism, function_text, binding_sites, pdb_ids)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (primary_accession, model_id) DO UPDATE 
                SET sequence_hash = EXCLUDED.sequence_hash,
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
        # CHANGED: Dynamic retrieval for both 1280D (Titan) and 320D (Fallback) vectors
        # We use COALESCE to grab the vector from whichever table it resides in.
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