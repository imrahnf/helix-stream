# services/workers/inference_worker.py
import os
import time
import grpc
import logging
import json
from concurrent import futures
import torch
from transformers import AutoTokenizer, AutoModelForMaskedLM # CHANGED CLASS

import cache_pb2
import cache_pb2_grpc

class HealthServicer(cache_pb2_grpc.HealthServicer):
    def Check(self, request, context):
        return cache_pb2.HealthCheckResponse(status=cache_pb2.HealthCheckResponse.SERVING)

class HelixWorker:
    def __init__(self):
        host = os.getenv("TITAN_CACHE_HOST", "localhost")
        port = "9090"
        
        # Dynamitcally pull model from env (but default to the 8M model)
        self.model_id = os.getenv("MODEL_ID", "esm2_t6_8M_UR50D")
        self.local_model_name = "facebook/esm2_t6_8M_UR50D"

        # gRPC init
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = cache_pb2_grpc.CacheServiceStub(self.channel)
        
        logging.info(f"Loading Model: {self.local_model_name}...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.local_model_name)
        self.model = AutoModelForMaskedLM.from_pretrained(self.local_model_name)
        self.model.eval()
        logging.info("Worker Ready.")

    def run(self):
        # Start Health Server
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        cache_pb2_grpc.add_HealthServicer_to_server(HealthServicer(), server)
        server.add_insecure_port('[::]:50051')
        server.start()
        logging.info("Health Check server started on port 50051")
        logging.info("Starting inference loop")
        while True:
            try:
                self._poll_and_process()
            except grpc.RpcError as e:
                logging.error(f"gRPC Communication Error: {e.code()}")
            except Exception as e:
                logging.error(f"Worker Error: {e}")
            time.sleep(1)

    def _poll_and_process(self):
        lease_req = cache_pb2.LeaseRequest(
            target_model_id=self.model_id,
            max_batch_size=8
        )
        response = self.stub.LeaseTasks(lease_req)
        
        if not response.tasks:
            return

        sorted_tasks = sorted(response.tasks, key=lambda t: len(t.sequence))
        sequences = [t.sequence for t in sorted_tasks]
        
        logging.info(f"Processing bucket of {len(sequences)} sequences...")

        inputs = self.tokenizer(sequences, padding=True, return_tensors="pt")
        
        with torch.no_grad():
            outputs = self.model(**inputs, output_hidden_states=True)
            
            # Get Vector
            # hidden_states[-1] is the last layer
            embeddings = outputs.hidden_states[-1].mean(dim=1)
            
            # Get the Confidence
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)
            
            # Gather the probability of the ACTUAL input tokens
            token_ids = inputs["input_ids"]
            
            token_probs = torch.gather(probs, dim=-1, index=token_ids.unsqueeze(-1)).squeeze(-1)
            mask = inputs["attention_mask"]
            # Average probability
            seq_confidence = (token_probs * mask).sum(dim=1) / mask.sum(dim=1)

        batch_results = []
        for i, task in enumerate(sorted_tasks):
            vector = embeddings[i].tolist()
            # Convert single tensor value to float
            conf_score = seq_confidence[i].item() 
            
            entry = cache_pb2.BatchResult.Entry(
                key=task.hash,
                embedding_json=json.dumps(vector),
                confidence_score=conf_score
            )
            batch_results.append(entry)

        if batch_results:
            self.stub.SubmitBatch(cache_pb2.BatchResult(
                results=batch_results,
                model_id=self.model_id
            ))
            logging.info(f"Submitted batch of {len(batch_results)}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    worker = HelixWorker()
    worker.run()