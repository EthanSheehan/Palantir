import omni.kit.commands
import omni.usd
from pxr import UsdGeom, Gf, Sdf, Usd
import asyncio
import omni.kit.app

stage = omni.usd.get_context().get_stage()

# Import STL
stl_path = r"C:\Users\victo\Downloads\unreal_to_isaac_target_tracking_2\scripts\guidance\Fixed V2 for Print.stl"

print("Importing drone STL...")
import omni.kit.asset_converter
converter = omni.kit.asset_converter.get_instance()

async def import_drone():
    # Convert STL to USD
    usd_path = r"C:\Users\victo\Downloads\unreal_to_isaac_target_tracking_2\scripts\guidance\drone_model.usd"
    
    context = omni.kit.asset_converter.AssetConverterContext()
    context.ignore_materials = False
    context.ignore_animations = True
    
    task = converter.create_converter_task(stl_path, usd_path, None, context)
    success = await task.wait_until_finished()
    
    if success:
        print(f"Converted to: {usd_path}")
        
        # Add as reference in the scene
        drone_prim_path = "/DroneModel"
        if stage.GetPrimAtPath(drone_prim_path):
            stage.RemovePrim(drone_prim_path)
        
        drone_prim = stage.DefinePrim(drone_prim_path)
        drone_prim.GetReferences().AddReference(usd_path)
        print(f"Drone mesh added at {drone_prim_path}")
        print("Now run ISAACSIM_pitch_guidance.py — drone mesh will follow the camera!")
    else:
        print("STL conversion failed!")

asyncio.ensure_future(import_drone())
