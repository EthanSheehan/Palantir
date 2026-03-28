"""OffscreenRenderer — GPU-accelerated or CPU-fallback offscreen rendering.

Replaces Isaac Sim's render pipeline + rep.create.render_product.

On Windows: pyrender uses pyglet to create a hidden window for OpenGL context.
            Do NOT set PYOPENGL_PLATFORM — let pyrender auto-detect.
On Linux:   pyrender can use EGL (GPU) or OSMesa (CPU).
"""
import os
import sys
from typing import Tuple

import numpy as np
import pyrender

from .camera import DroneCamera


class OffscreenRenderer:
    def __init__(self, width: int, height: int, prefer_gpu: bool = True):
        self.width = width
        self.height = height
        self._renderer = None
        self._backend = "unknown"

        if prefer_gpu:
            self._try_default()

        if self._renderer is None and sys.platform != "win32":
            self._try_egl()

        if self._renderer is None and sys.platform != "win32":
            self._try_osmesa()

        if self._renderer is None:
            raise RuntimeError(
                "Could not initialize any rendering backend.\n"
                "  Windows: install pyglet>=2.0 (pip install pyglet)\n"
                "  Linux:   install EGL or OSMesa (apt install libegl1 or libosmesa6)"
            )

    def _try_default(self):
        """Try default platform (pyglet on Windows, auto on Linux)."""
        # Remove any platform override — let pyrender choose
        saved = os.environ.pop("PYOPENGL_PLATFORM", None)
        try:
            self._renderer = pyrender.OffscreenRenderer(
                self.width, self.height, point_size=1.0)
            self._backend = "GPU (OpenGL/pyglet)"
            print(f"Renderer: {self._backend}")
        except Exception as e:
            print(f"Default renderer unavailable: {e}")
            self._renderer = None
            if saved is not None:
                os.environ["PYOPENGL_PLATFORM"] = saved

    def _try_egl(self):
        """Try EGL rendering (Linux with GPU, headless)."""
        try:
            os.environ["PYOPENGL_PLATFORM"] = "egl"
            self._renderer = pyrender.OffscreenRenderer(
                self.width, self.height, point_size=1.0)
            self._backend = "GPU (EGL)"
            print(f"Renderer: {self._backend}")
        except Exception as e:
            print(f"EGL rendering unavailable: {e}")
            self._renderer = None

    def _try_osmesa(self):
        """Try OSMesa rendering (CPU software rasterizer, Linux)."""
        try:
            os.environ["PYOPENGL_PLATFORM"] = "osmesa"
            self._renderer = pyrender.OffscreenRenderer(
                self.width, self.height, point_size=1.0)
            self._backend = "CPU (OSMesa)"
            print(f"Renderer: {self._backend}")
        except Exception as e:
            print(f"OSMesa rendering unavailable: {e}")
            self._renderer = None

    def render(self, scene: pyrender.Scene, camera: DroneCamera
               ) -> Tuple[np.ndarray, np.ndarray]:
        """Render a frame. Returns (color_HxWx3_uint8, depth_HxW_float32).

        Temporarily adds the camera to the scene, renders, then removes it.
        """
        pr_camera = pyrender.IntrinsicsCamera(
            fx=camera.focal_length_mm / camera.sensor_width_mm * camera.width,
            fy=camera.focal_length_mm / camera.sensor_width_mm * camera.width,
            cx=camera.width / 2.0,
            cy=camera.height / 2.0,
            znear=camera.near,
            zfar=camera.far,
        )

        cam_pose = np.linalg.inv(camera.view_matrix)
        cam_node = scene.add(pr_camera, pose=cam_pose)

        try:
            color, depth = self._renderer.render(scene)
        finally:
            scene.remove_node(cam_node)

        return color, depth

    @property
    def backend(self) -> str:
        return self._backend

    def close(self):
        if self._renderer is not None:
            self._renderer.delete()
            self._renderer = None
