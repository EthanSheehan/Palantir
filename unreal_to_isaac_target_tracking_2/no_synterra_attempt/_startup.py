
import omni.kit.app
import asyncio

async def _auto_start():
    # Wait for Isaac Sim to fully initialize
    for _ in range(120):
        await omni.kit.app.get_app().next_update_async()
    print("[STARTUP] Isaac Sim ready, loading auto pipeline...")
    import os as _os
    _auto_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_auto_isaac.py")
    exec(open(_auto_path).read())  # noqa: S102 — Isaac Sim startup requires exec

asyncio.ensure_future(_auto_start())
