"""
Apply semantic labels to UE5-exported prims in Isaac Sim.
The GUI Semantics Schema Editor has issues with UE5 exports,
so we use the pxr Semantics API directly.

Run in Isaac Sim Script Editor after opening your terrain_scene.usd.
Must be run BEFORE any Replicator/annotator scripts.
"""
import omni.usd
from pxr import Usd, UsdGeom

stage = omni.usd.get_context().get_stage()

print("=== Applying Semantic Labels ===")
labeled = 0
for prim in stage.GetPseudoRoot().GetChildren():
    for child in Usd.PrimRange(prim):
        name = child.GetName().lower()
        if "zil" in name or "truck" in name or "sedan" in name or "car" in name:
            path = str(child.GetPath())
            try:
                from pxr import Semantics as SemAPI
                sem = SemAPI.SemanticsAPI.Apply(child, "Semantics")
                sem.CreateSemanticTypeAttr().Set("class")
                sem.CreateSemanticDataAttr().Set("truck")
                print(f"  Labeled: {path}")
                labeled += 1
            except Exception as e:
                print(f"  FAILED {path}: {e}")

print(f"\nLabeled {labeled} prims. Now hit Play and run ISAACSIM_pitch_guidance.py")

