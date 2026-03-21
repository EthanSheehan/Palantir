import math
from typing import Tuple

import structlog

logger = structlog.get_logger()


def pixel_to_gps(
    pixel_x: int,
    pixel_y: int,
    image_width: int,
    image_height: int,
    drone_lat: float,
    drone_lon: float,
    drone_alt: float,
    gimbal_pitch: float,  # Degrees, negative is look down
    gimbal_yaw: float,  # Degrees, 0 is North
    hfov: float = 60.0,  # Horizontal Field of View in degrees
) -> Tuple[float, float]:
    """
    Translates pixel coordinates (x, y) to GPS coordinates (Lat, Long).

    This is a simplified projection assuming flat earth for local coordinates.
    """
    # 1. Convert degrees to radians
    pitch_rad = math.radians(gimbal_pitch)
    yaw_rad = math.radians(gimbal_yaw)
    hfov_rad = math.radians(hfov)

    # 2. Calculate Ground Sample Distance (GSD) or scale
    # Aspect ratio
    aspect_ratio = image_width / image_height
    vfov_rad = 2 * math.atan(math.tan(hfov_rad / 2) / aspect_ratio)

    # Distance to ground at center (assuming look down near nadir)
    # If pitch is -90 (vertical), dist = alt
    if gimbal_pitch > -1:  # Avoid division by zero if looking at horizon
        gimbal_pitch = -1

    dist_at_center = drone_alt / math.sin(abs(pitch_rad))

    # Normalized coordinates from center (-0.5 to 0.5)
    norm_x = (pixel_x / image_width) - 0.5
    norm_y = 0.5 - (pixel_y / image_height)  # Inverted because y is down in image

    # Angle offsets from center
    angle_x = norm_x * hfov_rad
    angle_y = norm_y * vfov_rad

    # Local offsets in meters (simplified)
    # This is a linear approximation valid for low FOVs and near-nadir angles
    offset_x_local = dist_at_center * math.tan(angle_x)
    offset_y_local = dist_at_center * math.tan(angle_y) / math.cos(math.radians(gimbal_pitch + 90))

    # Rotate by gimbal yaw
    # 0 deg is North (+y), 90 deg is East (+x)
    offset_e = offset_x_local * math.cos(yaw_rad) + offset_y_local * math.sin(yaw_rad)
    offset_n = -offset_x_local * math.sin(yaw_rad) + offset_y_local * math.cos(yaw_rad)

    # 3. Convert meter offsets to Lat/Long
    # Constants
    EARTH_RADIUS = 6378137.0

    delta_lat = (offset_n / EARTH_RADIUS) * (180 / math.pi)
    delta_lon = (offset_e / (EARTH_RADIUS * math.cos(math.radians(drone_lat)))) * (180 / math.pi)

    return drone_lat + delta_lat, drone_lon + delta_lon


if __name__ == "__main__":
    # Test case: 100m alt, looking straight down (-90 pitch), center pixel
    # Expected: drone GPS
    lat, lon = pixel_to_gps(320, 240, 640, 480, 51.4545, -2.5879, 100, -90, 0)
    logger.info("test_center_pixel", lat=lat, lon=lon)

    # Test case: center-right pixel
    lat, lon = pixel_to_gps(640, 240, 640, 480, 51.4545, -2.5879, 100, -90, 0)
    logger.info("test_right_edge", lat=lat, lon=lon)
