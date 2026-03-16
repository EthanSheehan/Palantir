import asyncio
import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from websocket_manager import manager
from pipeline import F2T2EAPipeline
from schemas.ontology import Track, CourseOfAction

app = FastAPI(title="Palantir C2 API")

# Configure CORS for Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the actual dashboard URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock LLM Client for demonstration
class MockLLM:
    async def generate_response(self, prompt: str):
        return "Mock response from AIP Assistant."

llm_client = MockLLM()
pipeline = F2T2EAPipeline(llm_client=llm_client)

@app.get("/")
async def root():
    return {"status": "Palantir C2 Online", "version": "1.0.0"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Receive data and relay it to all connected clients
            try:
                data = await websocket.receive_text()
            except RuntimeError:
                # Handle "Need to call accept first" or already closed
                break
            try:
                message = json.loads(data)
                # Relay message to all OTHER connected clients
                await manager.broadcast(message, exclude=websocket)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/ingest")
async def ingest_data(payload: dict):
    """Data ingestion endpoint for heterogeneous sensor feeds."""
    # In a real scenario, this would be handled asynchronously
    result = pipeline.run(json.dumps(payload), auto_approve=True)
    
    # Broadcast updates to the dashboard via WebSocket
    await manager.broadcast({
        "type": "TRACK_UPDATE",
        "timestamp": datetime.now().isoformat(),
        "data": result["isr_output"].dict()
    })
    
    if result["analyst_output"].nominations:
        await manager.broadcast({
            "type": "NOMINATION_ALERT",
            "data": result["analyst_output"].dict()
        })
    
    return {"status": "ingested", "processed_tracks": len(result["isr_output"].tracks)}

@app.post("/approve-coa")
async def approve_coa(coa_id: str):
    """HITL Approval endpoint for executing a strike."""
    # Search for the COA in a real system (mocked here)
    return {"status": "approved", "coa_id": coa_id, "token": "HUMAN_APPROVAL_TOKEN_VALID"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
