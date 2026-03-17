import tempfile
import textwrap
from pathlib import Path

import pytest
import yaml

from theater_loader import (
    Bounds,
    TheaterConfig,
    TheaterValidationError,
    list_theaters,
    load_theater,
)


# ---------------------------------------------------------------------------
# Loading each theater
# ---------------------------------------------------------------------------

class TestLoadTheaters:
    def test_load_romania(self):
        config = load_theater("romania")
        assert config.name == "Romania Eastern Flank"
        assert config.blue_force.uavs.count == 20
        assert config.blue_force.uavs.type == "MQ-9"
        assert len(config.red_force.units) == 8
        assert config.bounds.min_lon == pytest.approx(20.26)
        assert config.environment.terrain == "mixed"

    def test_load_south_china_sea(self):
        config = load_theater("south_china_sea")
        assert config.name == "South China Sea Maritime Operations"
        assert config.blue_force.uavs.count == 15
        assert config.blue_force.uavs.type == "P-8_Poseidon"
        assert config.environment.terrain == "maritime"
        unit_types = {u.type for u in config.red_force.units}
        assert "DESTROYER" in unit_types
        assert "SUBMARINE" in unit_types

    def test_load_baltic(self):
        config = load_theater("baltic")
        assert config.name == "Baltic States Defense"
        assert config.blue_force.uavs.count == 12
        assert config.grid.cols == 30
        assert config.grid.rows == 30
        unit_types = {u.type for u in config.red_force.units}
        assert "APC" in unit_types
        assert "MBT" in unit_types


# ---------------------------------------------------------------------------
# Listing theaters
# ---------------------------------------------------------------------------

class TestListTheaters:
    def test_list_theaters_returns_all(self):
        theaters = list_theaters()
        assert "romania" in theaters
        assert "south_china_sea" in theaters
        assert "baltic" in theaters

    def test_list_theaters_sorted(self):
        theaters = list_theaters()
        assert theaters == sorted(theaters)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_invalid_theater_name_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            load_theater("nonexistent")

    def test_missing_required_field_raises_validation_error(self, tmp_path, monkeypatch):
        bad_yaml = tmp_path / "broken.yaml"
        bad_yaml.write_text(yaml.dump({"name": "Test"}))
        import theater_loader
        monkeypatch.setattr(theater_loader, "THEATERS_DIR", tmp_path)
        with pytest.raises(TheaterValidationError, match="Missing required key"):
            load_theater("broken")

    def test_invalid_bounds_min_greater_than_max(self, tmp_path, monkeypatch):
        data = {
            "name": "Bad Bounds",
            "description": "test",
            "bounds": {"min_lon": 30.0, "max_lon": 20.0, "min_lat": 40.0, "max_lat": 50.0},
            "grid": {"cols": 10, "rows": 10},
            "blue_force": {
                "uavs": {
                    "count": 5,
                    "type": "MQ-9",
                    "base_lon": 25.0,
                    "base_lat": 45.0,
                    "default_altitude_m": 3000,
                    "sensor_type": "EO_IR",
                    "endurance_hours": 24,
                }
            },
            "red_force": {
                "units": [{"type": "SAM", "count": 1, "behavior": "stationary"}]
            },
            "environment": {"weather": "clear", "time_of_day": "day", "terrain": "mixed"},
        }
        bad_yaml = tmp_path / "bad_bounds.yaml"
        bad_yaml.write_text(yaml.dump(data))
        import theater_loader
        monkeypatch.setattr(theater_loader, "THEATERS_DIR", tmp_path)
        with pytest.raises(TheaterValidationError, match="min_lon.*must be less than.*max_lon"):
            load_theater("bad_bounds")

    def test_invalid_bounds_lat_min_greater_than_max(self, tmp_path, monkeypatch):
        data = {
            "name": "Bad Lat Bounds",
            "description": "test",
            "bounds": {"min_lon": 20.0, "max_lon": 30.0, "min_lat": 50.0, "max_lat": 40.0},
            "grid": {"cols": 10, "rows": 10},
            "blue_force": {
                "uavs": {
                    "count": 5,
                    "type": "MQ-9",
                    "base_lon": 25.0,
                    "base_lat": 45.0,
                    "default_altitude_m": 3000,
                    "sensor_type": "EO_IR",
                    "endurance_hours": 24,
                }
            },
            "red_force": {
                "units": [{"type": "SAM", "count": 1, "behavior": "stationary"}]
            },
            "environment": {"weather": "clear", "time_of_day": "day", "terrain": "mixed"},
        }
        bad_yaml = tmp_path / "bad_lat.yaml"
        bad_yaml.write_text(yaml.dump(data))
        import theater_loader
        monkeypatch.setattr(theater_loader, "THEATERS_DIR", tmp_path)
        with pytest.raises(TheaterValidationError, match="min_lat.*must be less than.*max_lat"):
            load_theater("bad_lat")

    def test_zero_uav_count_raises_validation_error(self, tmp_path, monkeypatch):
        data = {
            "name": "Zero UAVs",
            "description": "test",
            "bounds": {"min_lon": 20.0, "max_lon": 30.0, "min_lat": 40.0, "max_lat": 50.0},
            "grid": {"cols": 10, "rows": 10},
            "blue_force": {
                "uavs": {
                    "count": 0,
                    "type": "MQ-9",
                    "base_lon": 25.0,
                    "base_lat": 45.0,
                    "default_altitude_m": 3000,
                    "sensor_type": "EO_IR",
                    "endurance_hours": 24,
                }
            },
            "red_force": {
                "units": [{"type": "SAM", "count": 1, "behavior": "stationary"}]
            },
            "environment": {"weather": "clear", "time_of_day": "day", "terrain": "mixed"},
        }
        bad_yaml = tmp_path / "zero_uavs.yaml"
        bad_yaml.write_text(yaml.dump(data))
        import theater_loader
        monkeypatch.setattr(theater_loader, "THEATERS_DIR", tmp_path)
        with pytest.raises(TheaterValidationError, match="count must be positive"):
            load_theater("zero_uavs")


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_theater_config_is_frozen(self):
        config = load_theater("romania")
        with pytest.raises(AttributeError):
            config.name = "Modified"

    def test_bounds_is_frozen(self):
        config = load_theater("romania")
        with pytest.raises(AttributeError):
            config.bounds.min_lon = 999.0

    def test_red_force_units_is_tuple(self):
        config = load_theater("romania")
        assert isinstance(config.red_force.units, tuple)


# ---------------------------------------------------------------------------
# Required fields present
# ---------------------------------------------------------------------------

class TestRequiredFields:
    def test_all_required_fields_present_romania(self):
        config = load_theater("romania")
        assert config.name
        assert config.description
        assert config.bounds.min_lon is not None
        assert config.bounds.max_lon is not None
        assert config.bounds.min_lat is not None
        assert config.bounds.max_lat is not None
        assert config.grid.cols > 0
        assert config.grid.rows > 0
        assert config.blue_force.uavs.count > 0
        assert config.blue_force.uavs.type
        assert len(config.red_force.units) > 0
        assert config.environment.weather
        assert config.environment.time_of_day
        assert config.environment.terrain

    def test_red_units_have_required_fields(self):
        for theater_name in list_theaters():
            config = load_theater(theater_name)
            for unit in config.red_force.units:
                assert unit.type
                assert unit.count > 0
                assert unit.behavior
