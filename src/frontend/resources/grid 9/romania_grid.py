import math
from typing import Dict, List, Tuple

def is_point_in_polygon(x: float, y: float, polygon: List[Tuple[float, float]]) -> bool:
    """Ray casting algorithm for point in polygon."""
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

class GridZone:
    def __init__(self, x_idx: int, y_idx: int, lon: float, lat: float, width_deg: float, height_deg: float):
        self.id = (x_idx, y_idx)
        self.lon = lon
        self.lat = lat
        self.width_deg = width_deg
        self.height_deg = height_deg
        
        # Macro state variables equivalent to previous implementation
        self.base_lambda = 0.1
        self.demand_rate = self.base_lambda
        self.queue = 0
        self.uav_count = 0
        self.imbalance = 0.0
        
        # Fast graph edge traversal for adjacent zones
        self.neighbors: List['GridZone'] = []

class RomaniaMacroGrid:
    def __init__(self):
        # Rough bounding box of Romania
        self.MIN_LON = 20.2
        self.MAX_LON = 29.8
        self.MIN_LAT = 43.6
        self.MAX_LAT = 48.3
        
        # Approximate center of Romania for projection calculation
        # 1 deg Lat = ~111.32 km.
        # 50x50 grid over Romania
        # Lat range: 48.3 - 43.6 = 4.7 deg. 4.7 / 50 = 0.094
        self.CELL_DEG_LAT = 0.094
        
        # Lon range: 29.8 - 20.2 = 9.6 deg. 9.6 / 50 = 0.192
        self.CELL_DEG_LON = 0.192
        
        # Simplified Polygon of Romania (Longitude, Latitude)
        # Sourced from accurate low-res GeoJSON boundaries
        self.ROMANIA_POLYGON = [
            (22.711, 47.882),
            (23.142, 48.096),
            (23.761, 47.986),
            (24.402, 47.982),
            (24.866, 47.738),
            (25.208, 47.891),
            (25.946, 47.987),
            (26.197, 48.221),
            (26.619, 48.221),
            (26.924, 48.123),
            (27.234, 47.827),
            (27.551, 47.405),
            (28.128, 46.81),
            (28.16, 46.372),
            (28.054, 45.945),
            (28.234, 45.488),
            (28.68, 45.304),
            (29.15, 45.465),
            (29.603, 45.293),
            (29.627, 45.035),
            (29.142, 44.82),
            (28.838, 44.914),
            (28.558, 43.707),
            (27.97, 43.812),
            (27.242, 44.176),
            (26.065, 43.943),
            (25.569, 43.688),
            (24.101, 43.741),
            (23.332, 43.897),
            (22.945, 43.824),
            (22.657, 44.235),
            (22.474, 44.409),
            (22.706, 44.578),
            (22.459, 44.703),
            (22.145, 44.478),
            (21.562, 44.769),
            (21.484, 45.181),
            (20.874, 45.416),
            (20.762, 45.735),
            (20.22, 46.127),
            (21.022, 46.316),
            (21.627, 46.994),
            (22.1, 47.672),
            (22.711, 47.882),
        ]
        
        self.zones: Dict[Tuple[int, int], GridZone] = {}
        self.flow_accum: Dict[Tuple[int, int], Dict[Tuple[int, int], float]] = {}
        
        self.K_GAIN = 0.3
        self.MU_CAPACITY_FACTOR = 10.0
        
        self._build_grid()
        
    def _build_grid(self):
        """Creates the grid zones that fall within the bounds of the country polygon."""
        width_deg = self.MAX_LON - self.MIN_LON
        height_deg = self.MAX_LAT - self.MIN_LAT
        
        num_cols = math.ceil(width_deg / self.CELL_DEG_LON)
        num_rows = math.ceil(height_deg / self.CELL_DEG_LAT)
        
        # 1. Generate Filtered Zones
        for x in range(num_cols):
            for y in range(num_rows):
                lon = self.MIN_LON + (x + 0.5) * self.CELL_DEG_LON
                lat = self.MIN_LAT + (y + 0.5) * self.CELL_DEG_LAT
                
                # Check mapping
                if is_point_in_polygon(lon, lat, self.ROMANIA_POLYGON):
                    zone = GridZone(x, y, lon, lat, self.CELL_DEG_LON, self.CELL_DEG_LAT)
                    self.zones[(x, y)] = zone
                    
                    self.flow_accum[(x, y)] = {}
                    
        # 2. Build Efficient Adjacency Graph (only existing valid neighbors)
        # This graph topology replaces the inefficient O(N*M) continuous edge-checking from before.
        for (x, y), zone in self.zones.items():
            potential_neighbors = [
                (x+1, y), (x-1, y), 
                (x, y+1), (x, y-1)
            ]
            for nx, ny in potential_neighbors:
                if (nx, ny) in self.zones:
                    neighbor_zone = self.zones[(nx, ny)]
                    zone.neighbors.append(neighbor_zone)
                    # Initialize flow accumulator
                    self.flow_accum[(x, y)][(nx, ny)] = 0.0

    def get_zone_at(self, lon: float, lat: float) -> GridZone:
        """Finds the closest valid zone for a given geographic lon/lat coordinate."""
        x = math.floor((lon - self.MIN_LON) / self.CELL_DEG_LON)
        y = math.floor((lat - self.MIN_LAT) / self.CELL_DEG_LAT)
        if (x, y) in self.zones:
            return self.zones[(x, y)]
        return None

    def calculate_macro_flow(self, dt_sec: float) -> List[Dict]:
        """
        Calculates imbalance gradients and required flow between adjacent country sectors.
        Returns a list of dispatch instruction metadata to rebalance the macro grid.
        """
        # 1. Update Imbalances for active zones
        for zone in self.zones.values():
            capacity = self.MU_CAPACITY_FACTOR * zone.uav_count
            zone.imbalance = capacity - zone.queue

        # 2. Compute Flow Dispatches using the direct graph edge connections
        dispatches = []
        for (x, y), zone_r in self.zones.items():
            for zone_s in zone_r.neighbors:
                nx, ny = zone_s.id
                
                # Proportional flow gradient: from r to s
                u_rs = self.K_GAIN * (zone_r.imbalance - zone_s.imbalance)
                
                if u_rs > 0:
                    self.flow_accum[(x, y)][(nx, ny)] += u_rs * dt_sec
                    
                    if self.flow_accum[(x, y)][(nx, ny)] >= 1.0:
                        count = int(self.flow_accum[(x, y)][(nx, ny)])
                        self.flow_accum[(x, y)][(nx, ny)] -= count
                        
                        # In the real simulation, ensure zone_r has enough idle UAVs here
                        dispatches.append({
                            "source_id": (x, y),
                            "target_id": (nx, ny),
                            "count": count,
                            "source_coord": (zone_r.lon, zone_r.lat),
                            "target_coord": (zone_s.lon, zone_s.lat),
                        })
                        
        return dispatches
