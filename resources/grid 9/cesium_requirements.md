# Grid 2: Cesium 3D Globe Implementation Guide

To create a Google Earth / Grid-Sentinel-style 3D macro grid, we will use **CesiumJS**, an open-source JavaScript library for world-class 3D globes and maps.

## 1. Required API Keys

Before we start writing the frontend code, you will need to acquire some free API keys to enable the high-quality 3D data.

### A. Cesium ion Access Token (Mandatory)
This is the core key required to initialize the Cesium viewer, fetch the default 3D terrain, and load standard imagery.
*   **How to get it:**
    1. Go to [cesium.com/ion/](https://cesium.com/ion/) and create a free community account.
    2. Once logged in, go to the **Access Tokens** tab on the left sidebar.
    3. Copy the `Default` token string.
*   **Cost:** Free for development and non-commercial use.

### B. Google Photorealistic 3D Tiles API Key (Highly Recommended)
If you specifically want the "Google Earth" look (where entire cities, buildings, and trees are rendered in photorealistic 3D), you should enable the Google Maps 3D Tiles API. Cesium natively integrates with this.
*   **How to get it:**
    1. Go to your [Google Cloud Console](https://console.cloud.google.com/).
    2. Create a new project or select an existing one.
    3. Go to **APIs & Services > Library** and search for **Map Tiles API**. Enable it.
    4. Go to **Credentials**, click **Create Credentials**, and select **API Key**.
*   **Cost:** Google offers a generous free tier ($200 monthly credit) which is more than enough for development.

*(If you choose not to get the Google API key, we can still fall back to Cesium's "OSM Buildings" which provides white 3D building extrusions on top of satellite imagery. It still looks very cool, just not photorealistic).*

---

## 2. Technology Stack & Architecture

We will follow a similar architectural split as `grid 1`, but deeply optimized for a 3D environment.

### Backend (Python / FastAPI)
*   **Simulator:** We can reuse the exact same `sim.py` and `romania_grid.py` logic from `grid 1`. The math for distributing the UAVs across the 10x10km zones does not change.
*   **API:** We will run a WebSocket server on a new port (e.g., `8004`) to broadcast the UAV and Zone coordinates `[longitude, latitude, altitude]`.

### Frontend (HTML / Vanilla JS / CesiumJS)
*   **Engine:** CesiumJS (loaded via CDN so no complex Node.js build steps are required).
*   **Visualization:**
    *   **Zones:** Rendered as 3D Polygons (`Cesium.Entity` with `polygon` graphics), clamped to the ground, with dynamic colors/opacity representing the imbalance gradient.
    *   **Flows:** Rendered as 3D Polylines that arc through the sky (using `Cesium.ArcType.GEODESIC`) to visually represent UAV repositioning over the mountains.
    *   **UAVs:** Rendered as 3D models (glTF) or simple glowing spheres floating at altitude, with their positions updating smoothly.
*   **UI:** A sleek, dark, glassmorphism UI overlay (Grid-Sentinel style) using vanilla CSS, showing connection status, fleet health, and interactive controls to trigger demand spikes.

---

## 3. Next Steps

Please provide the API keys, or let me know if you want me to build the prototype using the default open-source Cesium assets (which won't look exactly like Google Earth, but still provide a full 3D globe and terrain).

Once you're ready, I will generate the `backend` and `frontend` folders inside `grid 2` and wire them up!
