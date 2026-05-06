"""
Drive the Grid-Sentinel SimulationModel for a few ticks, then render its real
state (drones + targets) through the pyrender bridge. Saves snapshots of:
  - overhead god view of the whole battlespace
  - UAV-POV gimbal view from the first drone
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

GS = "/Volumes/Toshiba_1TB/GitHub/Grid-Sentinel"
sys.path.insert(0, os.path.join(GS, "src", "python"))

from sim_engine import SimulationModel
from vision.pyrender_bridge import GridSentinelRenderer

OUT = "/tmp/gs-snapshots"
os.makedirs(OUT, exist_ok=True)


def hud_overlay(arr, lines):
    img = Image.fromarray(arr).convert("RGB")
    draw = ImageDraw.Draw(img)
    y = 6
    for line in lines:
        draw.text((7, y + 1), line, fill=(0, 0, 0))
        draw.text((6, y), line, fill=(255, 220, 0))
        y += 14
    return img


def snapshot_caption(sim, uav_id):
    target_types = {}
    for t in sim.targets.values():
        target_types[t.type] = target_types.get(t.type, 0) + 1
    parts = ", ".join(f"{k}:{v}" for k, v in sorted(target_types.items()))
    host = sim.uavs.get(uav_id) if uav_id else None
    lines = [
        f"theater    {sim.theater_name}",
        f"UAVs       {len(sim.uavs)}",
        f"targets    {len(sim.targets)}  [{parts}]",
    ]
    if host:
        lines.append(f"host UAV   #{host.id} alt={host.altitude_m:.0f}m mode={host.mode}")
    return lines


print("Booting Grid-Sentinel SimulationModel (theater=romania)…")
sim = SimulationModel(theater_name="romania")
print(f"  initial UAVs={len(sim.uavs)} targets={len(sim.targets)}")

# Tick a few times so kinematics, detections, fusion settle
for _ in range(15):
    sim.tick()
print(f"  after 15 ticks: UAVs={len(sim.uavs)} targets={len(sim.targets)}")

renderer = GridSentinelRenderer(width=720, height=480, scene_radius_m=4_000.0)
print(f"Renderer backend: {renderer._renderer.backend}")

uav_ids = list(sim.uavs.keys())
print(f"Available UAV ids: {uav_ids[:8]}{'…' if len(uav_ids)>8 else ''}")

# 1) Overhead god view — shows whole battlespace
overhead = renderer.render_overhead(sim, altitude_m=6000.0)
hud_overlay(overhead, snapshot_caption(sim, None) + ["view  OVERHEAD (god)"]).save(
    os.path.join(OUT, "gs_overhead.png")
)
print("saved gs_overhead.png")

# 2) UAV gimbal view from the first available UAV
if uav_ids:
    host_id = uav_ids[0]
    img = renderer.render_from_uav(sim, host_id, gimbal_pitch_deg=20.0)
    hud_overlay(img, snapshot_caption(sim, host_id) + [f"view  GIMBAL  pitch=20deg"]).save(
        os.path.join(OUT, f"gs_uav_{host_id}_gimbal.png")
    )
    print(f"saved gs_uav_{host_id}_gimbal.png")

# 3) Tick more, render again — show targets have moved
for _ in range(60):
    sim.tick()
print(f"After 60 more ticks: UAVs={len(sim.uavs)} targets={len(sim.targets)}")

overhead2 = renderer.render_overhead(sim, altitude_m=6000.0)
hud_overlay(overhead2, snapshot_caption(sim, None) + ["view  OVERHEAD (t+60)"]).save(
    os.path.join(OUT, "gs_overhead_t60.png")
)
print("saved gs_overhead_t60.png")

if uav_ids:
    host_id = uav_ids[0]
    img2 = renderer.render_from_uav(sim, host_id, gimbal_pitch_deg=20.0)
    hud_overlay(img2, snapshot_caption(sim, host_id) + [f"view  GIMBAL  t+60"]).save(
        os.path.join(OUT, f"gs_uav_{host_id}_gimbal_t60.png")
    )
    print(f"saved gs_uav_{host_id}_gimbal_t60.png")

# 4) Steep-angle dive view (pitch high) — rendered from a UAV closing on a target
if sim.targets and uav_ids:
    # Move host UAV near a target to make for a dramatic dive frame
    target = next(iter(sim.targets.values()))
    host = sim.uavs[uav_ids[0]]
    # Approach 0.005 deg (~500 m) west of the target, pointing east
    host.x = target.x - 0.005
    host.y = target.y
    host.altitude_m = 1500.0
    host.heading_deg = 90.0  # east
    img3 = renderer.render_from_uav(sim, host.id, gimbal_pitch_deg=45.0)
    hud_overlay(img3, snapshot_caption(sim, host.id) + ["view  DIVE  pitch=45deg, 500m W of target"]).save(
        os.path.join(OUT, "gs_dive_close.png")
    )
    print("saved gs_dive_close.png")

renderer.close()
print(f"\nAll snapshots in {OUT}")
