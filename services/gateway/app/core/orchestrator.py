# services/gateway/app/core/orchestrator.py
import os, hashlib, torch, json, logging, requests, grpc, time, re
from typing import List, Dict, Any
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
               desc.get("submissionNames", [{}])[0].get("fullName", {}).get("value", "Unknown")
        
        function_desc = "No description."
        for comment in entry.get("comments", []):
            if comment.get("commentType") == "FUNCTION":
                texts = comment.get("texts", [])
                if texts: function_desc = texts[0].get("value", function_desc)
                break

        pdb_ids = [x.get("id") for x in entry.get("uniProtKBCrossReferences", []) if x.get("database") == "PDB"]
        annotations = []
        for f in entry.get("features", []):
            if f.get("type") in ["Binding site", "Active site"]:
                label = f.get("ligand", {}).get("name") or f.get("description") or f.get("type")
                pos = f.get("location", {}).get("start", {}).get("value")
                if pos: annotations.append({"label": label, "pos": pos})
        
        return {
            "accession": entry.get("primaryAccession"),
            "name": name,
            "organism": entry.get("organism", {}).get("scientificName", "Unknown"),
            "sequence": entry.get("sequence", {}).get("value", ""), 
            "function": function_desc,
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
                response = stub.Check(health_pb2.HealthCheckRequest(service=""), timeout=1.0)
                return response.status == health_pb2.HealthCheckResponse.SERVING
        except Exception:
            return False

    def _load_local_model(self):
        if not self.local_model:
            self.local_tokenizer = AutoTokenizer.from_pretrained(self.local_model_name)
            self.local_model = AutoModelForMaskedLM.from_pretrained(self.local_model_name)
            self.local_model.eval()

    def _run_local_inference(self, sequence: str) -> List[float]:
        self._load_local_model()
        clean_seq = self._clean_sequence(sequence)
        inputs = self.local_tokenizer(clean_seq, return_tensors="pt")
        with torch.no_grad():
            outputs = self.local_model(**inputs, output_hidden_states=True)
            return outputs.hidden_states[-1].mean(dim=1).tolist()[0]

    async def ingest_from_uniprot(self, query: str, model_id: str, limit: int = 5):
        raw_results = self.ingestor.fetch_proteins(query, limit)
        processed = []
        is_gpu_ready = self._is_worker_online() if "650M" in model_id else False
        
        with DatabaseContext(self.db_url) as repo:
            for raw in raw_results:
                data = self.ingestor.parse_entry(raw)
                clean_seq = self._clean_sequence(data['sequence'])
                seq_hash = hashlib.sha256(clean_seq.encode()).hexdigest()
                vector, active_model, was_fallback = None, model_id, False
                
                if is_gpu_ready:
                    try:
                        target = f"{self.remote_host}:{self.remote_port}"
                        with grpc.insecure_channel(target) as channel:
                            stub = cache_pb2_grpc.CacheServiceStub(channel)
                            stub.SubmitTask(cache_pb2.Task(hash=seq_hash, sequence=clean_seq, model_id=model_id))
                            for _ in range(15):
                                cache_res = stub.Get(cache_pb2.KeyRequest(key=seq_hash, model_id=model_id))
                                if cache_res.found:
                                    vector = json.loads(cache_res.value)
                                    break
                                time.sleep(1)
                    except Exception: is_gpu_ready = False

                if vector is None:
                    active_model, was_fallback = "esm2_t6_8M_UR50D", True
                    vector = self._run_local_inference(clean_seq)

                repo.store_rich_embedding(seq_hash, active_model, vector, data, 1.0, is_fallback=was_fallback)
                processed.append({"accession": data['accession'], "name": data['name'], "status": "COMPLETED_REMOTE" if not was_fallback else "COMPLETED_LOCAL"})
        return processed

    async def search_similar(self, sequence: str, model_id: str, limit: int = 5):
        clean_seq = self._clean_sequence(sequence)
        vector = None
        active_model = model_id

        # If searching 650M we need the worker for 1280D
        if "650M" in model_id and self._is_worker_online():
            try:
                target = f"{self.remote_host}:{self.remote_port}"
                seq_hash = hashlib.sha256(clean_seq.encode()).hexdigest()
                with grpc.insecure_channel(target) as channel:
                    stub = cache_pb2_grpc.CacheServiceStub(channel)
                    stub.SubmitTask(cache_pb2.Task(hash=seq_hash, sequence=clean_seq, model_id=model_id))
                    for _ in range(10):
                        cache_res = stub.Get(cache_pb2.KeyRequest(key=seq_hash, model_id=model_id))
                        if cache_res.found:
                            vector = json.loads(cache_res.value)
                            break
                        time.sleep(0.5)
            except: pass

        if vector is None:
            # Fallback to local 8M search
            active_model = "esm2_t6_8M_UR50D"
            vector = self._run_local_inference(clean_seq)

        with DatabaseContext(self.db_url) as repo:
            return repo.find_similar(vector, active_model, limit)

    async def get_structure_data(self, accession: str, model_id: str):
        with DatabaseContext(self.db_url) as repo:
            protein_data = repo.get_embedding_by_accession(accession, model_id)
            if not protein_data: return None
            return StructureOrchestrator.generate_manifest(protein_data)