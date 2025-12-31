import os
import sys
import grpc
import logging
import hashlib
import asyncio
import torch
from transformers import AutoTokenizer, AutoModelForMaskedLM
import json

from app.db.repository import DatabaseContext

import cache_pb2
import cache_pb2_grpc

class HelixOrchestrator:
    def __init__(self):
        self.host = os.getenv("TITAN_IP", os.getenv("TITAN_CACHE_HOST", "localhost"))
        self.port = "9090"
        self.health_port = "50051"
        self.db_url = os.getenv("DATABASE_URL")
        
        # Setup gRPC channels
        self.channel = grpc.insecure_channel(f"{self.host}:{self.port}")
        self.stub = cache_pb2_grpc.CacheServiceStub(self.channel)

        self.health_channel = grpc.insecure_channel(f"{self.host}:{self.health_port}")
        self.health_stub = cache_pb2_grpc.HealthStub(self.health_channel)
        
        # Status/background task
        self.is_remote_healthy = False
        
        try:
            asyncio.create_task(self._monitor_health()) 
        except RuntimeError:
            pass

        self.local_model = None
        self.local_tokenizer = None
        self.local_model_name = "facebook/esm2_t6_8M_UR50D"

    async def _monitor_health(self):
        while True:
            try:
                response = self.health_stub.Check(
                    cache_pb2.HealthCheckRequest(service=""), 
                    timeout=2.0
                )
                was_unhealthy = not self.is_remote_healthy
                self.is_remote_healthy = (response.status == 1)
                
                if was_unhealthy and self.is_remote_healthy:
                    logging.info(">>> Windows Compute Node RECOVERED. Resuming high-accuracy inference.")
                    
            except Exception:
                if self.is_remote_healthy:
                    logging.warning("!!! Windows Compute Node OFFLINE. Switching to local fallback.")
                self.is_remote_healthy = False
            
            await asyncio.sleep(5)

    def _load_local_model(self):
        if self.local_model is None:
            logging.info(f"Loading Fallback Model: {self.local_model_name}")
            self.local_tokenizer = AutoTokenizer.from_pretrained(self.local_model_name)
            self.local_model = AutoModelForMaskedLM.from_pretrained(self.local_model_name)
            self.local_model.eval()

    async def _process_locally(self, sequence, seq_hash, model_id):
        self._load_local_model()
        
        inputs = self.local_tokenizer(sequence, return_tensors="pt")
        with torch.no_grad():
            outputs = self.local_model(**inputs, output_hidden_states=True)
            embedding = outputs.hidden_states[-1].mean(dim=1).tolist()[0]
            
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)
            token_ids = inputs["input_ids"]
            token_probs = torch.gather(probs, dim=-1, index=token_ids.unsqueeze(-1)).squeeze(-1)
            confidence = token_probs.mean().item()

        # Update DB
        with DatabaseContext(self.db_url) as repo:
            repo.store_embedding(
                seq_hash, 
                model_id, 
                embedding, 
                confidence, 
                is_fallback=True 
            )
            repo.update_job_status(seq_hash, model_id, 'COMPLETED')

        return {
            "hash": seq_hash,
            "status": "COMPLETED",
            "source": "LOCAL_FALLBACK",
            "model": self.local_model_name,
            "data": embedding, 
            "confidence": confidence
        }

    def _generate_hash(self, sequence: str) -> str:
        return hashlib.sha256(sequence.encode()).hexdigest()

    async def analyze_sequence(self, sequence: str, model_id: str):
        seq_hash = self._generate_hash(sequence)
        
        # Circuit Breaker
        if not self.is_remote_healthy:
            fallback_model = "esm2_t6_8M_UR50D"
            return await self._process_locally(sequence, seq_hash, fallback_model)

        # Check L1 TitanCache
        try:
            request = cache_pb2.KeyRequest(key=seq_hash, model_id=model_id)
            response = self.stub.Get(request)
            
            if response.found:
                vector_data = json.loads(response.value)
                
                with DatabaseContext(self.db_url) as repo:
                    if not repo.get_embedding(seq_hash, model_id):
                        repo.store_embedding(
                            seq_hash, 
                            model_id, 
                            vector_data, 
                            response.confidence_score,
                            is_fallback=False
                        )
                    repo.update_job_status(seq_hash, model_id, 'COMPLETED')
                
                return {
                    "hash": seq_hash,
                    "status": "COMPLETED",
                    "source": "L1_CACHE",
                    "model": response.model_id,
                    "data": vector_data,
                    "confidence": response.confidence_score
                }
        except grpc.RpcError as e:
            logging.error(f"L1 Connection Failed: {e}")

        # Check L2 (Postgres)
        with DatabaseContext(self.db_url) as repo:
            record = repo.get_embedding(seq_hash, model_id)
            if record:
                return {
                    "hash": seq_hash,
                    "status": "COMPLETED", 
                    "source": "L2_STORE", 
                    "model": model_id,
                    "data": record['raw_json'] 
                }
            
            status = repo.get_job_status(seq_hash, model_id)
            if status:
                return {
                    "hash": seq_hash,
                    "status": status, 
                    "source": "JOB_QUEUE", 
                    "model": model_id
                }
            
            # Create New Job
            repo.create_job(seq_hash, model_id, compute_node="WINDOWS_GPU")
            
            try:
                self.stub.SubmitTask(cache_pb2.Task(hash=seq_hash, sequence=sequence, model_id=model_id))
            except grpc.RpcError:
                logging.error("Failed to submit task to TitanCache")

            return {
                "hash": seq_hash,
                "status": "PENDING", 
                "source": "NEW_JOB", 
                "model": model_id
            }