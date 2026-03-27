"""
Step 1: Build terrain mesh + texture from DEM + satellite GeoTIFFs.
Outputs: terrain_mesh.obj, terrain_texture.png, metadata.json

Usage:
  python build_terrain_mesh.py --dem path/to/dem.tif --sat path/to/sat.tif --lat 47.2 --lon 27.6
  python build_terrain_mesh.py  (uses defaults)

Then load terrain_mesh.obj in Isaac Sim and apply terrain_texture.png
"""
import rasterio
import numpy as np
from pyproj import Transformer
from PIL import Image
import json
import os
import argparse

# ============================================================
# CLI ARGUMENTS
# ============================================================
parser = argparse.ArgumentParser(description="Build terrain mesh from DEM + satellite GeoTIFFs")
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_SCRIPT_DIR)
parser.add_argument("--dem", default=os.path.join(_PROJECT_DIR, "GIS", "rasters_COP30", "output_hh.tif"), help="Path to DEM GeoTIFF (EPSG:4326)")
parser.add_argument("--sat", default=os.path.join(_PROJECT_DIR, "GIS", "iasi_esri_clipped.tif"), help="Path to satellite imagery GeoTIFF (EPSG:4326, RGB)")
parser.add_argument("--lat", type=float, default=47.21724592886579, help="POI latitude (center of scene, where target is placed)")
parser.add_argument("--lon", type=float, default=27.614609502715126, help="POI longitude")
parser.add_argument("--output", default=_SCRIPT_DIR, help="Output directory")
parser.add_argument("--max-vertices", type=int, default=15000, help="Max terrain vertices (auto-calculates subsample)")
args = parser.parse_args()

DEM_PATH = args.dem
SAT_PATH = args.sat
OUTPUT_DIR = args.output
POI_LAT = args.lat
POI_LON = args.lon
MAX_VERTICES = args.max_vertices

print("=" * 60)
print("  TERRAIN MESH BUILDER")
print("=" * 60)

# ============================================================
# 1. Read DEM
# ============================================================
print("\n[1/5] Reading DEM...")
with rasterio.open(DEM_PATH) as dem:
    elevation = dem.read(1).astype(np.float32)
    dem_transform = dem.transform
    dem_crs = dem.crs
    dem_bounds = dem.bounds
    dem_width = dem.width
    dem_height = dem.height

print(f"  Size: {dem_width}x{dem_height}")
print(f"  Elevation: {elevation.min():.1f}m - {elevation.max():.1f}m")
print(f"  Bounds: ({dem_bounds.left:.4f}, {dem_bounds.bottom:.4f}) - ({dem_bounds.right:.4f}, {dem_bounds.top:.4f})")
print(f"  CRS: {dem_crs}")

# Validate CRS
crs_str = str(dem_crs).upper()
if "4326" not in crs_str and "WGS" not in crs_str:
    print(f"  WARNING: DEM CRS is {dem_crs}, expected EPSG:4326. Results may be incorrect!")

# Validate POI is within DEM bounds
if not (dem_bounds.left <= POI_LON <= dem_bounds.right and dem_bounds.bottom <= POI_LAT <= dem_bounds.top):
    print(f"  ERROR: POI ({POI_LAT}, {POI_LON}) is outside DEM bounds!")
    print(f"  DEM covers: lat [{dem_bounds.bottom:.4f}, {dem_bounds.top:.4f}], lon [{dem_bounds.left:.4f}, {dem_bounds.right:.4f}]")
    import sys; sys.exit(1)

# ============================================================
# 2. Auto-calculate subsample and build mesh
# ============================================================
# Auto-subsample: target ~MAX_VERTICES vertices
total_pixels = dem_width * dem_height
SUBSAMPLE = max(1, int(np.sqrt(total_pixels / MAX_VERTICES)))
print(f"\n[2/5] Building mesh (auto subsample={SUBSAMPLE} for ~{MAX_VERTICES} max vertices)...")
elev_sub = elevation[::SUBSAMPLE, ::SUBSAMPLE]
rows, cols = elev_sub.shape
print(f"  Grid: {cols}x{rows} = {cols*rows} vertices")

# Convert pixel coords to lat/lon, then to local meters
# POI becomes origin (0, 0)
lat_per_pixel = (dem_bounds.top - dem_bounds.bottom) / dem_height * SUBSAMPLE
lon_per_pixel = (dem_bounds.right - dem_bounds.left) / dem_width * SUBSAMPLE

# Meters per degree at this latitude
m_per_deg_lat = 111320.0
m_per_deg_lon = 111320.0 * np.cos(np.radians(POI_LAT))

# Build vertices
vertices = []
uvs = []
for r in range(rows):
    for c in range(cols):
        # Geo coordinates
        lat = dem_bounds.top - r * lat_per_pixel
        lon = dem_bounds.left + c * lon_per_pixel

        # Local meters (POI = origin)
        east = (lon - POI_LON) * m_per_deg_lon
        north = (lat - POI_LAT) * m_per_deg_lat
        up = float(elev_sub[r, c])

        # Convert to cm, Y-up convention (OBJ/USD standard)
        # X = east, Y = up, Z = -north (south)
        vertices.append((east * 100, up * 100, -north * 100))

        # UV coordinates (0-1 range for texture mapping)
        u = c / (cols - 1)
        v = 1.0 - r / (rows - 1)  # Flip V (image Y is top-down)
        uvs.append((u, v))

print(f"  Vertices: {len(vertices)}")

# Build triangles (two per grid cell)
faces = []
for r in range(rows - 1):
    for c in range(cols - 1):
        idx = r * cols + c
        # Triangle 1
        faces.append((idx, idx + cols, idx + 1))
        # Triangle 2
        faces.append((idx + 1, idx + cols, idx + cols + 1))

print(f"  Triangles: {len(faces)}")

# ============================================================
# 3. Write OBJ mesh
# ============================================================
print("\n[3/5] Writing OBJ mesh...")
obj_path = os.path.join(OUTPUT_DIR, "terrain_mesh.obj")
mtl_path = os.path.join(OUTPUT_DIR, "terrain_mesh.mtl")

with open(obj_path, 'w') as f:
    f.write("# Terrain mesh from DEM\n")
    f.write(f"mtllib terrain_mesh.mtl\n")
    f.write(f"usemtl terrain_mat\n\n")

    for v in vertices:
        f.write(f"v {v[0]:.2f} {v[1]:.2f} {v[2]:.2f}\n")

    f.write("\n")
    for uv in uvs:
        f.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")

    f.write("\n")
    for face in faces:
        f0, f1, f2 = face[0]+1, face[1]+1, face[2]+1  # OBJ is 1-indexed
        f.write(f"f {f0}/{f0} {f1}/{f1} {f2}/{f2}\n")

with open(mtl_path, 'w') as f:
    f.write("newmtl terrain_mat\n")
    f.write("Ka 1.0 1.0 1.0\n")
    f.write("Kd 1.0 1.0 1.0\n")
    f.write("map_Kd terrain_texture.png\n")

print(f"  Saved: {obj_path}")
print(f"  Saved: {mtl_path}")

# ============================================================
# 4. Extract satellite texture
# ============================================================
print("\n[4/5] Extracting satellite texture...")
with rasterio.open(SAT_PATH) as sat:
    sat_bounds = sat.bounds
    sat_crs_str = str(sat.crs).upper()
    print(f"  Satellite bounds: ({sat_bounds.left:.4f}, {sat_bounds.bottom:.4f}) - ({sat_bounds.right:.4f}, {sat_bounds.top:.4f})")
    print(f"  Satellite size: {sat.width}x{sat.height}")
    print(f"  Satellite CRS: {sat.crs}")

    if "4326" not in sat_crs_str and "WGS" not in sat_crs_str:
        print(f"  WARNING: Satellite CRS is {sat.crs}, expected EPSG:4326!")

    # Check satellite covers DEM extent
    if sat_bounds.left > dem_bounds.left or sat_bounds.right < dem_bounds.right or \
       sat_bounds.bottom > dem_bounds.bottom or sat_bounds.top < dem_bounds.top:
        print("  WARNING: Satellite does not fully cover DEM extent! Texture may have gaps.")

    # Read a window matching the DEM bounds
    from rasterio.windows import from_bounds
    window = from_bounds(
        dem_bounds.left, dem_bounds.bottom,
        dem_bounds.right, dem_bounds.top,
        sat.transform
    )

    # Read RGB bands within the window
    rgb = sat.read([1, 2, 3], window=window)
    print(f"  Clipped window: {rgb.shape}")

    # Transpose to HxWxC and resize to reasonable texture size
    rgb = np.transpose(rgb, (1, 2, 0))

    # Resize to max 4096x4096 for performance
    max_tex = 4096
    h, w = rgb.shape[:2]
    if h > max_tex or w > max_tex:
        scale = max_tex / max(h, w)
        new_h, new_w = int(h * scale), int(w * scale)
        img = Image.fromarray(rgb)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        rgb = np.array(img)
        print(f"  Resized to: {new_w}x{new_h}")

tex_path = os.path.join(OUTPUT_DIR, "terrain_texture.png")
Image.fromarray(rgb).save(tex_path)
print(f"  Saved: {tex_path}")

# ============================================================
# 5. Write metadata
# ============================================================
print("\n[5/5] Writing metadata...")

# POI ground height
poi_row = int((dem_bounds.top - POI_LAT) / (dem_bounds.top - dem_bounds.bottom) * dem_height)
poi_col = int((POI_LON - dem_bounds.left) / (dem_bounds.right - dem_bounds.left) * dem_width)
poi_row = np.clip(poi_row, 0, dem_height - 1)
poi_col = np.clip(poi_col, 0, dem_width - 1)
poi_elevation = float(elevation[poi_row, poi_col])

metadata = {
    "poi_lat": POI_LAT,
    "poi_lon": POI_LON,
    "poi_elevation_m": poi_elevation,
    "poi_local_x_cm": 0.0,             # East (POI = origin)
    "poi_local_y_cm": poi_elevation * 100,  # Up (Y-up convention)
    "poi_local_z_cm": 0.0,             # South (POI = origin)
    "dem_bounds": {
        "left": dem_bounds.left,
        "bottom": dem_bounds.bottom,
        "right": dem_bounds.right,
        "top": dem_bounds.top,
    },
    "mesh_vertices": len(vertices),
    "mesh_triangles": len(faces),
    "subsample": SUBSAMPLE,
    "terrain_extent_m": {
        "x": (dem_bounds.right - dem_bounds.left) * m_per_deg_lon,
        "y": (dem_bounds.top - dem_bounds.bottom) * m_per_deg_lat,
    },
}

meta_path = os.path.join(OUTPUT_DIR, "metadata.json")
with open(meta_path, 'w') as f:
    json.dump(metadata, f, indent=2)
print(f"  Saved: {meta_path}")
print(f"  POI elevation: {poi_elevation:.1f}m")
print(f"  Terrain extent: {metadata['terrain_extent_m']['x']:.0f}m x {metadata['terrain_extent_m']['y']:.0f}m")

print("\n" + "=" * 60)
print("  DONE! Files ready for Isaac Sim import:")
print(f"    {obj_path}")
print(f"    {tex_path}")
print(f"    {meta_path}")
print(f"\n  Next: Load in Isaac Sim via asset importer or Script Editor")
print("=" * 60)
