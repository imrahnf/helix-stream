import requests
import time

# The range of sequences you just flooded (10 to 50)
START = 10
END = 50
BASE_URL = "http://localhost:8000/v1/analyze"
MODEL_ID = "esm2_t6_8M_UR50D"

def verify_sweep():
    print(f"🚀 Starting verification sweep for sequences {START} to {END}...")
    
    hits = 0
    errors = 0

    for i in range(START, END + 1):
        sequence = f"MKTLLILAVVSEQUENCE{i}"
        
        try:
            # The "Second Call" that triggers Read-Repair
            response = requests.post(
                BASE_URL, 
                params={"sequence": sequence, "model_id": MODEL_ID}
            )
            data = response.json()

            if data.get("source") == "L1_CACHE" and data.get("status") == "COMPLETED":
                print(f"✅ Seq {i}: Verified in L1 (Repair Triggered)")
                hits += 1
            else:
                print(f"⚠️  Seq {i}: Unexpected Source -> {data.get('source')}")
        
        except Exception as e:
            print(f"❌ Error verifying Seq {i}: {e}")
            errors += 1

    print("\n--- Final Report ---")
    print(f"Total Verified: {hits}/{END - START + 1}")
    print(f"Failures: {errors}")

if __name__ == "__main__":
    verify_sweep()