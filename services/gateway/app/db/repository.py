# services/gateway/app/db/repository.py
import psycopg2
from psycopg2.extras import RealDictCursor
import json

class DatabaseContext:
    def __init__(self, db_url):
        self.db_url = db_url
        self.conn = None

    def __enter__(self):
        self.conn = psycopg2.connect(self.db_url)
        return EmbeddingRepository(self.conn)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn: self.conn.close()

class EmbeddingRepository:
    def __init__(self, conn):
        self.conn = conn

    def store_embedding(self, seq_hash, model_id, vector_data, confidence_score=0.0, is_fallback=False, sequence_text=None, external_metadata=None):
        vector_list = json.loads(vector_data) if isinstance(vector_data, str) else vector_data
        
        with self.conn.cursor() as cur:
            query_meta = """
                INSERT INTO embedding_metadata 
                (sequence_hash, model_id, confidence_score, is_fallback, raw_json, sequence_text, external_metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sequence_hash, model_id) DO UPDATE 
                SET confidence_score = EXCLUDED.confidence_score,
                    external_metadata = EXCLUDED.external_metadata
                RETURNING id;
            """
            cur.execute(query_meta, (
                seq_hash, model_id, confidence_score, is_fallback, 
                json.dumps(vector_list), sequence_text, json.dumps(external_metadata or {})
            ))
            meta_id = cur.fetchone()[0]

            table = 'vectors_esm2_8m' if model_id == 'esm2_t6_8M_UR50D' else 'vectors_esm2_650m'
            query_vec = f"INSERT INTO {table} (metadata_id, vector) VALUES (%s, %s) ON CONFLICT (metadata_id) DO UPDATE SET vector = EXCLUDED.vector;"
            cur.execute(query_vec, (meta_id, vector_list))
            self.conn.commit()

    def find_similar(self, vector, model_id, limit=5):
        # Vector similarity search- pgvector cosine distance
        table = 'vectors_esm2_650m' if '650M' in model_id else 'vectors_esm2_8m'
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = f"""
                SELECT m.sequence_hash, m.sequence_text, m.external_metadata,
                       (v.vector <=> %s::vector) as distance
                FROM {table} v
                JOIN embedding_metadata m ON v.metadata_id = m.id
                WHERE m.model_id = %s
                ORDER BY distance ASC
                LIMIT %s
            """
            cur.execute(query, (vector, model_id, limit))
            return cur.fetchall()

    def get_embedding(self, seq_hash: str, model_id: str):
        table = 'vectors_esm2_8m' if model_id == 'esm2_t6_8M_UR50D' else 'vectors_esm2_650m'
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = f"SELECT m.*, v.vector FROM embedding_metadata m JOIN {table} v ON m.id = v.metadata_id WHERE m.sequence_hash = %s AND m.model_id = %s"
            cur.execute(query, (seq_hash, model_id))
            return cur.fetchone()

    def get_job_status(self, seq_hash: str, model_id: str):
        with self.conn.cursor() as cur:
            cur.execute("SELECT status FROM inference_jobs WHERE sequence_hash = %s AND model_id = %s", (seq_hash, model_id))
            result = cur.fetchone()
            return result[0] if result else None

    def create_job(self, seq_hash: str, model_id: str, compute_node: str = "UNKNOWN"):
        with self.conn.cursor() as cur:
            query = "INSERT INTO inference_jobs (sequence_hash, model_id, status, compute_node) VALUES (%s, %s, 'PENDING', %s) ON CONFLICT DO NOTHING"
            cur.execute(query, (seq_hash, model_id, compute_node))
            self.conn.commit()
            
    def update_job_status(self, seq_hash, model_id, status):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE inference_jobs SET status = %s WHERE sequence_hash = %s AND model_id = %s", (status, seq_hash, model_id))
            self.conn.commit()