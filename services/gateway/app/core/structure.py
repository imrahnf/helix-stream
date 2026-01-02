# services/gateway/app/core/structure.py
from typing import Dict, Any

class StructureOrchestrator:
    PDB_BASE_URL = "https://files.rcsb.org/view/{id}.pdb"
    ALPHAFOLD_BASE_URL = "https://alphafold.ebi.ac.uk/files/AF-{id}-F1-model_v4.pdb"

    @classmethod
    def generate_manifest(cls, protein_data: Dict[str, Any]) -> Dict[str, Any]:
        accession = protein_data.get("primary_accession")
        # Handle cases where DB results might be stringified JSON or dicts
        pdb_ids = protein_data.get("pdb_ids", [])
        binding_sites = protein_data.get("binding_sites", [])

        if pdb_ids and len(pdb_ids) > 0:
            primary_id = pdb_ids[0]
            source, url = "RCSB_PDB", cls.PDB_BASE_URL.format(id=primary_id)
        else:
            primary_id = accession
            source, url = "ALPHAFOLD_DB", cls.ALPHAFOLD_BASE_URL.format(id=primary_id)

        return {
            "accession": accession,
            "structure": {"id": primary_id, "source": source, "url": url},
            "annotations": {"residue_highlights": binding_sites},
            "metadata": {"name": protein_data.get("protein_name"), "organism": protein_data.get("organism")}
        }