# services/gateway/app/core/orchestrator.py
import os, hashlib, torch, json, logging, requests
from typing import List, Dict, Any
from transformers import AutoTokenizer, AutoModelForMaskedLM
from app.db.repository import DatabaseContext

logger = logging.getLogger("HelixOrchestrator")

class UniProtIngestor:
    BASE_URL = "https://rest.uniprot.org/uniprotkb/search"
    FIELDS = ["accession", "protein_name", "organism_name", "sequence", "cc_function", "ft_binding", "ft_site", "xref_pdb", "xref_alphafolddb"]

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
        
        annotations = []
        for f in entry.get("features", []):
            if f.get("type") in ["Binding site", "Active site"]:
                annotations.append({
                    "label": f.get("ligand", {}).get("name") or f.get("description", "Site"),
                    "pos": f.get("location", {}).get("start", {}).get("value")
                })

        return {
            "accession": entry.get("primaryAccession"),
            "name": name,
            "organism": entry.get("organism", {}).get("scientificName", "Unknown"),
            "sequence": entry.get("sequence", {}).get("value", ""),
            "function": function_desc,
            "pdb_ids": pdb_ids,
            "annotations": annotations
        }

# Main Orchestrator
class HelixOrchestrator:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        self.local_model_name = "facebook/esm2_t6_8M_UR50D"
        self.local_model = None
        self.local_tokenizer = None
        self.ingestor = UniProtIngestor()

    def _load_model(self):
        if not self.local_model:
            logger.info(f"Loading Model: {self.local_model_name}")
            self.local_tokenizer = AutoTokenizer.from_pretrained(self.local_model_name)
            self.local_model = AutoModelForMaskedLM.from_pretrained(self.local_model_name)
            self.local_model.eval()

    def _embed_sequence(self, sequence: str):
        # Turns string into vector
        self._load_model()
        clean_seq = sequence.upper().replace(" ", "")[:1022] # Truncate to model max length
        inputs = self.local_tokenizer(clean_seq, return_tensors="pt")
        with torch.no_grad():
            outputs = self.local_model(**inputs, output_hidden_states=True)
            return outputs.hidden_states[-1].mean(dim=1).tolist()[0]

    async def ingest_from_uniprot(self, query: str, model_id: str, limit: int = 5):
        # Fetch > Parse > Embed > Save
        raw_results = self.ingestor.fetch_proteins(query, limit)
        processed_results = []

        with DatabaseContext(self.db_url) as repo:
            for raw in raw_results:
                # Normalize Data
                data = self.ingestor.parse_entry(raw)
                seq_hash = hashlib.sha256(data['sequence'].encode()).hexdigest()

                # Generate Vector
                vector = self._embed_sequence(data['sequence'])

                # Store EVERYTHING
                repo.store_rich_embedding(
                    seq_hash=seq_hash,
                    model_id=model_id,
                    vector_data=vector,
                    biological_data=data,
                    confidence_score=1.0 # UniProt data so confidence is max
                )
                
                processed_results.append({
                    "accession": data['accession'],
                    "name": data['name'],
                    "status": "INGESTED"
                })
        
        return processed_results

    async def search_similar(self, sequence: str, model_id: str, limit: int = 5):
        # Now returns rich biological context
        query_vector = self._embed_sequence(sequence)
        with DatabaseContext(self.db_url) as repo:
            return repo.find_similar(query_vector, model_id, limit)