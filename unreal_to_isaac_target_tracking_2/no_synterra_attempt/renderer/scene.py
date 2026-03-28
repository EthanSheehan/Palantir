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
        self._scene = pyrender.Scene(
            bg_color=[0.0, 0.0, 0.0, 1.0],
            ambient_light=[0.3, 0.3, 0.3],
        )

        # Load terrain mesh with texture
        self._load_terrain(obj_path, texture_path)

        # Add directional light (sun from above)
        light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.0)
        light_pose = np.eye(4)
        light_pose[:3, 3] = [0, 100000, 0]
        self._scene.add(light, pose=light_pose)

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

    def add_target(self, name: str, label: str, position: np.ndarray,
                   size: float = 500.0, color: Tuple[float, ...] = (0.5, 0.5, 0.2, 1.0)):
        """Add a box target at the given position (cm, Y-up).

        Equivalent to UsdGeom.Cube.Define() + Semantics.SemanticsAPI.Apply().
        """
        pos = np.asarray(position, dtype=np.float64)
        half = size / 2.0

        # Create box mesh
        box = trimesh.creation.box(extents=[size, size, size])
        box.visual.face_colors = [int(c * 255) for c in color]

        # Convert to pyrender
        material = pyrender.MetallicRoughnessMaterial(
            baseColorFactor=color,
            metallicFactor=0.1,
            roughnessFactor=0.8,
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
