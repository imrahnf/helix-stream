# services/gateway/main.py
from fastapi import FastAPI, HTTPException
import hashlib
from app.core.orchestrator import HelixOrchestrator

app = FastAPI(title="HelixStream Gateway")
orchestrator = HelixOrchestrator()

@app.post("/v1/analyze")
async def analyze_sequence(sequence: str):
    seq_hash = hashlib.sha256(sequence.encode()).hexdigest()
    result = await orchestrator.get_embedding(seq_hash)
    
    # Check if the Orchestrator returned an error
    if result["status"] == "error":
        raise HTTPException(status_code=503, detail=result["message"])

    return {
        "hash": seq_hash,
        "status": result["status"].upper(),
        "source": result.get("source"),
        "embedding": result.get("data")
    }

@app.get("/health")
def health_check():
    return {"status": "online", "plane": "Control_Gateway"}