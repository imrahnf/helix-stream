import sys
import os
# Add the sdk to the path so we can import it
sys.path.append(os.path.join(os.getcwd(), 'libs', 'titan-sdk'))
from titan_client import TitanClient

def run_test():
    try:
        with TitanClient(host='localhost', port=6379) as client:
            # Test SET
            resp = client.set("p_7721", "MKVLWAALLVTFLAGCQAK...")
            print(f"Set Response: {resp}")
            
            # Test GET
            data = client.get("p_7721")
            print(f"Get Response: {data}")
            
            if data == "MKVLWAALLVTFLAGCQAK...":
                print("TCP Bridge successfully established!")
            else:
                print("Data mismatch.")
    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    run_test()