# apps/api/main.py
from fastapi import FastAPI, BackgroundTasks
import hashlib
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'libs', 'titan-sdk'))
from titan_client import TitanClient

app = FastAPI(title="HelixStream Gateway")

# Load .env config 
TITAN_HOST = os.getenv("TITAN_HOST", "localhost")
TITAN_PORT = int(os.getenv("TITAN_PORT", 6379))

@app.post("/analyze")
async def analyze_sequence(sequence: str):
    seq_hash = hashlib.sha256(sequence.encode()).hexdigest()
    
    with TitanClient(host=TITAN_HOST, port=TITAN_PORT) as client:
        cached_val = client.get(seq_hash)
        
        if cached_val and cached_val != "null":
            return {"status": "CACHED", "hash": seq_hash, "data": cached_val}

        # Handl;e MISS
        # Queue the task for the worker to find later
        print(f"Cache Miss- Queuing task:{seq_hash[:8]}")
        client.set(f"task:{seq_hash}", sequence)
    
    return {"status": "QUEUED", "hash": seq_hash}