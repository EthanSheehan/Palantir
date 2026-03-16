"""
Asset Registry – a simulated in-memory registry of available effectors.

In production this would be backed by a real-time database or ISR link.
Each entry represents a military effector (kinetic **or** non-kinetic) with
its current position, readiness status, and performance characteristics.
"""

from schemas.ontology import Effector

# ---------------------------------------------------------------------------
# Static sample assets used for development / demo.  Replace with DB queries.
# ---------------------------------------------------------------------------
ASSET_REGISTRY: list[dict] = [
    {
        "effector": Effector(
            effector_id="F35-ALPHA-01",
            name="F-35A Lightning II (Alpha)",
            effector_type="Kinetic",
            status="Available",
        ),
        "lat": 33.50,
        "lon": 44.40,
        "pk_rating": 0.95,
        "cost_index": 8.5,          # relative cost 1-10
        "speed_kmh": 1_960.0,
    },
    {
        "effector": Effector(
            effector_id="HIMARS-02",
            name="HIMARS Battery Bravo",
            effector_type="Kinetic",
            status="Available",
        ),
        "lat": 33.30,
        "lon": 44.20,
        "pk_rating": 0.88,
        "cost_index": 5.0,
        "speed_kmh": 0.0,           # rocket flight speed handled differently
        "max_range_km": 300.0,
        "rocket_flight_time_min": 3.5,
    },
    {
        "effector": Effector(
            effector_id="MQ9-REAPER-03",
            name="MQ-9 Reaper (Viper 3)",
            effector_type="Kinetic",
            status="Available",
        ),
        "lat": 33.45,
        "lon": 44.55,
        "pk_rating": 0.80,
        "cost_index": 3.0,
        "speed_kmh": 480.0,
    },
    {
        "effector": Effector(
            effector_id="CYBER-TEAM-04",
            name="Cyber Effects Team Delta",
            effector_type="Non-Kinetic",
            status="Available",
        ),
        "lat": 0.0,                 # location-agnostic
        "lon": 0.0,
        "pk_rating": 0.60,
        "cost_index": 1.0,
        "speed_kmh": 0.0,           # instantaneous
        "time_to_effect_min": 0.5,
    },
    {
        "effector": Effector(
            effector_id="STRYKER-05",
            name="Stryker ICV (Sabre 5)",
            effector_type="Kinetic",
            status="Available",
        ),
        "lat": 33.35,
        "lon": 44.30,
        "pk_rating": 0.70,
        "cost_index": 2.0,
        "speed_kmh": 97.0,
    },
]


def get_available_effectors() -> list[dict]:
    """Return all effectors currently marked as Available."""
    return [a for a in ASSET_REGISTRY if a["effector"].status == "Available"]
