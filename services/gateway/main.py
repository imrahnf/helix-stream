# services/gateway/main.py
from fastapi import FastAPI, Query
from app.core.orchestrator import HelixOrchestrator

app = FastAPI(title="HelixStream Gateway (Decoupled)")
orchestrator = HelixOrchestrator()

@app.post("/v1/analyze")
async def analyze_sequence(sequence: str, model_id: str = Query("esm2_t6_8M_UR50D")):
    result = await orchestrator.analyze_sequence(sequence, model_id)
    return {
        "hash": result.get("hash"),
        "status": result["status"],
        "model": result.get("model"),
        "embedding": result.get("data"),
        "confidence": result.get("confidence")
    }

@app.get("/health")
def health_check():
    return {
        "status": "HEALTHY",
        "remote_node": orchestrator.host,
        "mode": "Decoupled_Local_Inference"
    }