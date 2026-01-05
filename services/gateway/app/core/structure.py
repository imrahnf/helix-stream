"""
File Overview: Structure manifest builder for mapping proteins to 3D resources for HelixStream visualization.
Responsibilities:
- Choose primary structure source (RCSB PDB first, else AlphaFold) and build download/render URLs.
- Package residue-level highlights and metadata into a manifest for frontend 3D viewers.
Data Flow:
- Inputs: protein metadata dict (primary_accession, pdb_ids, binding_sites, names, organism, function, confidence, sequence).
- Outputs: manifest dict with structure details, annotations, and metadata for rendering.
System Integration:
- Feeds manifests to frontend components that render via 3Dmol/AlphaFold viewers; relies on data from embedding_metadata rows.
Technical Details:
- Sets verification flag based on source (PDB vs AlphaFold) and preserves all PDB IDs; no external calls at generation time.
Future Considerations:
- Validate accession formats/URLs and enrich annotations (domains, variants) as data becomes available.
"""

from typing import Dict, Any

class StructureOrchestrator:
    PDB_BASE_URL = "https://files.rcsb.org/view/{id}.pdb"
    ALPHAFOLD_BASE_URL = "https://alphafold.ebi.ac.uk/files/AF-{id}-F1-model_v4.pdb"

    @classmethod
    def generate_manifest(cls, protein_data: Any) -> Dict[str, Any]:
        accession = protein_data.get("primary_accession")
        pdb_ids = protein_data.get("pdb_ids") or []
        
        if pdb_ids:
            primary_id = pdb_ids[0]
            source, url, verified = "RCSB_PDB", cls.PDB_BASE_URL.format(id=primary_id), True
        else:
            primary_id = accession
            source, url, verified = "ALPHAFOLD_DB", cls.ALPHAFOLD_BASE_URL.format(id=primary_id), False

        return {
            "accession": accession,
            "structure": {"id": primary_id, "source": source, "url": url, "is_verified": verified, "all_pdb_ids": pdb_ids},
            "annotations": {"residue_highlights": protein_data.get("binding_sites") or []},
            "metadata": {
                "name": protein_data.get("protein_name"),
                "organism": protein_data.get("organism"),
                "function": protein_data.get("function_text"),
                "confidence": protein_data.get("confidence_score"),
                "sequence": protein_data.get("sequence_text", "")
            }
        }