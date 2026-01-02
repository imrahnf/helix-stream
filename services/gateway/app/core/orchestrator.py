# services/gateway/app/core/orchestrator.py
import os, hashlib, torch, json, logging
from transformers import AutoTokenizer, AutoModelForMaskedLM
from app.db.repository import DatabaseContext

logger = logging.getLogger("HelixOrchestrator")

class HelixOrchestrator:
    def __init__(self):
        self.host = os.getenv("TITAN_IP", os.getenv("TITAN_CACHE_HOST", "localhost"))
        self.is_remote_healthy = False 
        self.db_url = os.getenv("DATABASE_URL")
        
        # Local Model Settings
        self.local_model_name = "facebook/esm2_t6_8M_UR50D"
        self.local_model = None
        self.local_tokenizer = None

    def _sanitize_sequence(self, sequence: str) -> str:
        # FASTA sequence cleaner
        lines = sequence.strip().splitlines()
        filtered = [line.strip() for line in lines if not line.startswith(">")]
        return "".join(filtered).upper().replace(" ", "")

    def _load_model(self):
        # Lazy loads the ESM2 model into memory
        if not self.local_model:
            logger.info(f"Loading Fallback Model: {self.local_model_name}")
            self.local_tokenizer = AutoTokenizer.from_pretrained(self.local_model_name)
            self.local_model = AutoModelForMaskedLM.from_pretrained(self.local_model_name)
            self.local_model.eval()

    async def analyze_sequence(self, sequence: str, model_id: str):
        # Generates embedding and stores it locally
        clean_seq = self._sanitize_sequence(sequence)
        seq_hash = hashlib.sha256(clean_seq.encode()).hexdigest()
        
        self._load_model()
        
        inputs = self.local_tokenizer(clean_seq, return_tensors="pt")
        with torch.no_grad():
            outputs = self.local_model(**inputs, output_hidden_states=True)
            # Extract the mean embedding from the last hidden layer
            embedding = outputs.hidden_states[-1].mean(dim=1).tolist()[0]
            
            # Confidence metric based on softmax of logits
            probs = torch.softmax(outputs.logits, dim=-1)
            confidence = probs.max().item()

        # Save to Postgres
        with DatabaseContext(self.db_url) as repo:
            repo.store_embedding(
                seq_hash, 
                model_id, 
                embedding, 
                confidence, 
                is_fallback=True,
                sequence_text=clean_seq,
                external_metadata={} # For later
            )
            try:
                repo.update_job_status(seq_hash, model_id, 'COMPLETED')
            except:
                pass

        return {
            "hash": seq_hash,
            "status": "COMPLETED",
            "source": "LOCAL_INFERENCE",
            "model": model_id,
            "data": embedding, 
            "confidence": confidence,
            "external_metadata": {}
        }

    async def search_similar(self, sequence: str, model_id: str, limit: int = 5):
        # Vector similarity search using pgvector
        clean_seq = self._sanitize_sequence(sequence)
        
        self._load_model()
        inputs = self.local_tokenizer(clean_seq, return_tensors="pt")
        with torch.no_grad():
            outputs = self.local_model(**inputs, output_hidden_states=True)
            query_vector = outputs.hidden_states[-1].mean(dim=1).tolist()[0]

        with DatabaseContext(self.db_url) as repo:
            neighbors = repo.find_similar(query_vector, model_id, limit)
            
        return neighbors