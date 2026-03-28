"""DroneCamera — virtual camera with heading+pitch control.

Ported from run_auto.py:280-320 (set_cam) and run_standalone.py:144-174.
Same gimbal-lock-safe rotation, same FOV math, OpenGL conventions.
"""
import numpy as np


class DroneCamera:
    def __init__(self, width: int = 640, height: int = 480,
                 focal_length_mm: float = 18.0, sensor_width_mm: float = 36.0,
                 near: float = 1.0, far: float = 50000000.0):
        self.width = width
        self.height = height
        self.focal_length_mm = focal_length_mm
        self.sensor_width_mm = sensor_width_mm
        self.near = near
        self.far = far

        # Horizontal FOV from focal length and sensor width
        self.hfov_rad = 2.0 * np.arctan(sensor_width_mm / (2.0 * focal_length_mm))
        self.hfov_deg = np.degrees(self.hfov_rad)

        # Vertical FOV derived from aspect ratio
        aspect = width / height
        self.vfov_rad = 2.0 * np.arctan(np.tan(self.hfov_rad / 2.0) / aspect)

        # View matrix (world-to-camera), set by set_pose()
        self._view_matrix = np.eye(4, dtype=np.float64)
        self._position = np.zeros(3, dtype=np.float64)

    def set_pose(self, position: np.ndarray, flight_dir: np.ndarray,
                 pitch_deg: float):
        """Build camera pose from drone position, flight direction, and pitch.

        Uses heading+pitch decomposition to avoid gimbal lock.
        Matches run_auto.py set_cam() exactly.
        """
        pos = np.asarray(position, dtype=np.float64)
        self._position = pos.copy()
        pitch_rad = np.radians(pitch_deg)

        # Horizontal forward (project flight_dir onto XZ plane)
        fwd_h = np.array([flight_dir[0], 0.0, flight_dir[2]], dtype=np.float64)
        norm = np.linalg.norm(fwd_h)
        if norm > 1e-9:
            fwd_h /= norm

        # Heading angle in XZ plane
        heading = np.arctan2(fwd_h[2], fwd_h[0])

        # Right vector: perpendicular to heading in XZ plane
        right = np.array([-np.sin(heading), 0.0, np.cos(heading)],
                         dtype=np.float64)

        # Forward vector: heading pitched down
        cos_p = np.cos(pitch_rad)
        sin_p = np.sin(pitch_rad)
        fwd = np.array([fwd_h[0] * cos_p, -sin_p, fwd_h[2] * cos_p],
                       dtype=np.float64)

        # Up = right x fwd (guaranteed orthogonal)
        up = np.cross(right, fwd)
        up_len = np.linalg.norm(up)
        if up_len > 1e-9:
            up /= up_len

        # Build view matrix (world-to-camera, OpenGL convention: camera looks -Z)
        # R = [right | up | -fwd] as rows, T = -R @ pos
        R = np.array([right, up, -fwd], dtype=np.float64)  # 3x3
        t = -R @ pos  # 3x1

        self._view_matrix = np.eye(4, dtype=np.float64)
        self._view_matrix[:3, :3] = R
        self._view_matrix[:3, 3] = t

    @property
    def view_matrix(self) -> np.ndarray:
        return self._view_matrix.copy()

    @property
    def position(self) -> np.ndarray:
        return self._position.copy()

    def get_projection_matrix(self) -> np.ndarray:
        """4x4 perspective projection matrix (OpenGL conventions)."""
        aspect = self.width / self.height
        fov_y = self.vfov_rad
        n, f = self.near, self.far

        t = np.tan(fov_y / 2.0) * n
        b = -t
        r = t * aspect
        l = -r

        P = np.zeros((4, 4), dtype=np.float64)
        P[0, 0] = 2.0 * n / (r - l)
        P[1, 1] = 2.0 * n / (t - b)
        P[0, 2] = (r + l) / (r - l)
        P[1, 2] = (t + b) / (t - b)
        P[2, 2] = -(f + n) / (f - n)
        P[2, 3] = -2.0 * f * n / (f - n)
        P[3, 2] = -1.0
        return P

    def project_points(self, world_points: np.ndarray) -> np.ndarray:
        """Project Nx3 world coordinates to Nx3 (pixel_x, pixel_y, depth).

        Returns pixel coordinates and camera-space depth for each point.
        Points behind the camera get depth <= 0.
        """
        pts = np.asarray(world_points, dtype=np.float64)
        N = pts.shape[0]

        # To homogeneous
        ones = np.ones((N, 1), dtype=np.float64)
        pts_h = np.hstack([pts, ones])  # Nx4

        # World to camera
        cam_pts = (self._view_matrix @ pts_h.T).T  # Nx4
        cam_z = cam_pts[:, 2]  # negative for points in front (OpenGL)

        # Project
        P = self.get_projection_matrix()
        clip = (P @ cam_pts.T).T  # Nx4

        # Perspective divide (avoid division by zero)
        w = clip[:, 3]
        w_safe = np.where(np.abs(w) > 1e-9, w, 1e-9)
        ndc = clip[:, :3] / w_safe[:, np.newaxis]

        # NDC to pixel: ndc.x in [-1,1] → [0, width], ndc.y → [0, height]
        px = (ndc[:, 0] * 0.5 + 0.5) * self.width
        py = (1.0 - (ndc[:, 1] * 0.5 + 0.5)) * self.height

        # Depth in camera space (positive = in front of camera)
        depth = -cam_z

        return np.column_stack([px, py, depth])

    def get_look_at(self) -> tuple:
        """Return (position, focal_point, up) for PyVista/VTK compatibility."""
        # Inverse of view matrix to get camera world-space axes
        R = self._view_matrix[:3, :3]
        # Forward in world space is -Z in camera, which is the third row negated
        fwd_world = -R[2, :]
        up_world = R[1, :]
        focal_point = self._position + fwd_world * 50000.0
        return self._position.tolist(), focal_point.tolist(), up_world.tolist()
