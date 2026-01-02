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
        self.local_model_name = "facebook/esm2_t6_8M_UR50D"
        self.local_model = None
        self.local_tokenizer = None

    def _sanitize_sequence(self, sequence: str) -> str:
        lines = sequence.strip().splitlines()
        filtered = [line.strip() for line in lines if not line.startswith(">")]
        return "".join(filtered).upper().replace(" ", "")

    async def _process_locally(self, sequence: str, seq_hash: str, model_id: str):
        if not self.local_model:
            logger.info(f"Loading Local Model: {self.local_model_name}")
            self.local_tokenizer = AutoTokenizer.from_pretrained(self.local_model_name)
            self.local_model = AutoModelForMaskedLM.from_pretrained(self.local_model_name)
            self.local_model.eval()

        inputs = self.local_tokenizer(sequence, return_tensors="pt")
        with torch.no_grad():
            outputs = self.local_model(**inputs, output_hidden_states=True)
            vector = outputs.hidden_states[-1].mean(dim=1).tolist()[0]
            
            probs = torch.softmax(outputs.logits, dim=-1)
            confidence = probs.max().item()

        # Database Persistence
        with DatabaseContext(self.db_url) as repo:
            repo.store_embedding(
                seq_hash, 
                model_id, 
                vector, 
                confidence, 
                is_fallback=True, 
                sequence_text=sequence, 
                external_metadata={} 
            )
            try:
                repo.update_job_status(seq_hash, model_id, 'COMPLETED')
            except Exception as e:
                logger.warning(f"Job status update skipped: {e}")
        
        return {
            "hash": seq_hash, 
            "status": "COMPLETED",
            "source": "LOCAL_INFERENCE",
            "model": model_id,
            "data": vector, 
            "confidence": confidence,
            "external_metadata": {} 
        }

    async def analyze_sequence(self, sequence: str, model_id: str):
        clean_seq = self._sanitize_sequence(sequence)
        seq_hash = hashlib.sha256(clean_seq.encode()).hexdigest()
        return await self._process_locally(clean_seq, seq_hash, model_id)