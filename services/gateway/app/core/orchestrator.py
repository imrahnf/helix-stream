# services/gateway/app/core/orchestrator.py
import os, hashlib, torch, json, logging, requests, grpc
from typing import List, Dict, Any
from transformers import AutoTokenizer, AutoModelForMaskedLM
from app.db.repository import DatabaseContext
from app.core.structure import StructureOrchestrator

import gen.cache_pb2 as cache_pb2
import gen.cache_pb2_grpc as cache_pb2_grpc

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
        function_desc = next((c["texts"][0]["value"] for c in entry.get("comments", []) if c.get("commentType") == "FUNCTION"), "No description.")
        pdb_ids = [x["id"] for x in entry.get("uniProtKBCrossReferences", []) if x["database"] == "PDB"]
        annotations = [{"label": f.get("ligand", {}).get("name") or f.get("description", "Site"), 
                        "pos": f.get("location", {}).get("start", {}).get("value")} 
                       for f in entry.get("features", []) if f.get("type") in ["Binding site", "Active site"]]
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
        
        self.local_model_name = "facebook/esm2_t6_8M_UR50D"
        self.local_model = None
        self.local_tokenizer = None
        self.ingestor = UniProtIngestor()

    def _is_remote_available(self) -> bool:
        # Ping the Windows TitanCache to check if the GPU pipeline is alive
        try:
            channel = grpc.insecure_channel(f"{self.remote_host}:{self.remote_port}")
            # Use a short timeout (1 second) for the heartbeat
            grpc.channel_ready_future(channel).result(timeout=1)
            return True
        except Exception:
            logger.warning(f"Remote GPU Node ({self.remote_host}) unreachable. Using local fallback.")
            return False

    def _load_local_model(self):
        if not self.local_model:
            logger.info(f"Loading Fallback Model: {self.local_model_name}")
            self.local_tokenizer = AutoTokenizer.from_pretrained(self.local_model_name)
            self.local_model = AutoModelForMaskedLM.from_pretrained(self.local_model_name)
            self.local_model.eval()

    def _run_local_inference(self, sequence: str) -> List[float]:
        # Calculates 8M embedding on the mac CPU
        self._load_local_model()
        clean_seq = sequence.upper().replace(" ", "")[:1022]
        inputs = self.local_tokenizer(clean_seq, return_tensors="pt")
        with torch.no_grad():
            outputs = self.local_model(**inputs, output_hidden_states=True)
            return outputs.hidden_states[-1].mean(dim=1).tolist()[0]

    async def ingest_from_uniprot(self, query: str, model_id: str, limit: int = 5):
        raw_results = self.ingestor.fetch_proteins(query, limit)
        processed = []
        
        # Check if we should use the distributed path
        use_remote = self._is_remote_available() if "650M" in model_id else False

        with DatabaseContext(self.db_url) as repo:
            for raw in raw_results:
                data = self.ingestor.parse_entry(raw)
                seq_hash = hashlib.sha256(data['sequence'].encode()).hexdigest()
                
                vector = None
                active_model = model_id

                if use_remote:
                    try:
                        # Submit task to Windows
                        channel = grpc.insecure_channel(f"{self.remote_host}:{self.remote_port}")
                        stub = cache_pb2_grpc.CacheServiceStub(channel)
                        task = cache_pb2.Task(hash=seq_hash, sequence=data['sequence'], model_id=model_id)
                        stub.SubmitTask(task)
                        
                        logger.info(f"Task {seq_hash} delegated to Windows GPU.")
                        vector = [0.0] * 1280 # Placeholder until worker completes
                    except Exception as e:
                        logger.error(f"gRPC Submission failed: {e}")
                        use_remote = False # Force fallback for remaining batch

                if not use_remote or vector is None:
                    # Fallback- run on Mac
                    active_model = "esm2_t6_8M_UR50D"
                    vector = self._run_local_inference(data['sequence'])
                    logger.info(f"Task {seq_hash} processed locally via Fallback.")

                repo.store_rich_embedding(seq_hash, active_model, vector, data, 1.0)
                processed.append({
                    "accession": data['accession'], 
                    "name": data['name'], 
                    "status": "DELEGATED" if use_remote else "COMPLETED_LOCAL"
                })
                
        return processed