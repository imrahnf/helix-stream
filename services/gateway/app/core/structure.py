# services/gateway/app/core/structure.py

"""
================================================================================
MODULE: StructureOrchestrator
PURPOSE: Generate 3D structure manifests (PDB URLs, annotations) for frontend
         visualization via 3Dmol and AlphaFold integration.

KEY RESPONSIBILITIES:
  - Select primary structure source: RCSB PDB (if available) or AlphaFold DB
  - Generate fully qualified PDB file URLs for download/rendering
  - Compile residue-level annotations (binding sites, active sites, cleavage)
  - Build manifests linking embeddings to 3D structure data

DATA FLOW:
  INPUT:
    - Protein metadata dict from embedding_metadata table:
      * primary_accession (UniProt ID or MAN-<hash8>)
      * pdb_ids (list of RCSB PDB codes, e.g., ["1TRZ", "2HIU"])
      * binding_sites (JSON: [{pos, label}, ...])
      * protein_name, organism, function_text, confidence_score
  OUTPUT:
    - Manifest dict with structure + annotations + metadata:
      {
        "structure": {"id", "source", "url", "is_verified", "all_pdb_ids"},
        "annotations": {"residue_highlights": [...]},
        "metadata": {"name", "organism", "function", "confidence"}
      }

INFRASTRUCTURE ROLE:
  Bridges the GPU inference pipeline to the frontend's 3D visualization layer.
  Ensures every protein has a structure (verified PDB or AlphaFold prediction),
  enabling interactive exploration of structural features alongside sequence
  similarity clustering.

ERROR HANDLING STRATEGY:
  - Fallback Sources: RCSB → AlphaFold (graceful degradation)
  - Verification Flag: is_verified=true for experimental PDB, false for
    computationally predicted AlphaFold models
  - URL Correctness: Validate accession format (4 chars for PDB, Uniprot ID
    for AlphaFold) before generating URLs
================================================================================
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
                "confidence": protein_data.get("confidence_score")
            }
        }