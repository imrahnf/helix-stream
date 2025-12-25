import sys
import os

# This adds the 'gen' directory to your Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'gen'))

import grpc
import cache_pb2
import cache_pb2_grpc

class HelixOrchestrator:
    def __init__(self):
        # Connect to Java Memory Engine
        self.channel = grpc.insecure_channel('localhost:9090')
        self.cache_stub = cache_pb2_grpc.CacheServiceStub(self.channel)

    def analyze_sequence(self, sequence: str):
        # 1. Fingerprint
        seq_hash = generate_sha256(sequence)

        # 2. L1 Check (Sync gRPC to Java)
        cache_resp = self.cache_stub.Get(cache_pb2.KeyRequest(key=seq_hash))
        if cache_resp.found:
            return {"status": "hit", "source": "L1_TITAN", "data": cache_resp.value}

        # 3. L2 Check (Sync Postgres)
        db_record = postgres_client.get_by_hash(seq_hash)
        if db_record and db_record.embedding:
            # Update L1 for next time
            self.cache_stub.Put(cache_pb2.CacheEntry(key=seq_hash, value=str(db_record.embedding)))
            return {"status": "hit", "source": "L2_PG", "data": db_record.embedding}

        # 4. Miss - Trigger Async Inference
        # (This is where Phase 3 begins)
        return {"status": "pending", "task_id": seq_hash}