# services/gateway/main.py
from fastapi import FastAPI, Query
from app.core.orchestrator import HelixOrchestrator

app = FastAPI(title="HelixStream Gateway")
orchestrator = HelixOrchestrator()

@app.post("/v1/ingest")
async def ingest_data(
    query: str = Query(..., description="UniProt Search Query (e.g., 'insulin AND human')"), 
    limit: int = 5,
    model_id: str = "esm2_t6_8M_UR50D"
):
    # Triggers the fetch > embed > tore pi0peline
    results = await orchestrator.ingest_from_uniprot(query, model_id, limit)
    return {"count": len(results), "results": results}

@app.post("/v1/search")
async def search_similar(
        sequence: str, 
        model_id: str = "esm2_t6_8M_UR50D", 
        limit: int = 5
    ):
    # Performs vector similarity search against the ingested knowledge base.
    return await orchestrator.search_similar(sequence, model_id, limit)