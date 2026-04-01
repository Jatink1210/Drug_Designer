"""Triggers a background embedding job for all active Qdrant collections."""

import asyncio
import httpx
import sys

async def trigger_embed_job():
    url = "http://localhost:8000/api/embeddings/run"
    payload = {
        "collections": [
            "proteins", "genes", "diseases", "drugs", 
            "variants", "pathways", "publications", 
            "clinical_trials", "molecules"
        ],
        "limit_per_collection": 100
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            print(f"Successfully queued embedding job. Job ID: {data['job_id']}")
    except Exception as e:
        print(f"Error triggering embed job: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(trigger_embed_job())
