from pathlib import Path

content = """# SynTerra local import troubleshooting notes (Iași / Romania)

## Goal
Generate a local SynTerra tile in Unreal using:
- a custom **imagery raster**
- a custom **DEM**
for the Iași AOI near:

- **Latitude:** `47.21724592886579`
- **Longitude:** `27.614609502715126`

## Initial objective
Use higher-resolution Europe imagery than SynTerra's default low-resolution Europe option, by manually supplying:
- **Imagery**
- **Elevation / DEM**

## What SynTerra expects
For local uploads, the inputs need to be:

- **GeoTIFF**
- **EPSG:4326 (WGS84)**

### Practical meaning
- A normal JPG/PNG/screenshot is **not enough**
- The raster must be **georeferenced**
- Imagery and DEM should cover the **same AOI**

---

## Data sourcing decisions

### Imagery
Tried using:
- **ANCPI orthophoto services** for Romania

Problem:
- ANCPI services appeared fragmented / awkward to use for a quick export workflow

Fallback used:
- **ESRI Satellite / World Imagery** through QGIS

### DEM
Used:
- **OpenTopography / Copernicus DEM**

This part worked well and was straightforward.

---

## Bounding boxes used

### Center point
- `47.21724592886579, 27.614609502715126`

### 10 km × 10 km bounding box
Used in OpenTopography and QGIS:

- **Xmin:** `27.548481398657955`
- **Ymin:** `47.17233037011624`
- **Xmax:** `27.680737606772297`
- **Ymax:** `47.262161487615344`

Later, the **DEM extent** became the reference truth:

- **Xmin:** `27.5484722111111182`
- **Ymin:** `47.1726388999999955`
- **Xmax:** `27.6806944333333398`
- **Ymax:** `47.2623611222222166`

---

## Problems encountered

## 1. Confusion over what SynTerra needs
### Problem
Unclear whether only imagery was needed, whether DEM was optional, and whether georeferencing mattered.

### Resolution
Conclusion:
- **Imagery is the texture**
- **DEM is the terrain shape**
- For proper terrain generation, **both are needed**
- Inputs must be **georeferenced GeoTIFFs in EPSG:4326**

---

## 2. ANCPI orthophoto services were awkward / fragmented
### Problem
ANCPI services did not behave like one clean seamless nationwide basemap. Coverage looked fragmented.

### Resolution
For speed, switched to:
- **ESRI Satellite in QGIS**

This was easier for testing, even though it is not ideal for a final production workflow.

---

## 3. Difficulty adding basemap imagery in QGIS
### Problem
Needed a fast way to bring imagery into QGIS.

### Resolution
Used either:
- **QuickMapServices**, or
- direct **XYZ Tiles** connection for ESRI Satellite

---

## 4. Wrong assumption that a rendered map export would automatically be valid for SynTerra
### Problem
A TIFF exported from QGIS can still be wrong for SynTerra, even if it looks visually correct in QGIS.

### Resolution
Needed to verify for every file:
- **GeoTIFF**
- **EPSG:4326**
- correct **band count**
- proper **extent**

---

## 5. Imagery projection error in SynTerra
### Problem
SynTerra initially complained that the imagery had an incorrect layer projection.

### Resolution
Confirmed that:
- the imagery raster itself had to be in **EPSG:4326**
- not just the QGIS project

Eventually obtained a valid imagery file with:
- **GeoTIFF**
- **EPSG:4326**
- **3 bands**
- valid georeferencing

---

## 6. Tried warping the live ESRI XYZ layer directly
### Problem
Attempted to run **Warp (reproject)** directly on the ESRI XYZ tile source.

### Symptom
GDAL failed with an error because the input was just a QGIS XYZ connection string, not a real raster dataset.

### Resolution
Needed to first create a **local raster file**, then work on that file.

---

## 7. Imagery and DEM AOIs did not match
### Problem
Even after valid exports, the imagery and DEM covered slightly different areas.

### Why it mattered
SynTerra would ingest the files, but the generated result could be misaligned or behave incorrectly.

### Resolution
Used the **DEM extent as the reference** and clipped the imagery to match the DEM much more closely.

---

## 8. Misleading raster statistics from QGIS/GDAL
### Problem
One exported TIFF showed statistics suggesting it was a flat gray image:
- constant band values
- zero standard deviation

But when opened visually, it appeared in color.

### Resolution
Do not rely only on band statistics.
Also verify:
- visual appearance in QGIS
- band count
- CRS
- extent

---

## 9. Exported imagery from ESRI looked lower resolution than the live basemap
### Problem
The saved TIFF looked softer than the live ESRI Satellite imagery.

### Cause
ESRI Satellite in QGIS is a **display tile source**, not a direct native orthophoto raster download.
So the export is effectively a baked/rendered raster, not the original source imagery.

### Resolution
Accepted this as a limitation of the quick workflow.
For future higher-fidelity work, use a true downloadable orthophoto/raster source instead of a basemap tile service.

---

## 10. Unreal-side confusion after SynTerra generated assets
### Problem
SynTerra produced:
- a **Static Mesh**
- a **Material**
- a **Texture**

Unclear how to use them in Unreal.

### Resolution
The correct object to place in the level is the:
- **Static Mesh**

The material/texture support the mesh.

---

## 11. Cesium / georeference confusion
### Problem
Unclear whether Cesium georeference origin settings were needed.

### Resolution
If working in a Cesium georeferenced level, use the tile center as the origin:
- **Latitude:** `47.21724592886579`
- **Longitude:** `27.614609502715126`
- **Height:** `0`

But this turned out **not** to be the main blocker for generation.

---

## The actual SynTerra generation blocker
### Problem
Even with valid DEM and imagery, SynTerra still did not want to generate.

### Actual solution
The missing step was:

> **You must not only import the DEM and imagery; you also need to select the relevant tile in SynTerra's viewer where those datasets are located.**

In other words:
- import the DEM as before
- import the imagery raster as before
- then in the **SynTerra viewer**, explicitly **select the tile / area corresponding to those imported datasets**
- only then will SynTerra proceed properly

This was the key operational gotcha.

---

## Final working takeaway

### What worked
1. Prepare:
   - **DEM GeoTIFF**
   - **Imagery GeoTIFF**
2. Ensure both are:
   - georeferenced
   - in **EPSG:4326**
   - covering the same AOI as closely as possible
3. Import both into SynTerra:
   - **Elevation**
   - **Imagery**
4. In the **SynTerra viewer**, **select the relevant tile** where those imported rasters are located
5. Then generate

### Important note
Simply importing the files is **not sufficient**.
The corresponding tile must also be selected in SynTerra's viewer.

---

## Useful validation checklist for next time

Before blaming SynTerra, verify:

### Imagery
- [ ] GeoTIFF
- [ ] EPSG:4326
- [ ] 3 bands (or 4 if valid RGBA)
- [ ] visually contains real imagery
- [ ] AOI matches DEM closely

### DEM
- [ ] GeoTIFF
- [ ] EPSG:4326
- [ ] 1 band
- [ ] numeric elevation values
- [ ] AOI matches imagery closely

### SynTerra workflow
- [ ] imagery imported
- [ ] DEM imported
- [ ] correct tile selected in SynTerra viewer
- [ ] generate from that selected tile

---

## Recommendation for future attempts
For a cleaner long-term workflow:
- use a **true downloadable orthophoto raster source**
- avoid depending on rendered XYZ/ESRI basemap exports if high fidelity matters
- keep AOIs smaller during debugging
- always use the DEM extent as the reference footprint
- always remember the SynTerra viewer tile-selection step

---

## One-line memory aid
**Valid rasters alone are not enough — in SynTerra, also select the matching tile in the viewer before generating.**
"""

path = Path("/mnt/data/synterra_troubleshooting_notes.md")
path.write_text(content, encoding="utf-8")
print(path)
