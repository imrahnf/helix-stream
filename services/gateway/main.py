# services/gateway/main.py
from fastapi import FastAPI, Query, HTTPException, Body
from app.core.orchestrator import HelixOrchestrator
from typing import Dict

app = FastAPI(title="HelixStream Gateway")
orchestrator = HelixOrchestrator()

@app.post("/v1/ingest")
async def ingest_data(query: str = Query(...), limit: int = 5, model_id: str = "esm2_t6_8M_UR50D"):
    return await orchestrator.ingest_from_uniprot(query, model_id, limit)

@app.post("/v1/search")
async def search_similar(
    payload: Dict[str, str] = Body(...), 
    model_id: str = Query("esm2_t6_8M_UR50D"), 
    limit: int = 5
):
    sequence = payload.get("sequence")
    if not sequence:
        raise HTTPException(status_code=422, detail="Missing 'sequence' field")
    
    # Dimension Guard
    expected_dim = 1280 if "650M" in model_id else 320
    try:
        results = await orchestrator.search_similar(sequence, model_id, limit)
        return results
    except Exception as e:
        print(f"Search Crash: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/v1/structure/{accession}")
async def get_structure(accession: str, model_id: str = Query("esm2_t6_8M_UR50D")): 
    manifest = await orchestrator.get_structure_data(accession, model_id)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Protein {accession} not found in {model_id} index.")
    return manifest

@app.get("/health")
def health_check():
    return {"status": "HEALTHY", "mode": "Hybrid-Mac-Distributed"}