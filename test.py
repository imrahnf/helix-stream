import asyncio
import httpx
import hashlib
import time
from collections import Counter

# Configuration
GATEWAY_URL = "http://localhost:8000/v1/analyze"
TOTAL_BURST = 200  # Requests per burst
STATIC_SEQ = "MKTLLILTGVVAAASH" # The "Target" sequence

async def send_request(client, sequence):
    try:
        response = await client.post(GATEWAY_URL, params={"sequence": sequence})
        return response.json().get("status"), response.status_code
    except Exception as e:
        return f"ERROR: {str(e)}", 500

async def run_test_suite():
    async with httpx.AsyncClient(timeout=10.0) as client:
        print("🚀 Starting HelixStream Idempotency Suite\n")

        # --- TEST 1: The "Thundering Herd" (Same Sequence) ---
        print(f"TEST 1: Sending {TOTAL_BURST} identical sequences simultaneously...")
        start = time.perf_counter()
        tasks = [send_request(client, STATIC_SEQ) for _ in range(TOTAL_BURST)]
        results = await asyncio.gather(*tasks)
        end = time.perf_counter()
        
        counts = Counter([r[0] for r in results])
        print(f"  Result: {dict(counts)}")
        print(f"  Latency: {(end - start)*1000:.2f}ms")
        print("  💡 CHECK JAVA CONSOLE: Should only see ONE 'Queued' log.\n")

        # --- TEST 2: High-Throughput Unique Sequences ---
        print(f"TEST 2: Sending {TOTAL_BURST} unique sequences...")
        unique_seqs = [f"SEQ_{i}_{time.time()}" for i in range(TOTAL_BURST)]
        start = time.perf_counter()
        tasks = [send_request(client, s) for s in unique_seqs]
        results = await asyncio.gather(*tasks)
        end = time.perf_counter()

        counts = Counter([r[0] for r in results])
        print(f"  Result: {dict(counts)}")
        print(f"  Latency: {(end - start)*1000:.2f}ms")
        print(f"  💡 CHECK JAVA CONSOLE: Queue size should increase by {TOTAL_BURST}.\n")

        # --- TEST 3: Mixed Load (Hot vs New) ---
        print(f"TEST 3: Mixed Burst (50% Hot STATIC_SEQ, 50% New Unique)...")
        mixed_seqs = [STATIC_SEQ if i % 2 == 0 else f"NEW_{i}" for i in range(TOTAL_BURST)]
        start = time.perf_counter()
        tasks = [send_request(client, s) for s in mixed_seqs]
        results = await asyncio.gather(*tasks)
        end = time.perf_counter()

        counts = Counter([r[0] for r in results])
        print(f"  Result: {dict(counts)}")
        print(f"  Latency: {(end - start)*1000:.2f}ms")

if __name__ == "__main__":
    asyncio.run(run_test_suite())