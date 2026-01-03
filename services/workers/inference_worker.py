# services/workers/inference_worker.py
import os, time, grpc, logging, json, torch
from concurrent import futures
from transformers import AutoTokenizer, AutoModelForMaskedLM
import gen.cache_pb2 as cache_pb2
import gen.cache_pb2_grpc as cache_pb2_grpc

class HealthServicer(cache_pb2_grpc.HealthServicer):
    def Check(self, request, context):
        logging.info("Health Probe Received: SERVING")
        return cache_pb2.HealthCheckResponse(status=cache_pb2.HealthCheckResponse.SERVING)

class HelixWorker:
    def __init__(self):
        self.model_id = os.getenv("MODEL_ID", "esm2_t33_650M_UR50D")
        self.local_model_name = f"facebook/{self.model_id}"
        
        logging.info(f"--- STARTING GPU WORKER: {self.model_id} ---")

        self.tokenizer = AutoTokenizer.from_pretrained(self.local_model_name)
        self.model = AutoModelForMaskedLM.from_pretrained(self.local_model_name)
        self.model.eval()

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        host = os.getenv("TITAN_CACHE_HOST", "localhost")
        self.channel = grpc.insecure_channel(f"{host}:9090")
        self.stub = cache_pb2_grpc.CacheServiceStub(self.channel)
        logging.info(f"Worker Ready. Device: {self.device}")

    def run(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        cache_pb2_grpc.add_HealthServicer_to_server(HealthServicer(), server)
        server.add_insecure_port('0.0.0.0:50051') 
        server.start()
        logging.info("Health Server listening on 0.0.0.0:50051")

    def _poll_and_process(self):
        lease_req = cache_pb2.LeaseRequest(target_model_id=self.model_id, max_batch_size=1)
        response = self.stub.LeaseTasks(lease_req)
        if not response.tasks: return

        for task in response.tasks:
            logging.info(f"Computing Embedding: {task.hash}")
            clean_seq = task.sequence.upper().replace(" ", "")[:1022]
            inputs = self.tokenizer(clean_seq, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs, output_hidden_states=True)
                vector = outputs.hidden_states[-1].mean(dim=1).tolist()[0]
            
            entry = cache_pb2.BatchResult.Entry(
                key=task.hash, 
                embedding_json=json.dumps(vector), 
                confidence_score=1.0
            )
            self.stub.SubmitBatch(cache_pb2.BatchResult(results=[entry], model_id=self.model_id))
            logging.info(f"Task {task.hash} Resolved.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    HelixWorker().run()