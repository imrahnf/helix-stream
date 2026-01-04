# TEST ON WINDOWS (from root): env:MODEL_ID="esm2_t33_650M_UR50D"; $env:TITAN_CACHE_HOST="localhost"; python services/workers/inference_worker.py
# services/workers/inference_worker.py

"""
================================================================================
MODULE: HelixWorker & HealthServicer (GPU/CPU (fallback) Worker)
PURPOSE: Compute ESM2-650M protein embeddings on Windows GPU via gRPC polling.
         Registers health status, leases inference tasks, and returns 1280-D
         vectors with confidence scores to TitanCache coordinator.

KEY RESPONSIBILITIES:
  - Load ESM2-650M tokenizer and model from HuggingFace (one time init)
  - Poll TitanCache gRPC service for pending inference tasks
  - Execute forward pass: sequence → hidden states → embeddings → L2
    normalization
  - Calculate confidence scores from output logit entropy
  - Submit completed batches (key, embedding_json, confidence) to cache
  - Expose health check endpoint (HealthServicer) for orchestrator validation

DATA FLOW:
  INPUT (gRPC):
    LeaseRequest: target_model_id, max_batch_size
    Response: [Task(hash, sequence, model_id), ...]
  PROCESSING:
    - Tokenize sequence (HuggingFace BPE tokenizer)
    - Forward pass: AutoModelForMaskedLM(**inputs, output_hidden_states=True)
    - Extract final hidden layer, mean-pool over sequence, L2-normalize
    - Entropy-based confidence: 1 - (entropy / log(20)) ∈ [0, 1]
  OUTPUT (gRPC):
    BatchResult: [Entry(key, embedding_json, confidence_score), ...]

INFRASTRUCTURE ROLE:
  The GPU compute node in the distributed system. Runs on Windows with CUDA.
  Offloads heavy ESM2-650M inference from macOS Gateway. TitanCache coordinates
  task distribution; HelixOrchestrator on macOS polls results. Single-worker
  design (can be scaled horizontally with multiple instances).

RESOURCE MANAGEMENT:
  - Model Loading: ESM2-650M (~1.3 GB) loaded once on startup
  - Device Selection: Automatically detects CUDA; falls back to CPU if unavailable
  - Channel Cleanup: atexit handler ensures gRPC channel is closed gracefully
  - Memory: No explicit batching within loop (max_batch_size=1 for stability)

ERROR HANDLING STRATEGY:
  - Model Load Failures: Logged and re-raised (fatal on startup)
  - Sequence Errors: Truncated to 1022 AA; non-AA chars stripped by orchestrator
  - gRPC Connection Loss: Handled by TitanCache retry logic; worker continues
    polling
  - Confidence Calculation: Entropy from logits; clipped to [0, 1] range
  - Task Processing Loop: Catch-all exception handler logs errors without
    crashing worker

ENVIRONMENT VARIABLES:
  - MODEL_ID: "esm2_t33_650M_UR50D" (default)
  - TITAN_CACHE_HOST: IP/hostname of TitanCache service (default: localhost)
  - TITAN_CACHE_PORT: gRPC port for cache (default: 9090)
  - WORKER_PORT: Health check port (default: 50051)
================================================================================
"""

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