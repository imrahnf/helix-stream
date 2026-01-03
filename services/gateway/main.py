# services/gateway/main.py
from fastapi import FastAPI, Query, HTTPException, Body, UploadFile, File
from app.core.orchestrator import HelixOrchestrator
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Optional

app = FastAPI(title="HelixStream Gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = HelixOrchestrator()

@app.post("/v1/ingest")
async def ingest_data(
    query: Optional[str] = Query(None), 
    sequence: Optional[str] = Body(None, embed=True),
    limit: int = 5, 
    model_id: str = "esm2_t6_8M_UR50D"
):
    # Direct Sequence Paste
    if sequence and len(sequence) > 10:
        return await orchestrator.ingest_manual_sequence(sequence, model_id)
    
    # UniProt Search
    if query:
        return await orchestrator.ingest_from_uniprot(query, model_id, limit)
        
    raise HTTPException(status_code=400, detail="Must provide 'query' or 'sequence'")

@app.post("/v1/search")
async def search_similar(
    payload: Dict[str, str] = Body(...), 
    model_id: str = Query("esm2_t6_8M_UR50D"), 
    limit: int = 5
):
    sequence = payload.get("sequence")
    if not sequence:
        raise HTTPException(status_code=422, detail="Missing 'sequence'")
    return await orchestrator.search_similar(sequence, model_id, limit)

@app.get("/v1/structure/{accession}")
async def get_structure(accession: str, model_id: str = Query("esm2_t6_8M_UR50D")): 
    manifest = await orchestrator.get_structure_data(accession, model_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Protein not found")
    return manifest

@app.get("/v1/embeddings")
async def get_all_embeddings(limit: int = 100):
    from app.db.repository import DatabaseContext
    with DatabaseContext(orchestrator.db_url) as repo:
        return repo.get_all_summaries(limit)

@app.post("/v1/ingest/bulk")
async def bulk_ingest(file: UploadFile = File(...), model_id: str = "esm2_t6_8M_UR50D"):
    content = (await file.read()).decode("utf-8")
    entries = content.split(">")[1:] 
    results = []
    for entry in entries:
        lines = entry.strip().split("\n")
        sequence = "".join(lines[1:])
        res = await orchestrator.ingest_manual_sequence(sequence, model_id)
        results.append({"status": res[0]["status"]})
    return {"total": len(results), "summary": results}