import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager

# Import from sim_engine (which will be our new sim.py from grid 9)
from sim_engine import SimulationModel

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start simulation loop
    task = asyncio.create_task(simulation_loop())
    yield
    # Shutdown: Cancel task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

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
    print("Starting Palantir C2 Simulation Loop at 10Hz")
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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    print("Dashboard Connected to Uplink")
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
            
            elif payload.get("action") == "move_drone":
                drone_id = payload.get("drone_id")
                lon = payload.get("target_lon")
                lat = payload.get("target_lat")
                if drone_id is not None and lon is not None and lat is not None:
                    sim.command_move(drone_id, lon, lat)
                    print(f"Commanded Drone {drone_id} to [{lon}, {lat}]")
            
            elif payload.get("action") == "SET_SCENARIO":
                # Forward scenario commands to simulators
                print(f"Forwarding Scenario Command: {payload}")
                for client in list(clients):
                    if client != websocket: # Don't send back to sender
                        try:
                            await client.send_text(json.dumps(payload))
                        except:
                            pass

            elif payload.get("type") == "DRONE_FEED" or payload.get("type") == "TRACK_UPDATE":
                # Broadcast vision-data to all dashboard clients (port 3000)
                # Note: SIMULATOR pushes these types
                for client in list(clients):
                    if client != websocket:
                        try:
                            await client.send_text(data)
                        except:
                            pass

            elif payload.get("action") == "reset":
                sim.reset_queues()
                print("Reset Grid State")

                
    except WebSocketDisconnect:
        print("Dashboard Disconnected")
        clients.discard(websocket)
    except Exception as e:
        print(f"WebSocket Error: {e}")
        clients.discard(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
