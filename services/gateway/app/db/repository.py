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

    def store_rich_embedding(self, seq_hash, model_id, vector_data, biological_data, confidence_score=0.0):
        vector_list = json.loads(vector_data) if isinstance(vector_data, str) else vector_data
        with self.conn.cursor() as cur:
            query_meta = """
                INSERT INTO embedding_metadata 
                (sequence_hash, model_id, confidence_score, is_fallback, sequence_text, 
                 primary_accession, protein_name, organism, function_text, binding_sites, pdb_ids)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sequence_hash, model_id) DO UPDATE 
                SET confidence_score = EXCLUDED.confidence_score,
                    protein_name = EXCLUDED.protein_name,
                    function_text = EXCLUDED.function_text,
                    pdb_ids = EXCLUDED.pdb_ids
                RETURNING id;
            """
            cur.execute(query_meta, (
                seq_hash, model_id, confidence_score, True, biological_data['sequence'],
                biological_data.get('accession'), biological_data.get('name'),
                biological_data.get('organism'), biological_data.get('function'),
                json.dumps(biological_data.get('annotations', [])),
                json.dumps(biological_data.get('pdb_ids', []))
            ))
            meta_id = cur.fetchone()[0]
            table = 'vectors_esm2_8m' if model_id == 'esm2_t6_8M_UR50D' else 'vectors_esm2_650m'
            query_vec = f"INSERT INTO {table} (metadata_id, vector) VALUES (%s, %s) ON CONFLICT (metadata_id) DO UPDATE SET vector = EXCLUDED.vector;"
            cur.execute(query_vec, (meta_id, vector_list))
            self.conn.commit()

    def find_similar(self, vector, model_id, limit=5):
        table = 'vectors_esm2_650m' if '650M' in model_id else 'vectors_esm2_8m'
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = f"""
                SELECT m.primary_accession, m.protein_name, m.organism, m.function_text, m.pdb_ids,
                       (v.vector <=> %s::vector) as distance
                FROM {table} v
                JOIN embedding_metadata m ON v.metadata_id = m.id
                WHERE m.model_id = %s
                ORDER BY distance ASC
                LIMIT %s
            """
            cur.execute(query, (vector, model_id, limit))
            return cur.fetchall()

    def get_embedding_by_accession(self, accession: str, model_id: str):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = "SELECT * FROM embedding_metadata WHERE primary_accession = %s AND model_id = %s"
            cur.execute(query, (accession, model_id))
            return cur.fetchone()