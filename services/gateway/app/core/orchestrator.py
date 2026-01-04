# services/gateway/app/core/orchestrator.py

"""
================================================================================
MODULE: HelixOrchestrator & UniProtIngestor
PURPOSE: Central coordination layer for protein ingestion, embedding computation,
         and distributed inference across macOS Gateway and Windows GPU Worker.

KEY RESPONSIBILITIES:
  - Orchestrate remote GPU inference via gRPC with intelligent failover
  - Parse UniProt REST API responses into rich protein metadata (sequence, PDB,
    organism, function, binding annotations)
  - Sanitize and validate amino acid sequences (strict ACDEFGHIKLMNPQRSTVWY)
  - Compute 1280-D ESM2 embeddings: Primary path (Windows 650M) → Fallback
    (macOS CPU 8M)
  - Hash sequences for deduplication and fast lookups
  - Persist embeddings + metadata to PostgreSQL with confidence scores

DATA FLOW:
  INPUT:
    - Raw FASTA sequences (manual) or UniProt accession IDs (e.g., "P01308")
    - Sequence strings up to 1022 amino acids
  OUTPUT:
    - Normalized 1280-D float vectors (L2-normalized)
    - Confidence scores derived from output entropy
    - Protein metadata: accession, name, organism, function, PDB IDs, binding sites
    - Status indicators: "COMPLETED_REMOTE" | "COMPLETED_LOCAL"

INFRASTRUCTURE ROLE:
  This is the brain of the distributed system. It decides whether to use the
  high fidelity Windows GPU/Model (650M params, 1280D) or fall back to the local
  macOS CPU (8M params, 320D) based on network health. Ensures graceful
  degradation without user facing failures.

ERROR HANDLING STRATEGY:
  - Sequence Validation: Regex-based strict AA filtering; raises 400 on invalid
  - gRPC Failover: Polls remote worker with exponential backoff (12 retries, 1s
    between). Times out at 2.0s for SubmitTask, 1.0s for Get. Falls through to
    local 8M model on any RpcError.
  - Network Resilience: Health check via HealthServicer before attempting remote
  - Confidence Scoring: Derived from softmax entropy
  - Resource Cleanup: No long-lived connections; all gRPC channels scoped to
    request lifetime
================================================================================
"""

import os, hashlib, torch, json, logging, requests, grpc, time, re
from typing import List, Dict, Any, Optional
from transformers import AutoTokenizer, AutoModelForMaskedLM
from app.db.repository import DatabaseContext
from app.core.structure import StructureOrchestrator

import gen.cache_pb2 as cache_pb2
import gen.cache_pb2_grpc as cache_pb2_grpc
from gen import cache_pb2 as health_pb2
from gen import cache_pb2_grpc as health_pb2_grpc

logger = logging.getLogger("HelixOrchestrator")

class UniProtIngestor:
    BASE_URL = "https://rest.uniprot.org/uniprotkb/search"
    FIELDS = ["accession", "protein_name", "organism_name", "sequence", "cc_function", "ft_binding", "ft_site", "xref_pdb"]

    def fetch_proteins(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            params = {"query": query, "fields": ",".join(self.FIELDS), "size": limit, "sort": "accession desc"}
            res = requests.get(self.BASE_URL, params=params, headers={"accept": "application/json"})
            res.raise_for_status()
            return res.json().get("results", [])
        except Exception as e:
            logger.error(f"UniProt Fetch Error: {e}")
            return []

    def parse_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        desc = entry.get("proteinDescription", {})
        name = desc.get("recommendedName", {}).get("fullName", {}).get("value") or \
               desc.get("submissionNames", [{}])[0].get("fullName", {}).get("value", "Unknown Protein")
        
        pdb_ids = [ref.get("id") for ref in entry.get("uniProtKBCrossReferences", []) if ref.get("database") == "PDB"]
        
        annotations = []
        for f in entry.get("features", []):
            if f.get("type") in ["Binding site", "Active site", "Metal binding", "Site"]:
                label = f.get("description") or f.get("ligand", {}).get("name") or f.get("type")
                pos = f.get("location", {}).get("start", {}).get("value")
                if pos: annotations.append({"label": label, "pos": pos})
        
        function_text = "No description."
        for comment in entry.get("comments", []):
            if comment.get("commentType") == "FUNCTION":
                texts = comment.get("texts", [])
                if texts: function_text = texts[0].get("value", function_text)
                break

        return {
            "accession": entry.get("primaryAccession"),
            "name": name,
            "organism": entry.get("organism", {}).get("scientificName", "Unknown"),
            "sequence": entry.get("sequence", {}).get("value", ""), 
            "function": function_text,
            "pdb_ids": pdb_ids,
            "annotations": annotations
        }

class HelixOrchestrator:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        self.remote_host = os.getenv("TITAN_CACHE_HOST", "localhost")
        self.remote_port = os.getenv("TITAN_CACHE_PORT", "9090")
        self.worker_health_port = os.getenv("WORKER_PORT", "50051")
        self.local_model_name = "facebook/esm2_t6_8M_UR50D"
        self.local_model = None
        self.local_tokenizer = None
        self.ingestor = UniProtIngestor()

    def _clean_sequence(self, sequence: str) -> str:
        # Remove FASTA headers and whitespace
        seq = re.sub(r'>.*?\n', '', sequence)
        seq = re.sub(r'\s+', '', seq).upper()

        if re.search(r'[^ACDEFGHIKLMNPQRSTVWY]', seq):
            raise ValueError("Sequence contains invalid amino acids. Only ACDEFGHIKLMNPQRSTVWY are allowed.")

        if not seq: raise ValueError("Invalid protein sequence")
        return seq[:1022]

    def _is_worker_online(self) -> bool:
        target = f"{self.remote_host}:{self.worker_health_port}"
        try:
            with grpc.insecure_channel(target) as channel:
                stub = health_pb2_grpc.HealthStub(channel)
                response = stub.Check(health_pb2.HealthCheckRequest(service=""), timeout=0.5)
                is_online = response.status == health_pb2.HealthCheckResponse.SERVING
                logger.info(f"Worker health check: {target} -> {'ONLINE' if is_online else 'OFFLINE'}")
                return is_online
        except Exception as e:
            logger.warning(f"Worker health check failed for {target}: {e}")
            return False

    def _get_vector_data(self, clean_seq: str, model_id: str):
        seq_hash = hashlib.sha256(clean_seq.encode()).hexdigest()
        
        # Attempt remote
        if "650M" in model_id:
            try:
                if self._is_worker_online():
                    target = f"{self.remote_host}:{self.remote_port}"
                    with grpc.insecure_channel(target, options=[('grpc.enable_retries', 1), ('grpc.keepalive_timeout_ms', 10000)]) as channel:
                        stub = cache_pb2_grpc.CacheServiceStub(channel)
                        try:
                            stub.SubmitTask(cache_pb2.Task(hash=seq_hash, sequence=clean_seq, model_id=model_id), timeout=2.0)
                        except grpc.RpcError as e:
                            logger.error(f"SubmitTask failed: {e.code()} - {e.details()}")
                            raise e

                        for _ in range(12): 
                            try:
                                res = stub.Get(cache_pb2.KeyRequest(key=seq_hash, model_id=model_id), timeout=1.0)
                                if res.found: 
                                    return json.loads(res.value), model_id, res.confidence_score
                            except grpc.RpcError:
                                pass # Retry loop
                            time.sleep(1)
            except Exception as e:
                logger.warning(f"Remote Worker fail: {e}. Falling back to Local 8M.")

        # Local Fallback
        logger.info("Executing Local Fallback Inference...")
        if self.local_model is None:
            logger.info(f"Loading local model: {self.local_model_name}")
            self.local_tokenizer = AutoTokenizer.from_pretrained(self.local_model_name)
            self.local_model = AutoModelForMaskedLM.from_pretrained(self.local_model_name)
            self.local_model.eval()
        
        inputs = self.local_tokenizer(clean_seq, return_tensors="pt")
        with torch.no_grad():
            outputs = self.local_model(**inputs, output_hidden_states=True)
            embeddings = outputs.hidden_states[-1].mean(dim=1)
            normalized = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            
            # Calculate confidence from softmax entropy (matching remote worker behavior)
            logits = outputs.logits
            probs = torch.nn.functional.softmax(logits, dim=-1)
            entropy = -torch.sum(probs * torch.log(probs + 1e-10), dim=-1)
            confidence = 1.0 - (entropy.mean().item() / 10.0)  # Normalize entropy to [0, 1]
            confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
            
            logger.info(f"Local inference complete. Confidence: {confidence:.3f}")
            return normalized.tolist()[0], "esm2_t6_8M_UR50D", confidence

    async def ingest_manual_sequence(self, sequence: str, model_id: str):
        clean_seq = self._clean_sequence(sequence)
        seq_hash = hashlib.sha256(clean_seq.encode()).hexdigest()
        vector, active_model, confidence = self._get_vector_data(clean_seq, model_id)
        
        data = {
            "accession": f"MAN-{seq_hash[:8]}",
            "name": "Manual Ingestion",
            "organism": "User Defined",
            "sequence": clean_seq,
            "function": "Manually ingested sequence.",
            "annotations": [],
            "pdb_ids": []
        }

        is_fallback = (active_model != model_id)

        with DatabaseContext(self.db_url) as repo:
            repo.store_rich_embedding(seq_hash, active_model, vector, data, confidence, is_fallback=is_fallback)
        
        return [{
            "accession": data['accession'], 
            "status": f"COMPLETED_{'LOCAL' if is_fallback else 'REMOTE'}",
            "model_used": active_model
        }]

    async def ingest_from_uniprot(self, query: str, model_id: str, limit: int = 5):
        raw_results = self.ingestor.fetch_proteins(query, limit)
        processed = []
        with DatabaseContext(self.db_url) as repo:
            for raw in raw_results:
                data = self.ingestor.parse_entry(raw)
                clean_seq = self._clean_sequence(data['sequence'])
                seq_hash = hashlib.sha256(clean_seq.encode()).hexdigest()
                vector, active_model, confidence = self._get_vector_data(clean_seq, model_id)
                repo.store_rich_embedding(seq_hash, active_model, vector, data, confidence, is_fallback=(active_model != model_id))
                processed.append({"accession": data['accession'], "name": data['name'], "status": "COMPLETED"})
        return processed

    async def search_similar(self, sequence: str, model_id: str, limit: int = 5):
        clean_seq = self._clean_sequence(sequence)
        vector, active_model, _ = self._get_vector_data(clean_seq, model_id)
        with DatabaseContext(self.db_url) as repo:
            return repo.find_similar(vector, active_model, limit)

    async def get_structure_data(self, accession: str, model_id: str):
        with DatabaseContext(self.db_url) as repo:
            protein_data = repo.get_embedding_by_accession(accession, model_id)
            return StructureOrchestrator.generate_manifest(protein_data) if protein_data else None