import omni.usd
from pxr import Usd, Semantics as SemAPI

stage = omni.usd.get_context().get_stage()
for prim in Usd.PrimRange(stage.GetPseudoRoot()):
    if "zil" in prim.GetName().lower():
        sem = SemAPI.SemanticsAPI.Apply(prim, "Semantics")
        sem.CreateSemanticTypeAttr().Set("class")
        sem.CreateSemanticDataAttr().Set("truck")
        print(f"Labeled: {prim.GetPath()}")
