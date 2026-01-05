"""
File Overview: Thin service wrapper exposing similarity scores between protein accessions for HelixStream APIs.
Responsibilities:
- Delegate similarity retrieval to SimilarityCache and normalize response structure.
- Sort accession ordering for consistent cache keys and client responses.
Data Flow:
- Inputs: accession pair (acc1, acc2) and model_id plus repository for DB access (via cache).
- Outputs: dict containing accessions, rounded similarity score, cache-hit flag, and model_id.
System Integration:
- Consumed by FastAPI endpoints and ComparisonService; relies on cache.py logic that hits pgvector or DB cache.
Technical Details:
- Rounds similarity to 4 decimals and returns cached boolean without additional computation.
Future Considerations:
- Surface cache stats/reset controls and extend to batch similarity queries.
"""

# Transitioning to comparison_service.py

from typing import Dict
from app.core.cache import SimilarityCache

class SimilarityService:
    
    def __init__(self, repository):
        self.repo = repository
    
    def get_similarity(self, acc1: str, acc2: str, model_id: str) -> Dict:
        similarity, cached = SimilarityCache.get_similarity(self.repo, acc1, acc2, model_id)
        protein_a, protein_b = sorted([acc1, acc2])
        
        return {
            "protein_a": protein_a,
            "protein_b": protein_b,
            "similarity": round(similarity, 4),
            "cached": cached,
            "model_id": model_id
        }