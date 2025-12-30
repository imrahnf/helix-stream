# services/gateway/app/db/repository.py
import psycopg2
from psycopg2.extras import RealDictCursor
import os

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
        # Fetch embedding specific to the requested model version
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT vector, created_at 
                FROM embeddings 
                WHERE sequence_hash = %s AND model_id = %s
            """
            cur.execute(query, (seq_hash, model_id))
            return cur.fetchone()

    def get_job_status(self, seq_hash: str, model_id: str):
        # Check if this model is already working on this sequence
        with self.conn.cursor() as cur:
            query = """
                SELECT status 
                FROM inference_jobs 
                WHERE sequence_hash = %s AND model_id = %s
            """
            cur.execute(query, (seq_hash, model_id))
            result = cur.fetchone()
            return result[0] if result else None

    def create_job(self, seq_hash: str, model_id: str):
            # Create job linked to the specific model
            with self.conn.cursor() as cur:
                query = """
                    INSERT INTO inference_jobs (sequence_hash, model_id, status)
                    VALUES (%s, %s, 'PENDING')
                    ON CONFLICT DO NOTHING
                """
                cur.execute(query, (seq_hash, model_id))
                self.conn.commit()