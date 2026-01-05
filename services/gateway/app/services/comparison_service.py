"""
File Overview: Protein comparison service combining vector similarity, sequence alignment, and neighbor/structure context.
Responsibilities:
- Fetch protein metadata, compute cached vector similarity, and align sequences with BLOSUM62 scoring.
- Derive identity/similarity metrics, match-line visualization strings, and shared neighbor lists.
- Assemble comparison payloads including structural overlap hints and PDB listings.
Data Flow:
- Inputs: two accessions and model_id; repository for metadata/neighbors; relies on SimilarityService for vector similarity.
- Outputs: comparison dict with protein summaries, similarity metrics, alignment details, neighbors, and structure metadata.
System Integration:
- Used by FastAPI comparison endpoints; touches embedding_metadata, graph_edges, and cache-backed similarity computations.
Technical Details:
- Uses Biopython globalds alignment with gap penalties (-10 open, -0.5 extend); generates match_line for UI rendering.
- Calculates identity/similarity over aligned length; handles missing sequences by returning zeroed stats.
Future Considerations:
- Add length caps/streaming for very long sequences and incorporate structural superposition or RMSD comparisons.
"""

from typing import Dict, List, Optional
from Bio import pairwise2
from Bio.Align import substitution_matrices
from fastapi import HTTPException

from app.services.similarity_service import SimilarityService


# Comprehensive protein comparison service with sequence alignment
class ComparisonService:
    def __init__(self, repository):
        self.repo = repository
        self.similarity_service = SimilarityService(repository)
    
    def compare_detailed(self, acc1: str, acc2: str, model_id: str) -> Dict:
        # Fetch protein metadata
        protein1 = self.repo.get_embedding_by_accession(acc1, model_id)
        protein2 = self.repo.get_embedding_by_accession(acc2, model_id)
        
        if not protein1 or not protein2:
            raise HTTPException(status_code=404, detail="One or both proteins not found")
        
        # Vector similarity (from cache)
        sim_result = self.similarity_service.get_similarity(acc1, acc2, model_id)
        vector_similarity = sim_result['similarity']
        
        # Sequence alignment
        seq1 = protein1.get('sequence_text', '')
        seq2 = protein2.get('sequence_text', '')
        
        if seq1 and seq2:
            alignment_stats = self._compute_alignment(seq1, seq2)
        else:
            alignment_stats = {
                "identity": 0.0,
                "similarity": 0.0,
                "score": 0.0,
                "alignment": None
            }
        
        # Shared neighbors (functional similarity)
        neighbors1 = self.repo.get_precomputed_neighbors(acc1, model_id, 10)
        neighbors2 = self.repo.get_precomputed_neighbors(acc2, model_id, 10)
        shared = self._find_shared_neighbors(neighbors1, neighbors2)
        
        # Structural comparison metadata
        pdb1 = protein1.get('pdb_ids', [])
        pdb2 = protein2.get('pdb_ids', [])
        has_structures = len(pdb1) > 0 and len(pdb2) > 0
        
        return {
            "protein_a": self._format_protein_data(protein1),
            "protein_b": self._format_protein_data(protein2),
            "similarity": {
                "vector_similarity": vector_similarity,
                "sequence_identity": alignment_stats['identity'],
                "sequence_similarity": alignment_stats['similarity'],
                "alignment_score": alignment_stats['score']
            },
            "alignment": alignment_stats['alignment'],
            "shared_neighbors": shared,
            "structural_overlap": has_structures,
            "pdb_comparison": {
                "protein_a_pdbs": pdb1,
                "protein_b_pdbs": pdb2
            }
        }
    
    def _compute_alignment(self, seq1: str, seq2: str) -> Dict:
        # Perform pairwise sequence alignment using BLOSUM62 matrix. Returns exact matches, similarity, and alignment strings
        try:
            matrix = substitution_matrices.load("BLOSUM62")
            
            # Global alignment with gap penalties
            alignments = pairwise2.align.globalds(
                seq1, seq2, 
                matrix, 
                -10,   # Gap open penalty
                -0.5   # Gap extension penalty
            )
            
            if not alignments:
                return {
                    "identity": 0.0,
                    "similarity": 0.0,
                    "score": 0.0,
                    "alignment": None
                }
            
            # Get best alignment
            best = alignments[0]
            aligned1, aligned2, score, begin, end = best
            
            # Calculate exact matches
            matches = sum(1 for a, b in zip(aligned1, aligned2) if a == b and a != '-')
            total_length = len(aligned1)
            identity = matches / total_length if total_length > 0 else 0.0
            
            # Calculate similarity
            similar = sum(
                1 for a, b in zip(aligned1, aligned2)
                if a != '-' and b != '-' and matrix.get((a, b), -1) > 0
            )
            similarity = similar / total_length if total_length > 0 else 0.0
            
            # Generate match line for visualization
            match_line = "".join(
                '|' if a == b else ':' if (a != '-' and b != '-' and matrix.get((a, b), -1) > 0) else ' '
                for a, b in zip(aligned1, aligned2)
            )
            
            return {
                "identity": round(identity, 4),
                "similarity": round(similarity, 4),
                "score": round(score, 2),
                "alignment": {
                    "sequence_a": aligned1,
                    "sequence_b": aligned2,
                    "match_line": match_line,
                    "length": total_length
                }
            }
        except Exception as e:
            # If alignment fails, return zeros
            return {
                "identity": 0.0,
                "similarity": 0.0,
                "score": 0.0,
                "alignment": None,
                "error": str(e)
            }
    
    def _find_shared_neighbors(self, neighbors1: List, neighbors2: List) -> List[Dict]:
        # Find proteins that appear in both neighbor lists
        set1 = {n['primary_accession'] for n in neighbors1}
        set2 = {n['primary_accession'] for n in neighbors2}
        shared_accs = set1 & set2
        
        return [
            {
                "accession": acc,
                "name": next((n['protein_name'] for n in neighbors1 if n['primary_accession'] == acc), "Unknown")
            }
            for acc in shared_accs
        ]
    
    def _format_protein_data(self, protein: Dict) -> Dict:
        # Format protein data for comparison response
        return {
            "accession": protein.get('primary_accession', ''),
            "name": protein.get('protein_name', ''),
            "organism": protein.get('organism', ''),
            "function": protein.get('function_text', 'No functional annotation available'),
            "confidence": protein.get('confidence_score', 0.0),
            "is_fallback": protein.get('is_fallback', False),
            "sequence_length": len(protein.get('sequence_text', '')),
            "pdb_ids": protein.get('pdb_ids', [])
        }
