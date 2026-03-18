import requests
import time
import random
import uuid
from datetime import datetime

import structlog

logger = structlog.get_logger()

API_URL = "http://localhost:8000/ingest"

def generate_mock_detection():
    types = ["TEL", "SAM", "CP", "Unknown"]
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
    logger.info("synthesizer_started", count=count)
    for i in range(count):
        detection = generate_mock_detection()
        try:
            response = requests.post(API_URL, json=detection, timeout=10)
            if response.status_code == 200:
                data = response.json()
                logger.info("ingested", progress=f"{i+1}/{count}", tracks=data["processed_tracks"])
            else:
                logger.error("ingest_error", status=response.status_code, body=response.text)
        except requests.ConnectionError as exc:
            logger.error("connection_error", error=str(exc), hint="Is the API running?")
            break
        except requests.Timeout as exc:
            logger.error("request_timeout", error=str(exc))
            break

        time.sleep(interval)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args()

    run_synthesizer(count=args.count, interval=args.interval)
