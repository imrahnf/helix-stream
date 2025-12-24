from fastapi import FastAPI, BackgroundTasks
import hashlib
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'libs', 'titan-sdk'))
from titan_client import TitanClient

app = FastAPI(title="HelixStream Gateway")

# Load config from .env
TITAN_HOST = os.getenv("TITAN_HOST", "localhost")
TITAN_PORT = int(os.getenv("TITAN_PORT", 6379))

@app.post("/analyze")
async def analyze_sequence(sequence: str, background_tasks: BackgroundTasks):
    # Generate SHA-256
    seq_hash = hashlib.sha256(sequence.encode()).hexdigest()
    
    # Check Cache 
    with TitanClient(host=TITAN_HOST, port=TITAN_PORT) as client:
        cached_result = client.get(seq_hash)
        if cached_result:
            return {"status": "CACHED", "hash": seq_hash, "data": cached_result}
        
        # Cache Miss: Queue task
        client.set(f"task:{seq_hash}", sequence)
    
    return {"status": "QUEUED", "hash": seq_hash, "message": "Sequence sent to cluster."}