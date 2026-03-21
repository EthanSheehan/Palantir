import unittest

from src.python.vision.coordinate_transformer import pixel_to_gps


class TestVisionPipeline(unittest.TestCase):
    def test_nadir_projection(self):
        """
        Looking straight down at the center of the image should return the drone's position.
        """
        drone_lat, drone_lon = 51.4545, -2.5879
        lat, lon = pixel_to_gps(
            pixel_x=320,
            pixel_y=240,
            image_width=640,
            image_height=480,
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            drone_alt=100.0,
            gimbal_pitch=-90.0,
            gimbal_yaw=0.0,
        )
        self.assertAlmostEqual(lat, drone_lat, places=4)
        self.assertAlmostEqual(lon, drone_lon, places=4)

    def test_offset_projection(self):
        """
        Verification of basic offset direction.
        At yaw 0 (North), pixel above center should have higher latitude.
        """
        drone_lat, drone_lon = 51.4545, -2.5879
        lat, lon = pixel_to_gps(
            pixel_x=320,
            pixel_y=100,  # Above center
            image_width=640,
            image_height=480,
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            drone_alt=100.0,
            gimbal_pitch=-90.0,
            gimbal_yaw=0.0,
        )
        self.assertGreater(lat, drone_lat)
        self.assertAlmostEqual(lon, drone_lon, places=4)


if __name__ == "__main__":
    unittest.main()
