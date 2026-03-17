import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from contextlib import asynccontextmanager

# Import from sim_engine
from sim_engine import SimulationModel

class TacticalAssistant:
    def __init__(self):
        self.message_history = []
        self.last_detected = {} # target_id -> bool

    def update(self, sim_state):
        new_messages = []
        for target in sim_state.get("targets", []):
            tid = target["id"]
            is_detected = target["detected"]
            t_type = target["type"]
            
            if is_detected and not self.last_detected.get(tid, False):
                # New detection
                msg = {
                    "type": "ASSISTANT_MESSAGE",
                    "text": f"NEW CONTACT: {t_type} localized at {target['lon']:.4f}, {target['lat']:.4f}",
                    "severity": "INFO",
                    "timestamp": time.strftime("%H:%M:%S")
                }
                new_messages.append(msg)
            
            self.last_detected[tid] = is_detected
        
        return new_messages

assistant = TacticalAssistant()
import time

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
clients = {} # websocket -> info dict

async def broadcast(message: str, target_type: str = None, sender: WebSocket = None):
    """Parallel broadcast to all matching clients with a strict timeout."""
    if not clients:
        return
        
    targets = []
    for ws, info in clients.items():
        if ws == sender:
            continue
        if target_type and info.get("type") != target_type:
            continue
        targets.append(ws)
        
    if not targets:
        return

    async def _send(ws):
        try:
            await asyncio.wait_for(ws.send_text(message), timeout=0.1)
        except:
            return ws

    # Run all sends in parallel
    results = await asyncio.gather(*[_send(t) for t in targets])
    
    # Cleanup failed clients
    for failed_ws in results:
        if failed_ws and failed_ws in clients:
            del clients[failed_ws]

async def simulation_loop():
    print("Starting Palantir C2 Simulation Loop at 10Hz")
    while True:
        sim.tick()
        if clients:
            state = sim.get_state()
            state_json = json.dumps({"type": "state", "data": state})
            # Only send simulation state to dashboard clients
            await broadcast(state_json, target_type="DASHBOARD")

            # Update assistant
            assistant_msgs = assistant.update(state)
            for msg in assistant_msgs:
                await broadcast(json.dumps(msg), target_type="DASHBOARD")
                
        await asyncio.sleep(1/10.0)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Wait for the first message to identify the client
    try:
        ident_msg = await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
        ident_payload = json.loads(ident_msg)
        if ident_payload.get("type") == "IDENTIFY":
            client_type = ident_payload.get("client_type", "DASHBOARD")
            clients[websocket] = {"type": client_type}
            print(f"Client identified: {client_type}")
        else:
            # Fallback for older clients or immediate data
            clients[websocket] = {"type": "DASHBOARD"}
            await handle_payload(ident_payload, websocket, ident_msg)
    except Exception as e:
        clients[websocket] = {"type": "DASHBOARD"}
        print(f"Client identification failed ({e}), defaulting to DASHBOARD")

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            await handle_payload(payload, websocket, data)
    except WebSocketDisconnect:
        print("Client Disconnected")
    except Exception as e:
        print(f"WebSocket Error: {e}")
    finally:
        if websocket in clients:
            del clients[websocket]

async def handle_payload(payload: dict, websocket: WebSocket, raw_data: str):
    """Handle incoming payloads based on type/action."""
    action = payload.get("action")
    p_type = payload.get("type")

    if action == "spike":
        lon, lat = payload.get("lon"), payload.get("lat")
        if lon is not None and lat is not None:
            sim.trigger_demand_spike(lon, lat)
    
    elif action == "move_drone":
        drone_id = payload.get("drone_id")
        lon, lat = payload.get("target_lon"), payload.get("target_lat")
        if drone_id and lon is not None and lat is not None:
            sim.command_move(drone_id, lon, lat)
    
    elif action == "SET_SCENARIO":
        # Forward command to SIMULATORS
        await broadcast(raw_data, target_type="SIMULATOR", sender=websocket)

    elif p_type in ["DRONE_FEED", "TRACK_UPDATE", "TRACK_UPDATE_BATCH"]:
        # Forward vision/track data to DASHBOARDs
        await broadcast(raw_data, target_type="DASHBOARD", sender=websocket)

    elif action == "reset":
        sim.reset_queues()
        print("Reset Grid State")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
