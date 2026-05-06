"""SceneBuilder — loads terrain mesh + texture, places target objects.

Replaces Isaac Sim's USD scene graph with trimesh + pyrender.
"""
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import trimesh
import pyrender


class SceneBuilder:
    def __init__(self, obj_path: str, texture_path: str, metadata: dict):
        self._metadata = metadata
        self._targets: Dict[str, dict] = {}
        # Daylight sky background and brighter ambient — outdoor scene, not a black room.
        self._scene = pyrender.Scene(
            bg_color=[0.55, 0.72, 0.92, 1.0],
            ambient_light=[0.55, 0.55, 0.55],
        )

        # Load terrain mesh with texture
        self._load_terrain(obj_path, texture_path)

        # Two-light rig: warm sun from above-right, soft sky-fill from above-left.
        sun = pyrender.DirectionalLight(color=[1.0, 0.96, 0.86], intensity=5.0)
        sun_pose = np.eye(4)
        # Light direction is the -Z axis of the pose. Tilt the sun ~45° forward and right.
        sun_dir = np.array([-0.55, -0.75, -0.35], dtype=np.float64)
        sun_dir /= np.linalg.norm(sun_dir)
        up = np.array([0.0, 1.0, 0.0])
        right = np.cross(up, sun_dir)
        right /= np.linalg.norm(right)
        new_up = np.cross(sun_dir, right)
        sun_pose[:3, 0] = right
        sun_pose[:3, 1] = new_up
        sun_pose[:3, 2] = -sun_dir
        sun_pose[:3, 3] = [0, 100000, 0]
        self._scene.add(sun, pose=sun_pose)

        sky_fill = pyrender.DirectionalLight(color=[0.7, 0.78, 0.95], intensity=2.5)
        fill_pose = np.eye(4)
        fill_pose[:3, 3] = [0, 100000, 50000]
        self._scene.add(sky_fill, pose=fill_pose)

    def _load_terrain(self, obj_path: str, texture_path: str):
        """Load OBJ mesh and apply satellite texture."""
        # trimesh.load handles OBJ+MTL with textures
        mesh_or_scene = trimesh.load(obj_path, process=False)

        if isinstance(mesh_or_scene, trimesh.Scene):
            # Multi-mesh OBJ: iterate geometries
            for name, geom in mesh_or_scene.geometry.items():
                self._add_trimesh(geom, texture_path)
        elif isinstance(mesh_or_scene, trimesh.Trimesh):
            self._add_trimesh(mesh_or_scene, texture_path)
        else:
            raise ValueError(f"Unexpected mesh type: {type(mesh_or_scene)}")

    def _add_trimesh(self, mesh: trimesh.Trimesh, texture_path: str):
        """Add a trimesh to the pyrender scene, applying texture if needed."""
        # If the mesh already has a texture from the MTL, use it
        if mesh.visual and hasattr(mesh.visual, 'material'):
            try:
                pr_mesh = pyrender.Mesh.from_trimesh(mesh, smooth=False)
                self._scene.add(pr_mesh)
                return
            except Exception:
                pass

        # Fallback: manually apply texture via UV coordinates
        if mesh.visual and hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
            from PIL import Image
            tex_img = Image.open(texture_path)
            tex_array = np.array(tex_img)

            material = trimesh.visual.texture.SimpleMaterial(
                image=tex_img,
                ambient=[1.0, 1.0, 1.0, 1.0],
                diffuse=[1.0, 1.0, 1.0, 1.0],
            )
            color_visuals = trimesh.visual.TextureVisuals(
                uv=mesh.visual.uv,
                material=material,
                image=tex_img,
            )
            mesh.visual = color_visuals

        pr_mesh = pyrender.Mesh.from_trimesh(mesh, smooth=False)
        self._scene.add(pr_mesh)

    # Color palette mirrors src/python/vision/video_simulator.py TARGET_STYLES so the
    # 3D pyrender view matches the colors the rest of Grid-Sentinel uses for targets.
    _TARGET_COLORS = {
        "SAM":       (0.95, 0.10, 0.10, 1.0),
        "TEL":       (1.00, 0.55, 0.10, 1.0),
        "TRUCK":     (0.95, 0.95, 0.95, 1.0),
        "CP":        (0.20, 0.45, 1.00, 1.0),
        "MANPADS":   (0.78, 0.20, 0.78, 1.0),
        "RADAR":     (0.20, 0.95, 0.95, 1.0),
        "C2_NODE":   (0.95, 0.95, 0.20, 1.0),
        "LOGISTICS": (0.70, 0.70, 0.70, 1.0),
        "ARTILLERY": (1.00, 0.30, 0.55, 1.0),
        "APC":       (0.40, 0.30, 0.20, 1.0),
    }

    def add_target(self, name: str, label: str, position: np.ndarray,
                   size: float = 500.0, color: Tuple[float, ...] = None):
        """Add a box target at the given position (cm, Y-up).

        Equivalent to UsdGeom.Cube.Define() + Semantics.SemanticsAPI.Apply().
        Color is picked from the Grid-Sentinel target palette by `label` if not given.
        """
        pos = np.asarray(position, dtype=np.float64)
        half = size / 2.0
        if color is None:
            color = self._TARGET_COLORS.get(label.upper(), (0.95, 0.85, 0.15, 1.0))

        # Create box mesh
        box = trimesh.creation.box(extents=[size, size, size])
        box.visual.face_colors = [int(c * 255) for c in color]

        # Convert to pyrender — emissive so targets pop against the terrain
        material = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=color,
            metallicFactor=0.05,
            roughnessFactor=0.5,
            emissiveFactor=[c * 0.4 for c in color[:3]],
        )
        pr_mesh = pyrender.Mesh.from_trimesh(box, material=material)

        # Place at position
        pose = np.eye(4)
        pose[:3, 3] = pos
        node = self._scene.add(pr_mesh, pose=pose)

        # Store target info for annotation
        corners = np.array([
            [pos[0] + dx, pos[1] + dy, pos[2] + dz]
            for dx in [-half, half]
            for dy in [-half, half]
            for dz in [-half, half]
        ], dtype=np.float64)

        self._targets[name] = {
            "label": label,
            "position": pos.copy(),
            "size": size,
            "corners": corners,
            "node": node,
        }

    def get_target_aabb(self, name: str) -> np.ndarray:
        """Return 8x3 array of AABB corners in world space."""
        return self._targets[name]["corners"].copy()

    def get_targets(self) -> List[dict]:
        """Return all targets with label, position, and AABB corners."""
        return [
            {
                "name": name,
                "label": info["label"],
                "position": info["position"],
                "corners": info["corners"],
            }
            for name, info in self._targets.items()
        ]

    @property
    def scene(self) -> pyrender.Scene:
        return self._scene
