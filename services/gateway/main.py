# services/gateway/main.py
import hashlib
from fastapi import FastAPI, HTTPException, Query
from app.core.orchestrator import HelixOrchestrator

app = FastAPI(title="HelixStream Gateway")
orchestrator = HelixOrchestrator()

@app.post("/v1/analyze")
async def analyze_sequence(
        sequence: str, 
        model_id: str = Query("esm2_t6_8M_UR50D", description="Model ID to use for inference")
    ):
    result = await orchestrator.analyze_sequence(sequence, model_id)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=503, detail=result.get("message"))

    return {
        "hash": result.get("hash") or result.get("sequence_hash"),
        "status": result["status"].upper(),
        "source": result.get("source"),
        "model_version": result.get("model"),
        "embedding": result.get("data")
    }

@app.get("/health")
def health_check():
    status = "HEALTHY" if orchestrator.is_remote_healthy else "DEGRADED (Local Only)"
    return {
        "status": status,
        "remote_node": orchestrator.host,
        "plane": "Control_Gateway"
    }