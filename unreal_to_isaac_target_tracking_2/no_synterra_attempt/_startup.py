
import omni.kit.app
import asyncio

async def _auto_start():
    # Wait for Isaac Sim to fully initialize
    for _ in range(120):
        await omni.kit.app.get_app().next_update_async()
    print("[STARTUP] Isaac Sim ready, loading auto pipeline...")
    exec(open(r"C:\Users\victo\Downloads\unreal_to_isaac_target_tracking_2\no_synterra_attempt\_auto_isaac.py").read())

asyncio.ensure_future(_auto_start())
