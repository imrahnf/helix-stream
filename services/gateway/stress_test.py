import sys
import os
import grpc
import uuid
import time

# Resolve gRPC paths
current_dir = os.path.dirname(os.path.abspath(__file__))
gen_path = os.path.normpath(os.path.join(current_dir, "gen"))
sys.path.append(gen_path)

import cache_pb2
import cache_pb2_grpc

def run_stress_test(item_count=1000, string_length=5000):
    print(f"🚀 Starting Stress Test: {item_count} items, {string_length} chars each...")
    channel = grpc.insecure_channel('localhost:9090')
    stub = cache_pb2_grpc.CacheServiceStub(channel)

    start_time = time.time()
    success_count = 0

    # 1. BULK PUT
    print(f"📥 Filling TitanCache...")
    long_string = "A" * string_length  # Simulating a large embedding string
    
    for i in range(item_count):
        key = f"protein_seq_{i}_{uuid.uuid4().hex[:8]}"
        try:
            stub.Put(cache_pb2.CacheEntry(key=key, value=long_string))
            success_count += 1
            if i % 200 == 0:
                print(f"   Progress: {i}/{item_count} stored...")
        except grpc.RpcError as e:
            print(f"   ❌ Failed at item {i}: {e.code()}")

    # 2. VERIFY LATEST
    print(f"🔍 Verifying last item...")
    last_key = f"protein_seq_{item_count-1}" # This depends on your naming logic above
    # Let's just grab a random one we know we sent
    response = stub.Get(cache_pb2.KeyRequest(key=key))
    
    end_time = time.time()
    duration = end_time - start_time

    print("\n" + "="*30)
    print(f"📊 STRESS TEST RESULTS")
    print(f"Total Items: {success_count}")
    print(f"Payload Size: ~{string_length / 1024:.2f} KB per item")
    print(f"Total Time: {duration:.2f} seconds")
    print(f"Throughput: {success_count / duration:.2f} items/sec")
    print(f"Verification: {'✅ SUCCESS' if response.found else '❌ MISS (Check LRU Capacity)'}")
    print("="*30)

if __name__ == "__main__":
    run_stress_test()