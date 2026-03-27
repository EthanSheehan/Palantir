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
        if "sedan" in name or "car" in name or "office" in name or "building" in name:
            path = str(child.GetPath())
            try:
                from pxr import Semantics as SemAPI
                sem = SemAPI.SemanticsAPI.Apply(child, "Semantics")
                sem.CreateSemanticTypeAttr().Set("class")
                if "sedan" in name or "car" in name:
                    sem.CreateSemanticDataAttr().Set("car")
                else:
                    sem.CreateSemanticDataAttr().Set("building")
                print(f"  Labeled: {path}")
                labeled += 1
            except Exception as e:
                print(f"  FAILED {path}: {e}")

# Verify
print(f"\n=== Verification ({labeled} prims labeled) ===")
for prim in Usd.PrimRange(stage.GetPseudoRoot()):
    for attr in prim.GetAttributes():
        if "semantic" in attr.GetName().lower():
            print(f"  {prim.GetPath()}: {attr.GetName()} = {attr.Get()}")

print("\nDone! Save the scene (Ctrl+S) to persist labels.")
