"""
File Overview: Graph-focused service wrapping layout computation and neighbor retrieval for HelixStream proteins.
Responsibilities:
- Fetch precomputed neighbors for an accession/model or return placeholder messaging when absent.
- Compute or re-compute 3D layout positions using ProjectionEngine and persist them.
- Initialize graph data by generating positions and precomputing neighbor edges.
Data Flow:
- Inputs: accession, model_id, limit, method, force_recompute flags; repository for DB access.
- Outputs: neighbor lists/status payloads; stored graph_positions and graph_edges rows; timing info in responses.
System Integration:
- Invokes ProjectionEngine (UMAP) and repository graph helpers; consumed by FastAPI endpoints serving graph data.
Technical Details:
- Guards against redundant layout work unless force_recompute=true; handles JSON vectors; converts vectors to numpy arrays.
Future Considerations:
- Add progress callbacks/streaming for long runs and pagination for large neighbor sets.
"""

import time
import numpy as np
import logging
import json
from typing import Dict

logger = logging.getLogger(__name__)

# Handles graph layout computation and neighbor relationships
class GraphService:
    
    def __init__(self, repository):
        self.repo = repository
    
    def get_neighbors(self, accession: str, model_id: str, limit: int = 10) -> Dict:
        neighbors = self.repo.get_precomputed_neighbors(accession, model_id, limit)
        
        if not neighbors:
            protein = self.repo.get_embedding_by_accession(accession, model_id)
            if not protein:
                return None
            return {"accession": accession, "neighbors": [], "message": "Neighbors not yet computed"}
        
        return {"accession": accession, "neighbors": neighbors}
    
    def compute_layout(self, model_id: str, method: str = "umap", force_recompute: bool = False) -> Dict:
        from app.core.projection import ProjectionEngine
        
        start_time = time.time()
        
        if not force_recompute:
            existing_count = self.repo.check_positions_exist(model_id, method)
            if existing_count > 0:
                return {
                    "status": "already_computed",
                    "computed": existing_count,
                    "method": method,
                    "message": "Positions already exist. Use force_recompute=true"
                }
        
        data = self.repo.get_all_summaries(limit=10000)
        if not data:
            return {"error": f"No proteins found for model {model_id}"}
        
        filtered = [d for d in data if d.get('model_id') == model_id]
        if not filtered:
            return {"error": f"No proteins found for model {model_id}"}
        
        vectors = [item['vector'] for item in filtered if item.get('vector')]
        accessions = [item['primary_accession'] for item in filtered if item.get('vector')]
        
        if not vectors:
            return {"error": "No valid vectors found"}
        
        vectors_array = np.array(vectors, dtype=np.float32)
        positions_3d = ProjectionEngine.compute_umap_3d(vectors_array)
        stored_count = ProjectionEngine.store_positions(self.repo, accessions, positions_3d, model_id, method)
        
        return {
            "status": "success",
            "computed": stored_count,
            "method": method,
            "duration_seconds": round(time.time() - start_time, 2),
            "message": f"3D positions computed for {stored_count} proteins"
        }
    
    def initialize_graph_data(self, model_id: str) -> Dict:
        from app.core.projection import ProjectionEngine
        
        logger.info("Computing 3D positions...")
        data = self.repo.get_all_summaries(limit=10000)
        filtered = [d for d in data if d.get('model_id') == model_id and d.get('vector')]
        
        if not filtered:
            return {"error": "No proteins found"}
        
        # UMAP requires at least 4 samples
        if len(filtered) < 4:
            logger.warning(f"Only {len(filtered)} proteins found - UMAP requires at least 4 samples")
            return {
                "error": f"Insufficient data: {len(filtered)} proteins (need >= 4 for UMAP)",
                "proteins_found": len(filtered)
            }
        
        vectors = []
        for d in filtered:
            vec = d['vector']
            if isinstance(vec, str):
                vec = json.loads(vec)
            vectors.append(vec)
        
        vectors = np.array(vectors, dtype=np.float32)
        accessions = [d['primary_accession'] for d in filtered]
        
        try:
            positions_3d = ProjectionEngine.compute_umap_3d(vectors)
            ProjectionEngine.store_positions(self.repo, accessions, positions_3d, model_id, 'umap')
            logger.info(f"✓ Computed 3D positions for {len(accessions)} proteins")
            
            logger.info("Computing graph edges...")
            edge_count = self.repo.precompute_all_neighbors(model_id, k=10)
            logger.info(f"✓ Graph initialization complete: {edge_count} edges")
            
            return {"positions": len(accessions), "edges": edge_count}
        except Exception as e:
            logger.error(f"Graph computation failed: {e}", exc_info=True)
            return {"error": str(e), "proteins_attempted": len(filtered)}
