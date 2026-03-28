"""GroundTruthAnnotator — 2D bounding boxes from 3D projection + depth occlusion.

Replaces Isaac Sim's rep.AnnotatorRegistry.get_annotator("bounding_box_2d_tight").
"""
from typing import List, Dict

import numpy as np

from .camera import DroneCamera
from .scene import SceneBuilder


class GroundTruthAnnotator:
    def __init__(self, camera: DroneCamera, scene_builder: SceneBuilder):
        self.camera = camera
        self.scene = scene_builder

    def get_annotations(self, depth_buffer: np.ndarray = None) -> List[Dict]:
        """Compute 2D ground truth bounding boxes for all targets.

        Algorithm:
        1. Get 8 AABB corners per target in world space
        2. Project all corners to pixel coordinates via camera matrices
        3. Compute tight 2D bbox (min/max of visible projected corners)
        4. Clip to screen bounds
        5. Optionally check occlusion using depth buffer

        Returns list matching gt_data.json 'boxes' format.
        """
        targets = self.scene.get_targets()
        boxes = []

        for target in targets:
            corners = target["corners"]  # 8x3
            projected = self.camera.project_points(corners)  # 8x3 (px, py, depth)

            # Filter points in front of camera (depth > 0)
            visible_mask = projected[:, 2] > 0
            if not np.any(visible_mask):
                continue

            visible_pts = projected[visible_mask]
            px = visible_pts[:, 0]
            py = visible_pts[:, 1]
            depths = visible_pts[:, 2]

            # Tight 2D bbox
            x_min = int(np.clip(np.floor(np.min(px)), 0, self.camera.width - 1))
            y_min = int(np.clip(np.floor(np.min(py)), 0, self.camera.height - 1))
            x_max = int(np.clip(np.ceil(np.max(px)), 0, self.camera.width - 1))
            y_max = int(np.clip(np.ceil(np.max(py)), 0, self.camera.height - 1))

            # Skip degenerate boxes
            if x_max <= x_min or y_max <= y_min:
                continue

            # Occlusion check via depth buffer
            occ = 0.0
            if depth_buffer is not None:
                occ = self._compute_occlusion(visible_pts, depth_buffer)

            boxes.append({
                "x_min": x_min,
                "y_min": y_min,
                "x_max": x_max,
                "y_max": y_max,
                "label": target["label"],
                "occ": float(occ),
            })

        return boxes

    def _compute_occlusion(self, projected_pts: np.ndarray,
                           depth_buffer: np.ndarray) -> float:
        """Compute occlusion ratio by sampling depth buffer at projected corners.

        For each projected corner, compare rendered depth vs expected depth.
        If the rendered depth is significantly less, the corner is occluded by terrain.
        """
        h, w = depth_buffer.shape
        n_total = len(projected_pts)
        n_occluded = 0

        for i in range(n_total):
            px_x = int(np.clip(projected_pts[i, 0], 0, w - 1))
            px_y = int(np.clip(projected_pts[i, 1], 0, h - 1))
            expected_depth = projected_pts[i, 2]

            rendered_depth = depth_buffer[px_y, px_x]

            # pyrender returns 0.0 for background (no geometry)
            if rendered_depth <= 0:
                continue

            # Convert pyrender depth buffer to linear depth
            # pyrender depth is already linearized in world units
            # Object is occluded if rendered depth is significantly less
            if rendered_depth < expected_depth * 0.95:
                n_occluded += 1

        return n_occluded / max(n_total, 1)
