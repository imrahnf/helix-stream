from fastapi import FastAPI, HTTPException
import hashlib
from app.core.orchestrator import HelixOrchestrator

app = FastAPI(title="HelixStream Gateway")
orchestrator = HelixOrchestrator()

@app.post("/v1/analyze")
async def analyze_sequence(sequence: str):
    seq_hash = hashlib.sha256(sequence.encode()).hexdigest()
    
    # The Orchestrator will generate the hash internally
    result = await orchestrator.analyze_sequence(sequence)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=503, detail=result.get("message"))

    return {
        "hash": seq_hash,
        "status": result["status"].upper(),
        "source": result.get("source"),
        "model_version": result.get("model"), # New field
        "embedding": result.get("data")
    }

@app.get("/health")
def health_check():
    return {"status": "online", "plane": "Control_Gateway"}