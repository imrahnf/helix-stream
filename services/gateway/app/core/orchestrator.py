# services/gateway/app/core/orchestrator.py
import sys
import os
import grpc
import logging

current_dir = os.path.dirname(os.path.abspath(__file__))
gen_path = os.path.normpath(os.path.join(current_dir, "../../gen"))
sys.path.append(gen_path)

try:
    import cache_pb2
    import cache_pb2_grpc
except ImportError:
    logging.error(f"Could not find gRPC stubs in {gen_path}")
    raise

class HelixOrchestrator:
    def __init__(self, host=os.getenv("TITAN_CACHE_HOST", "localhost"), port="9090"):
        # Initialize the gRPC connection to the Java Memory Engine
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = cache_pb2_grpc.CacheServiceStub(self.channel)
        logging.info(f"Connected to TitanCache gRPC on {host}:{port}")

    async def get_embedding(self, seq_hash: str):
        try:
            request = cache_pb2.KeyRequest(key=seq_hash)
            response = self.stub.Get(request)
            
            if response.found:
                return {"status": "hit", "source": "L1_TITAN_CACHE", "data": response.value}
            
            self.stub.SubmitTask(cache_pb2.KeyRequest(key=seq_hash)) 
            return {"status": "pending", "message": "Task queued for GPU workers"}
                
        except grpc.RpcError as e:
            logging.error(f"gRPC Communication Error: {e.code()} - {e.details()}")
            return {"status": "error", "message": "Memory Engine Unreachable"}