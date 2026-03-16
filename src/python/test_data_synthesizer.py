import requests
import time
import random
import uuid
from datetime import datetime

API_URL = "http://localhost:8000/ingest"

def generate_mock_detection():
    types = ["TEL", "SAM", "Command Post", "Unknown"]
    sources = ["UAV", "Satellite", "SIGINT"]
    
    return {
        "source": random.choice(sources),
        "lat": 33.3 + random.uniform(-0.1, 0.1),
        "lon": 44.3 + random.uniform(-0.1, 0.1),
        "confidence": random.uniform(0.4, 0.98),
        "classification": random.choice(types),
        "timestamp": datetime.now().isoformat()
    }

def run_synthesizer(count=50, interval=1.0):
    print(f"Starting Project Antigravity Data Synthesizer ({count} targets)...")
    for i in range(count):
        detection = generate_mock_detection()
        try:
            response = requests.post(API_URL, json=detection)
            if response.status_code == 200:
                data = response.json()
                print(f"[{i+1}/{count}] Ingested: {data['processed_tracks']} tracks processed.")
            else:
                print(f"Error ingesting data: {response.text}")
        except Exception as e:
            print(f"Connection error (is the API running?): {e}")
            break
        
        time.sleep(interval)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args()
    
    run_synthesizer(count=args.count, interval=args.interval)
