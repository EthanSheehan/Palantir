"""
Download DEM + Satellite imagery for multiple test locations.
No API keys needed — uses dem-stitcher (AWS) + Planetary Computer (Microsoft).

Usage:
  python download_test_data.py
  python download_test_data.py --locations san_francisco swiss_alps
"""
import os
import argparse
import numpy as np

OUTPUT_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "GIS DATA")

LOCATIONS = {
    "san_francisco": {
        "name": "San Francisco",
        "lat": 37.78, "lon": -122.42,
        "bbox": [-122.48, 37.72, -122.36, 37.82],  # W, S, E, N
        "desc": "Urban + water + hills (~13km x 11km)",
    },
    "swiss_alps": {
        "name": "Swiss Alps (Zermatt / Matterhorn)",
        "lat": 46.02, "lon": 7.75,
        "bbox": [7.65, 45.97, 7.85, 46.07],
        "desc": "Steep mountain terrain (~15km x 11km)",
    },
    "dubai": {
        "name": "Dubai",
        "lat": 25.20, "lon": 55.27,
        "bbox": [55.20, 25.15, 55.34, 25.25],
        "desc": "Flat desert + coast (~14km x 11km)",
    },
    "tokyo": {
        "name": "Tokyo Bay",
        "lat": 35.65, "lon": 139.77,
        "bbox": [139.70, 35.60, 139.84, 35.70],
        "desc": "Dense urban + coastline (~12km x 11km)",
    },
}

parser = argparse.ArgumentParser()
parser.add_argument("--locations", nargs="+", default=list(LOCATIONS.keys()),
                    choices=list(LOCATIONS.keys()), help="Which locations to download")
args = parser.parse_args()


def download_dem(loc_key, loc, out_dir):
    """Download Copernicus GLO-30 DEM via dem-stitcher (AWS, no auth)."""
    from dem_stitcher import stitch_dem
    import rasterio

    dem_path = os.path.join(out_dir, "dem.tif")
    if os.path.exists(dem_path):
        print(f"    DEM already exists: {dem_path}")
        return dem_path

    print(f"    Downloading Copernicus DEM 30m...")
    X, profile = stitch_dem(loc["bbox"], dem_name='glo_30')

    with rasterio.open(dem_path, 'w', **profile) as ds:
        ds.write(X, 1)

    print(f"    DEM saved: {dem_path} ({os.path.getsize(dem_path) / 1024:.0f} KB)")
    return dem_path


def download_satellite(loc_key, loc, out_dir):
    """Download Sentinel-2 RGB via AWS Earth Search + rasterio warp (no auth)."""
    from pystac_client import Client
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    from rasterio.transform import from_bounds as tfm_from_bounds

    sat_path = os.path.join(out_dir, "satellite.tif")
    if os.path.exists(sat_path):
        print(f"    Satellite already exists: {sat_path}")
        return sat_path

    print(f"    Searching Sentinel-2 imagery (low cloud)...")
    catalog = Client.open("https://earth-search.aws.element84.com/v1")

    bbox = loc["bbox"]
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime="2023-01-01/2025-12-31",
        query={"eo:cloud_cover": {"lt": 15}},
        max_items=10,
    )
    items = sorted(search.items(), key=lambda i: i.properties["eo:cloud_cover"])

    if not items:
        print(f"    ERROR: No Sentinel-2 images found for {loc['name']}!")
        return None

    item = items[0]
    cloud = item.properties["eo:cloud_cover"]
    date = item.properties["datetime"][:10]
    print(f"    Best image: {date}, cloud cover: {cloud:.1f}%")

    # Use TCI (True Color Image) or visual asset
    asset_key = "visual" if "visual" in item.assets else "tci"
    href = item.assets[asset_key].href
    print(f"    Downloading {asset_key} band from: ...{href[-60:]}")

    # Read, reproject to EPSG:4326, clip to bbox
    out_w, out_h = 2048, 2048
    dst_transform = tfm_from_bounds(*bbox, out_w, out_h)
    dst_crs = 'EPSG:4326'

    with rasterio.open(href) as src:
        dst_data = np.zeros((3, out_h, out_w), dtype=np.uint8)
        for band_idx in range(1, min(4, src.count + 1)):
            reproject(
                source=rasterio.band(src, band_idx),
                destination=dst_data[band_idx - 1],
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=dst_transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear,
            )

    profile = dict(
        driver='GTiff', dtype='uint8',
        width=out_w, height=out_h, count=3,
        crs=dst_crs, transform=dst_transform,
        compress='deflate',
    )
    with rasterio.open(sat_path, 'w', **profile) as dst:
        dst.write(dst_data)

    size_mb = os.path.getsize(sat_path) / 1024 / 1024
    print(f"    Satellite saved: {sat_path} ({size_mb:.1f} MB, {out_w}x{out_h})")
    return sat_path


# ============================================================
# MAIN
# ============================================================
print("=" * 60)
print("  GIS TEST DATA DOWNLOADER")
print("=" * 60)

for loc_key in args.locations:
    loc = LOCATIONS[loc_key]
    out_dir = os.path.join(OUTPUT_BASE, loc_key)
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"  {loc['name']} ({loc['desc']})")
    print(f"  Center: {loc['lat']}, {loc['lon']}")
    print(f"  BBox: {loc['bbox']}")
    print(f"  Output: {out_dir}")
    print(f"{'='*50}")

    # Download DEM
    print(f"\n  [DEM]")
    try:
        dem_path = download_dem(loc_key, loc, out_dir)
    except Exception as e:
        print(f"    DEM ERROR: {e}")
        dem_path = None

    # Download satellite
    print(f"\n  [SATELLITE]")
    try:
        sat_path = download_satellite(loc_key, loc, out_dir)
    except Exception as e:
        print(f"    SATELLITE ERROR: {e}")
        sat_path = None

    # Write location metadata
    meta = {
        "name": loc["name"],
        "lat": loc["lat"],
        "lon": loc["lon"],
        "bbox": loc["bbox"],
        "dem": os.path.basename(dem_path) if dem_path else None,
        "satellite": os.path.basename(sat_path) if sat_path else None,
        "desc": loc["desc"],
    }
    meta_path = os.path.join(out_dir, "location.json")
    import json
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

    status = "OK" if dem_path and sat_path else "PARTIAL"
    print(f"\n  Status: {status}")

print(f"\n{'='*60}")
print("  DONE! Test data saved to:")
print(f"  {OUTPUT_BASE}")
print()
print("  To run pipeline on any location:")
print('  C:\\isaac-sim\\python.bat run_auto.py --dem "GIS DATA\\san_francisco\\dem.tif" --sat "GIS DATA\\san_francisco\\satellite.tif" --lat 37.78 --lon -122.42')
print(f"{'='*60}")
