# services/gateway/app/core/orchestrator.py
import os
import sys
import grpc
import logging
import hashlib

from app.db.repository import DatabaseContext

import cache_pb2
import cache_pb2_grpc

class HelixOrchestrator:
    def __init__(self):
            host = os.getenv("TITAN_CACHE_HOST", "localhost")
            port = "9090"
            self.db_url = os.getenv("DATABASE_URL")
            
            # Connect to TitanCache
            self.channel = grpc.insecure_channel(f"{host}:{port}")
            self.stub = cache_pb2_grpc.CacheServiceStub(self.channel)

    def _generate_hash(self, sequence: str) -> str:
        return hashlib.sha256(sequence.encode()).hexdigest()

    async def analyze_sequence(self, sequence: str, model_id: str):
        seq_hash = self._generate_hash(sequence)
        
        # Fetch from L1 cache (TitanCache)
        try:
            request = cache_pb2.KeyRequest(key=seq_hash, model_id=model_id)
            response = self.stub.Get(request)
            
            if response.found:
                with DatabaseContext(self.db_url) as repo:
                    if not repo.get_embedding(seq_hash, model_id):
                        repo.store_embedding(
                            seq_hash, 
                            model_id,
                            response.value,
                            response.confidence_score
                        )
                    repo.update_job_status(seq_hash, model_id, 'COMPLETED')
                return {
                    "hash" : seq_hash,
                    "status" : "COMPLETED",
                    "source" : "L1_CACHE",
                    "model" : response.model_id,
                    "data" : response.value,
                    "confidence": response.confidence_score
                }
        except grpc.RpcError as e:
            print(f"L1 Cache Unavailables: {e}")
        
        # L2 DB (Postgres)
        with DatabaseContext(self.db_url) as repo:
            # Check for existing data
            record = repo.get_embedding(seq_hash, model_id)
            if record:
                # Populate L1 from L2
                try:
                    entry = cache_pb2.BatchResult.Entry(
                        key=seq_hash,
                        embedding_json=record['vector']
                    )
                    result_payload = cache_pb2.BatchResult(
                        results=[entry],
                        model_id=model_id
                    )
                    self.stub.SubmitBatch(result_payload)
                except grpc.RpcError as e:
                    logging.log(f"Failed to cache L1: {e}")
                return {
                    "hash" : seq_hash,
                    "status": "COMPLETED", 
                    "source": "L2_STORE", 
                    "model": model_id,
                    "data": record['vector']
                }
            
            # Check for pending job
            status = repo.get_job_status(seq_hash, model_id)
            if status:
                return {
                    "hash" : seq_hash,
                    "status": status, 
                    "source": "JOB_QUEUE", 
                    "model": model_id
                }
            
            # Trigger New Work
            repo.create_job(seq_hash, model_id)
            
            try:
                self.stub.SubmitTask(cache_pb2.Task(
                    hash=seq_hash, 
                    sequence=sequence, 
                    model_id=model_id
                ))
            except grpc.RpcError:
                logging.error("Failed to submit task to TitanCache")

            return {
                "hash" : seq_hash,
                "status": "PENDING", 
                "source": "NEW_JOB", 
                "model": model_id
            }