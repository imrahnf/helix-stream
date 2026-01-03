# services/gateway/app/db/repository.py
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
        with self.conn.cursor() as cur:
            query_meta = """
                INSERT INTO embedding_metadata 
                (sequence_hash, model_id, confidence_score, is_fallback, sequence_text, 
                 primary_accession, protein_name, organism, function_text, binding_sites, pdb_ids)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sequence_hash, model_id) DO UPDATE 
                SET confidence_score = EXCLUDED.confidence_score,
                    is_fallback = EXCLUDED.is_fallback,
                    protein_name = EXCLUDED.protein_name,
                    pdb_ids = EXCLUDED.pdb_ids,
                    binding_sites = EXCLUDED.binding_sites
                RETURNING id;
            """
            cur.execute(query_meta, (
                seq_hash, model_id, confidence_score, is_fallback, biological_data['sequence'],
                biological_data.get('accession'), biological_data.get('name'),
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
            cur.execute("SELECT * FROM embedding_metadata WHERE primary_accession = %s LIMIT 1", (accession,))
            row = cur.fetchone()
            if not row: return None
            # Fix json loading
            for key in ['pdb_ids', 'binding_sites']:
                if row.get(key) and isinstance(row[key], str):
                    row[key] = json.loads(row[key])
            return row
            
    def get_all_summaries(self, limit=100):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT primary_accession, protein_name, organism, is_fallback, model_id FROM embedding_metadata LIMIT %s", (limit,))
            return cur.fetchall()