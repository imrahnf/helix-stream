# services/gateway/main.py
from fastapi import FastAPI, Query, HTTPException
from app.core.orchestrator import HelixOrchestrator

app = FastAPI(title="HelixStream Gateway")
orchestrator = HelixOrchestrator()

@app.post("/v1/ingest")
async def ingest_data(query: str = Query(...), limit: int = 5, model_id: str = "esm2_t6_8M_UR50D"):
    return await orchestrator.ingest_from_uniprot(query, model_id, limit)

@app.post("/v1/search")
async def search_similar(sequence: str, model_id: str = Query("esm2_t6_8M_UR50D"), limit: int = 5):
    return await orchestrator.search_similar(sequence, model_id, limit)

@app.get("/v1/structure/{accession}")
async def get_structure(accession: str, model_id: str = "esm2_t6_8M_UR50D"):
    manifest = await orchestrator.get_structure_data(accession, model_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Protein not found in local index.")
    return manifest

@app.get("/health")
def health_check():
    return {"status": "HEALTHY", "mode": "Hybrid-Mac-Distributed"}