# $env:MODEL_ID="esm2_t33_650M_UR50D"; $env:TITAN_CACHE_HOST="localhost"; python services/workers/inference_worker.py
# services/workers/inference_worker.py
import os, sys, logging, json, torch, time, grpc, atexit
from concurrent import futures
from transformers import AutoTokenizer, AutoModelForMaskedLM

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'gateway'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'gateway', 'gen'))

import gen.cache_pb2 as cache_pb2
import gen.cache_pb2_grpc as cache_pb2_grpc

class HealthServicer(cache_pb2_grpc.HealthServicer):
    def Check(self, request, context):
        return cache_pb2.HealthCheckResponse(status=cache_pb2.HealthCheckResponse.SERVING)

class HelixWorker:
    def __init__(self):
        self.model_id = os.getenv("MODEL_ID", "esm2_t33_650M_UR50D")
        self.local_model_name = f"facebook/{self.model_id}"
        logging.info(f"--- STARTING GPU WORKER: {self.model_id} ---")
        
        logging.info("Loading tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.local_model_name)
        logging.info("Tokenizer loaded.")
        
        logging.info("Loading model...")
        self.model = AutoModelForMaskedLM.from_pretrained(self.local_model_name)
        logging.info("Model loaded.")
        
        self.model.eval()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        host = os.getenv("TITAN_CACHE_HOST", "localhost")
        port = os.getenv("TITAN_CACHE_PORT", "9090")
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = cache_pb2_grpc.CacheServiceStub(self.channel)
        
        atexit.register(self.cleanup)

    def cleanup(self):
        logging.info("Closing gRPC channel...")
        self.channel.close()

    def _calculate_confidence(self, logits, hidden_states):
        probs = torch.softmax(logits, dim=-1)
        entropy = -torch.sum(probs * torch.log(probs + 1e-10), dim=-1)
        normalized_entropy = 1.0 - (entropy / torch.log(torch.tensor(20.0)))  # 20 tokens
        return float(normalized_entropy.mean().item())

    def _poll_and_process(self):
        try:
            lease_req = cache_pb2.LeaseRequest(target_model_id=self.model_id, max_batch_size=1)
            response = self.stub.LeaseTasks(lease_req)
            if not response.tasks: return

            for task in response.tasks:
                logging.info(f"Computing: {task.hash}")
                clean_seq = task.sequence.upper().replace(" ", "")[:1022]
                inputs = self.tokenizer(clean_seq, return_tensors="pt").to(self.device)
                
                with torch.no_grad():
                    outputs = self.model(**inputs, output_hidden_states=True)
                    embeddings = outputs.hidden_states[-1].mean(dim=1)
                    normalized = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                    vector = normalized.tolist()[0]
                    confidence = self._calculate_confidence(outputs.logits, outputs.hidden_states)
                
                entry = cache_pb2.BatchResult.Entry(
                    key=task.hash, 
                    embedding_json=json.dumps(vector), 
                    confidence_score=confidence
                )
                self.stub.SubmitBatch(cache_pb2.BatchResult(results=[entry], model_id=self.model_id))
        except Exception as e:
            logging.error(f"Inference Loop Error: {e}")

    def run(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        cache_pb2_grpc.add_HealthServicer_to_server(HealthServicer(), server)
        worker_port = os.getenv("WORKER_PORT", "50051")
        server.add_insecure_port(f'0.0.0.0:{worker_port}') 
        server.start()
        while True:
            self._poll_and_process()
            time.sleep(0.5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    HelixWorker().run()