# services/gateway/app/core/orchestrator.py
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
        self.remote_port = "9090"
        self.worker_health_port = "50051"
        self.local_model_name = "facebook/esm2_t6_8M_UR50D"
        self.local_model = None
        self.local_tokenizer = None
        self.ingestor = UniProtIngestor()

    def _clean_sequence(self, sequence: str) -> str:
        seq = re.sub(r'>.*?\n', '', sequence)
        seq = re.sub(r'[^A-Z]', '', seq.upper())
        return seq[:1022]

    def _is_worker_online(self) -> bool:
        target = f"{self.remote_host}:{self.worker_health_port}"
        try:
            with grpc.insecure_channel(target) as channel:
                stub = health_pb2_grpc.HealthStub(channel)
                response = stub.Check(health_pb2.HealthCheckRequest(service=""), timeout=0.5)
                return response.status == health_pb2.HealthCheckResponse.SERVING
        except Exception:
            return False

    def _get_vector_data(self, clean_seq: str, model_id: str):
        seq_hash = hashlib.sha256(clean_seq.encode()).hexdigest()
        
        # Attempt remote
        if "650M" in model_id:
            try:
                if self._is_worker_online():
                    target = f"{self.remote_host}:{self.remote_port}"
                    with grpc.insecure_channel(target, options=[('grpc.enable_retries', 0)]) as channel:
                        stub = cache_pb2_grpc.CacheServiceStub(channel)
                        stub.SubmitTask(cache_pb2.Task(hash=seq_hash, sequence=clean_seq, model_id=model_id), timeout=1.0)
                        
                        for _ in range(12): 
                            try:
                                res = stub.Get(cache_pb2.KeyRequest(key=seq_hash, model_id=model_id), timeout=0.5)
                                if res.found: 
                                    return json.loads(res.value), model_id, None
                            except grpc.RpcError:
                                break 
                            time.sleep(1)
            except Exception as e:
                logger.warning(f"Remote Worker fail: {e}. Falling back to Local 8M.")

        # Local Fallback
        logger.info("Executing Local Fallback Inference...")
        if not self.local_model:
            self.local_tokenizer = AutoTokenizer.from_pretrained(self.local_model_name)
            self.local_model = AutoModelForMaskedLM.from_pretrained(self.local_model_name)
            self.local_model.eval()
        
        inputs = self.local_tokenizer(clean_seq, return_tensors="pt")
        with torch.no_grad():
            outputs = self.local_model(**inputs, output_hidden_states=True)
            embeddings = outputs.hidden_states[-1].mean(dim=1)
            normalized = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            return normalized.tolist()[0], "esm2_t6_8M_UR50D", None

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