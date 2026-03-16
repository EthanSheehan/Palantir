import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import sys
import os

# Add parent dir to path so we can import romania_grid
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import SimulationModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sim = SimulationModel()
clients = set()

async def simulation_loop():
    print("Starting simulation loop at 10Hz")
    while True:
        sim.tick()
        if clients:
            state = sim.get_state()
            state_json = json.dumps({"type": "state", "data": state})
            
            disconnected = set()
            for client in list(clients):
                try:
                    await client.send_text(state_json)
                except Exception:
                    disconnected.add(client)
            
            for client in disconnected:
                clients.discard(client)
                
        await asyncio.sleep(1/10.0)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulation_loop())

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            if payload.get("action") == "spike":
                lon = payload.get("lon")
                lat = payload.get("lat")
                if lon is not None and lat is not None:
                    sim.trigger_demand_spike(lon, lat)
                    print(f"Triggered spike at {lon}, {lat}")
            
            elif payload.get("action") == "reset":
                sim.reset_queues()
                print("Reset queues")
                
    except WebSocketDisconnect:
        clients.discard(websocket)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)
