import asyncio
import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

from websocket_manager import manager
from pipeline import F2T2EAPipeline
from schemas.ontology import Track, CourseOfAction
from sim_engine import sim

app = FastAPI(title="Palantir C2 API")

# Serve Frontend and Resources
app.mount("/static", StaticFiles(directory="src/frontend"), name="static")
app.mount("/resources", StaticFiles(directory="resources"), name="resources")

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

async def simulation_loop():
    """Background task to run the tactical simulation."""
    while True:
        sim.tick()
        state = sim.get_state()
        # Broadcast track updates to ALL clients
        await manager.broadcast(state)
        await asyncio.sleep(0.2) # 5Hz for stability

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulation_loop())

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
                
                # Handle Commands
                if message.get("type") == "CMD_SET_WAYPOINT":
                    sim.set_waypoint(
                        message.get("drone_id"),
                        message.get("lon"),
                        message.get("lat")
                    )
                elif message.get("type") == "CMD_SET_SCENARIO":
                    sim.set_scenario(message.get("scenario"))
                elif message.get("type") == "CMD_START_INTERCEPT":
                    sim.start_intercept(
                        message.get("drone_id"),
                        message.get("target_id")
                    )
                elif message.get("type") == "SUBSCRIBE_VIDEO":
                    await manager.subscribe(websocket, message.get("drone_id"))
                elif message.get("type") == "UNSUBSCRIBE_VIDEO":
                    await manager.unsubscribe(websocket, message.get("drone_id"))
                
                # Relay message to all OTHER connected clients
                await manager.broadcast(message, exclude=websocket)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(websocket)

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
