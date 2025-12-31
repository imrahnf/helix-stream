# services/gateway/app/db/repository.py
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import logging

class DatabaseContext:
    def __init__(self, db_url):
        self.db_url = db_url
        self.conn = None

    def __enter__(self):
        self.conn = psycopg2.connect(self.db_url)
        return EmbeddingRepository(self.conn)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

class EmbeddingRepository:
    def __init__(self, conn):
        self.conn = conn

    def get_embedding(self, seq_hash: str, model_id: str):
        # Determine which table to query for the vector based on model
        vector_table = None
        if model_id == 'esm2_t6_8M_UR50D':
            vector_table = 'vectors_esm2_8m'
        elif model_id == 'esm2_t33_650M_UR50D':
            vector_table = 'vectors_esm2_650m'
        
        # If we don't know the table, we can't return the vector
        if not vector_table:
            return None

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Join metadata with the specific vector table
            query = f"""
                SELECT m.confidence_score, m.created_at, m.raw_json, v.vector
                FROM embedding_metadata m
                JOIN {vector_table} v ON m.id = v.metadata_id
                WHERE m.sequence_hash = %s AND m.model_id = %s
            """
            cur.execute(query, (seq_hash, model_id))
            row = cur.fetchone()
            
            if row:
                # Ensure vector is returned in a format Orchestrator expects
                return row
            return None

    def get_job_status(self, seq_hash: str, model_id: str):
        with self.conn.cursor() as cur:
            query = """
                SELECT status 
                FROM inference_jobs 
                WHERE sequence_hash = %s AND model_id = %s
            """
            cur.execute(query, (seq_hash, model_id))
            result = cur.fetchone()
            return result[0] if result else None

    def create_job(self, seq_hash: str, model_id: str, compute_node: str = "UNKNOWN"):
        with self.conn.cursor() as cur:
            query = """
                INSERT INTO inference_jobs (sequence_hash, model_id, status, compute_node)
                VALUES (%s, %s, 'PENDING', %s)
                ON CONFLICT DO NOTHING
            """
            cur.execute(query, (seq_hash, model_id, compute_node))
            self.conn.commit()

    def store_embedding(self, seq_hash: str, model_id: str, vector_data, confidence_score: float = 0.0, is_fallback: bool = False):
        # Handle input formats (JSON string vs List)
        if isinstance(vector_data, str):
            try:
                vector_list = json.loads(vector_data)
            except:
                vector_list = [] # Fail safe
        else:
            vector_list = vector_data

        with self.conn.cursor() as cur:
            # Insert Metadata
            query_meta = """
                INSERT INTO embedding_metadata 
                (sequence_hash, model_id, confidence_score, is_fallback, raw_json)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (sequence_hash, model_id) DO UPDATE 
                SET confidence_score = EXCLUDED.confidence_score,
                    is_fallback = EXCLUDED.is_fallback
                RETURNING id;
            """
            # We store the raw JSON in metadata too for easy frontend access
            cur.execute(query_meta, (seq_hash, model_id, confidence_score, is_fallback, json.dumps(vector_list)))
            meta_id = cur.fetchone()[0]

            # Router: Choose the correct vector table
            table = None
            if model_id == 'esm2_t6_8M_UR50D':
                table = 'vectors_esm2_8m'
            elif model_id == 'esm2_t33_650M_UR50D':
                table = 'vectors_esm2_650m'
            
            if table:
                query_vec = f"""
                    INSERT INTO {table} (metadata_id, vector)
                    VALUES (%s, %s)
                    ON CONFLICT (metadata_id) DO UPDATE SET vector = EXCLUDED.vector;
                """
                cur.execute(query_vec, (meta_id, vector_list))
            
            self.conn.commit()

    def update_job_status(self, seq_hash: str, model_id: str, status: str):
        with self.conn.cursor() as cur:
            query = """
                UPDATE inference_jobs SET status = %s
                WHERE sequence_hash = %s AND model_id = %s
            """
            cur.execute(query, (status, seq_hash, model_id))
            self.conn.commit()