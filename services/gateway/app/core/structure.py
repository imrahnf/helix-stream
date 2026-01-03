# services/gateway/app/core/structure.py
import json
from typing import Dict, Any

class StructureOrchestrator:
    PDB_BASE_URL = "https://files.rcsb.org/view/{id}.pdb"
    ALPHAFOLD_BASE_URL = "https://alphafold.ebi.ac.uk/files/AF-{id}-F1-model_v4.pdb"

    @classmethod
    def generate_manifest(cls, protein_data: Dict[str, Any]) -> Dict[str, Any]:
        accession = protein_data.get("primary_accession")
        
        pdb_ids = protein_data.get("pdb_ids")
        if pdb_ids is None: pdb_ids = []
        
        binding_sites = protein_data.get("binding_sites")
        if binding_sites is None: binding_sites = []

        # PDB Priority Logic
        if len(pdb_ids) > 0:
            primary_id = pdb_ids[0]
            source = "RCSB_PDB"
            url = cls.PDB_BASE_URL.format(id=primary_id)
            is_verified = True
        else:
            primary_id = accession
            source = "ALPHAFOLD_DB"
            url = cls.ALPHAFOLD_BASE_URL.format(id=primary_id)
            is_verified = False

        return {
            "accession": accession,
            "structure": {
                "id": primary_id,
                "source": source,
                "url": url,
                "is_verified": is_verified
            },
            "annotations": {
                "residue_highlights": binding_sites
            },
            "metadata": {
                "name": protein_data.get("protein_name"),
                "organism": protein_data.get("organism"),
                "function": protein_data.get("function_text"),
                "fidelity": "ESM2-650M (High-Resolution)" if not protein_data.get("is_fallback") else "ESM2-8M (Standard)"
            }
        }