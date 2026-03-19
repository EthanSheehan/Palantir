// 1. Initialize Cesium Viewer
Cesium.Ion.defaultAccessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJmNTg1MmY5OC05NWQ0LTQ0MDEtYTFmMy0yMWI0YzEwYzRiNjciLCJpZCI6NDAzNzE1LCJpYXQiOjE3NzM1MTczMjV9.pfteEFlBPi85hAolMWsVyZkuRTwSeg_-bF5dlTMcWHo';

const viewer = new Cesium.Viewer('cesiumContainer', {
    terrain: Cesium.Terrain.fromWorldTerrain(),
    animation: false,
    baseLayerPicker: false,
    fullscreenButton: false,
    geocoder: false,
    homeButton: false,
    infoBox: false,
    sceneModePicker: false,
    selectionIndicator: false,
    timeline: false,
    navigationHelpButton: false,
    navigationInstructionsInitiallyVisible: false
});

// Remove default maps (if any) and imperatively load Stadia API securely
viewer.imageryLayers.removeAll();
const baseLayer = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
    url: 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'
}));
baseLayer.brightness = 1.8; // Lighten the dark theme to make it more grey
baseLayer.gamma = 1.2;

// Configure Palantir-style Cinematic Lighting & Dark Mode
viewer.scene.globe.baseColor = Cesium.Color.BLACK;
viewer.scene.backgroundColor = Cesium.Color.BLACK;
viewer.scene.globe.enableLighting = true; 
viewer.scene.globe.depthTestAgainstTerrain = true;

// Only re-render when something changes (entities, camera, explicit requestRender calls).
// Dramatically reduces idle CPU/GPU usage vs continuous 60fps rendering.
viewer.scene.requestRenderMode = true;
viewer.scene.maximumRenderTimeChange = Infinity; // only render on explicit requestRender() calls

// Freeze time at noon UTC during the summer solstice so Europe is fully illuminated
viewer.clock.currentTime = Cesium.JulianDate.fromIso8601("2023-06-21T10:00:00Z");
viewer.clock.shouldAnimate = true; // MUST BE TRUE for SampledPositionProperty to tween over time
// Force physics step to real world time 1:1
viewer.clock.multiplier = 1.0; 

// We need a specific velocity vector reference so tracking camera follows "behind"
viewer.trackedEntity = undefined;

viewer.scene.sun.show = false;
viewer.scene.moon.show = false;
viewer.scene.skyAtmosphere.hueShift = -0.5; 
viewer.scene.skyAtmosphere.brightnessShift = -0.8;
viewer.scene.fog.enabled = true;
viewer.scene.fog.density = 0.0001;
// (OsmBuildings removed for Grid 11 baseline)

viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(24.9668, 41.2, 500000.0), 
    orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-45.0),
        roll: 0.0
    },
    duration: 0 
});

// 1b. WorkspaceShell replaced by React layout (see app/layout/WorkspaceLayout.tsx)
// Legacy WorkspaceShell.init(viewer) is no longer called.
// React's WorkspaceLayout will reparent #cesiumContainer and #timelinePanel.
window.viewer = viewer; // Expose for React CesiumSurfaceHost to adopt

// Create temporary #ws-tool-palette for MapToolController (React will adopt its children later)
(function() {
    let palette = document.getElementById('ws-tool-palette');
    if (!palette) {
        palette = document.createElement('div');
        palette.id = 'ws-tool-palette';
        palette.className = 'ws-tool-palette';
        document.body.appendChild(palette);
    }
})();

// 1c. Initialize Map Tool Controller (click/tool modes)
MapToolController.init(viewer, null); // ws set later after connectWebSocket

// ── Right-click context menu (omnipresent; drone-only items hidden when not over a drone) ──
(function initDroneContextMenu() {
    const menu = document.getElementById('drone-context-menu');
    const btnSatellite = document.getElementById('ctx-satellite');
    const btnWaypoint = document.getElementById('ctx-set-waypoint');
    const btnRange = document.getElementById('ctx-range');
    const btnPaintTarget = document.getElementById('ctx-paint-target');
    let _ctxDroneId = null;

    function hideMenu() {
        menu.style.display = 'none';
        _ctxDroneId = null;
    }

    MapToolController.onDroneRightClick((entity, screenPos) => {
        _ctxDroneId = entity ? parseInt(entity.id.replace('uav_', '')) : null;

        // Set Waypoint: only when a drone is already selected (regardless of hover)
        btnWaypoint.style.display = trackedDroneEntity ? '' : 'none';
        // Range: only when right-clicking directly on a drone
        btnRange.style.display    = _ctxDroneId != null ? '' : 'none';

        // Paint Target: only when targets tab is active
        const isTargetsTab = window.AppState && typeof useAppStore !== 'undefined'
            ? false // fallback
            : false;
        // Check React store via window
        const _activeTab = document.querySelector('.ws-tab-btn.ws-active');
        const _onTargetsTab = _activeTab && _activeTab.textContent.includes('TARGET');
        btnPaintTarget.style.display = _onTargetsTab ? '' : 'none';
        if (_onTargetsTab) {
            const isPainting = MapToolController.getActiveTool() === 'paint_target';
            btnPaintTarget.textContent = isPainting ? 'Stop Painting' : 'Paint Target';
        }

        // Update satellite circle label to reflect current state
        btnSatellite.textContent = _lensActive ? 'Satellite Circle: ON' : 'Satellite Circle: OFF';

        // Position menu — keep it inside the window
        const itemCount = 1 + (trackedDroneEntity ? 1 : 0) + (_ctxDroneId != null ? 1 : 0) + (_onTargetsTab ? 1 : 0);
        const menuW = 170, menuH = itemCount * 38;
        const x = Math.min(screenPos.x, window.innerWidth  - menuW - 8);
        const y = Math.min(screenPos.y, window.innerHeight - menuH - 8);
        menu.style.left = x + 'px';
        menu.style.top  = y + 'px';
        menu.style.display = 'flex';
    });

    btnPaintTarget.addEventListener('click', () => {
        const current = MapToolController.getActiveTool();
        MapToolController.setTool(current === 'paint_target' ? 'select' : 'paint_target');
        hideMenu();
    });

    btnSatellite.addEventListener('click', () => {
        _toggleSatelliteLens();
        hideMenu();
    });

    btnWaypoint.addEventListener('click', () => {
        if (!trackedDroneEntity) return;
        MapToolController.setTool('set_waypoint');
        hideMenu();
    });

    btnRange.addEventListener('click', () => {
        if (_ctxDroneId == null) return;
        toggleDroneRange(_ctxDroneId);
        hideMenu();
    });

    // Dismiss on click outside or Escape
    document.addEventListener('click', (e) => {
        if (!menu.contains(e.target)) hideMenu();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') hideMenu();
    });
})();

// 2. Data Structures for ultra-fast rendering
let zonesPrimitive = null;
let zoneBordersPrimitive = null;
let gridVisState = 2; // 2 = ON, 1 = OUTLINES ONLY, 0 = OFF
const zoneAttributesCache = {}; // Cache to prevent lookup overhead
const flowLines = []; 
const uavEntities = {};

// Dictionary to track active 3D Range visualizations { uavId: [Entity, Entity...] }
const droneRangeVisuals = {};

function toggleDroneRange(uavId) {
    const droneWaypoints = MapToolController.getDroneWaypoints();
    if (droneRangeVisuals[uavId]) {
        droneRangeVisuals[uavId].forEach(entity => viewer.entities.remove(entity));
        delete droneRangeVisuals[uavId];
    } else {
        droneRangeVisuals[uavId] = [];
        const numRings = 10;
        const maxRadius = 50000;
        const maxAlt = 2000;
        for (let i = 0; i < numRings; i++) {
            const t = i / (numRings - 1);
            const radius = Math.max(1, t * maxRadius);
            const height = (1 - t) * maxAlt;
            const ring = viewer.entities.add({
                position: new Cesium.CallbackProperty(() => {
                    let targetPos = null;
                    if (droneWaypoints[uavId] && droneWaypoints[uavId].waypoint) {
                        targetPos = droneWaypoints[uavId].waypoint.position.getValue(viewer.clock.currentTime);
                    }
                    if (!targetPos) {
                        const droneEntity = viewer.entities.getById(`uav_${uavId}`);
                        if (droneEntity) targetPos = droneEntity.position.getValue(viewer.clock.currentTime);
                    }
                    if (targetPos) {
                        const carto = Cesium.Cartographic.fromCartesian(targetPos);
                        return Cesium.Cartesian3.fromRadians(carto.longitude, carto.latitude, height);
                    }
                    return null;
                }, false),
                ellipse: {
                    semiMajorAxis: radius,
                    semiMinorAxis: radius,
                    height: height,
                    fill: false,
                    outline: true,
                    outlineColor: Cesium.Color.fromCssColorString('#38bdf8').withAlpha(0.9 - (0.5 * t)),
                    outlineWidth: 4
                }
            });
            droneRangeVisuals[uavId].push(ring);
        }
    }
    viewer.scene.requestRender();
}

const svgCache = {};
function getDronePin(statusColor) {
    if (svgCache[statusColor]) return svgCache[statusColor];
    // Create a 70x78 invisible picking bounds (+15px padding) while perfectly centering the original 40x48 visual vector inside
    const svg = `<svg fill="none" height="78" width="70" viewBox="-15 -15 70 78" xmlns="http://www.w3.org/2000/svg"><rect x="-15" y="-15" width="70" height="78" fill="rgba(255,255,255,0.01)"/><rect x="6" y="6" width="28" height="28" stroke="#3b82f6" stroke-width="2"/><circle cx="20" cy="20" r="4" fill="#3b82f6"/><rect x="6" y="40" width="28" height="6" fill="${statusColor}"/></svg>`;
    const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    svgCache[statusColor] = url;
    return url;
}

// We cache colors to avoid massive allocations
const _imbalanceColorCache = {};
const _redBase = Cesium.Color.fromCssColorString('rgba(239, 68, 68, 1.0)');
const _blueBase = Cesium.Color.fromCssColorString('rgba(59, 130, 246, 1.0)');
const _zeroColor = new Cesium.Color(0, 0, 0, 0.0);

function getImbalanceColor(imbalance) {
    const imb = Math.max(-20, Math.min(20, imbalance));
    // Round to 1 decimal to limit cache size while keeping visual fidelity
    const key = Math.round(imb * 10);
    if (_imbalanceColorCache[key]) return _imbalanceColorCache[key];

    let color;
    if (imb < 0) {
        const intensity = Math.abs(imb) / 20.0;
        color = _redBase.withAlpha(0.2 + (intensity * 0.4));
    } else if (imb > 0) {
        const intensity = imb / 20.0;
        color = _blueBase.withAlpha(0.2 + (intensity * 0.4));
    } else {
        color = _zeroColor;
    }
    _imbalanceColorCache[key] = color;
    return color;
}

// Ensure the Primitive is built once, then we only update its instance attributes
function initOrUpdateZonesPrimitive(stateZones) {
    if (!zonesPrimitive) {
        // console.log("Building GroundPrimitive for", stateZones.length, "zones.");
        const fillInstances = [];
        const borderInstances = [];
        
        stateZones.forEach(z => {
            const zoneId = `z_${z.x_idx}_${z.y_idx}`;
            const width = z.width || 0.192;
            const height = z.height || 0.094;
            const halfW = width / 2;
            const halfH = height / 2;
            
            const p1 = [z.lon - halfW, z.lat - halfH];
            const p2 = [z.lon + halfW, z.lat - halfH];
            const p3 = [z.lon + halfW, z.lat + halfH];
            const p4 = [z.lon - halfW, z.lat + halfH];
            
            const hierarchy = new Cesium.PolygonHierarchy(Cesium.Cartesian3.fromDegreesArray([
                ...p1, ...p2, ...p3, ...p4
            ]));
            
            const color = getImbalanceColor(z.imbalance);
            
            fillInstances.push(new Cesium.GeometryInstance({
                id: zoneId,
                geometry: new Cesium.PolygonGeometry({
                    polygonHierarchy: hierarchy,
                    height: 0,
                    extrudedHeight: 0
                }),
                attributes: {
                    color: Cesium.ColorGeometryInstanceAttribute.fromColor(color)
                }
            }));
            
            const borderPositions = Cesium.Cartesian3.fromDegreesArray([
                ...p1, ...p2, ...p3, ...p4, ...p1
            ]);
            
            borderInstances.push(new Cesium.GeometryInstance({
                geometry: new Cesium.GroundPolylineGeometry({
                    positions: borderPositions,
                    width: 1.0
                })
            }));
        });
        
        zonesPrimitive = viewer.scene.primitives.add(new Cesium.GroundPrimitive({
            geometryInstances: fillInstances,
            appearance: new Cesium.PerInstanceColorAppearance({
                flat: true,
                translucent: true
            }),
            asynchronous: false // load immediately 
        }));
        
        zoneBordersPrimitive = viewer.scene.primitives.add(new Cesium.GroundPolylinePrimitive({
            geometryInstances: borderInstances,
            appearance: new Cesium.PolylineMaterialAppearance({
                material: Cesium.Material.fromType("Color", {
                    color: new Cesium.Color(1.0, 1.0, 1.0, 0.15)
                })
            }),
            asynchronous: true // Compute border math in background to not block UI
        }));
        
        zonesPrimitive.show = (gridVisState === 2);
        zoneBordersPrimitive.show = (gridVisState === 1 || gridVisState === 2);
    } else {
        // GroundPrimitive needs a render frame to compile geometry; skip until ready
        if (!zonesPrimitive.ready) return;

        // High-performance update loop: cache attributes and don't re-allocate
        stateZones.forEach(z => {
            const zoneId = `z_${z.x_idx}_${z.y_idx}`;
            const color = getImbalanceColor(z.imbalance);

            let attrs = zoneAttributesCache[zoneId];
            if (!attrs) {
                // First time we look this up, we cache it
                attrs = zonesPrimitive.getGeometryInstanceAttributes(zoneId);
                zoneAttributesCache[zoneId] = attrs;
                if (attrs) attrs._lastColor = null;
            }
            
            if (attrs) {
                const newColorStr = `${color.red},${color.green},${color.blue},${color.alpha}`;
                // Only write to the buffer if the color has actually changed
                if (attrs._lastColor !== newColorStr) {
                    // Set Uint8Array directly for max speed
                    attrs.color = [
                        Math.round(color.red * 255), 
                        Math.round(color.green * 255), 
                        Math.round(color.blue * 255), 
                        Math.round(color.alpha * 255)
                    ];
                    attrs._lastColor = newColorStr;
                }
            }
        });
    }
}

// 4. Update Loop
function updateSimulation(state) {
    viewer.scene.requestRender();

    // 4.1 Update Zones using ultra-fast GroundPrimitives
    initOrUpdateZonesPrimitive(state.zones);

    // 4.2 Update Flows (reuse entities to avoid add/remove churn)
    const numFlows = state.flows.length;

    // Create new entities only if we need more than we have
    while (flowLines.length < numFlows) {
        flowLines.push(viewer.entities.add({
            polyline: {
                positions: [],
                width: 3,
                material: new Cesium.PolylineGlowMaterialProperty({
                    glowPower: 0.2,
                    color: Cesium.Color.CYAN
                }),
                arcType: Cesium.ArcType.GEODESIC
            }
        }));
    }

    // Update positions on existing entities; hide extras
    for (let i = 0; i < flowLines.length; i++) {
        if (i < numFlows) {
            const flow = state.flows[i];
            flowLines[i].polyline.positions = Cesium.Cartesian3.fromDegreesArrayHeights([
                flow.source[0], flow.source[1], 2000,
                flow.target[0], flow.target[1], 2000
            ]);
            flowLines[i].show = true;
        } else {
            flowLines[i].show = false;
        }
    }

    // 4.3 Update UAVs
    const currentUavIds = new Set();
    state.uavs.forEach(uav => {
        currentUavIds.add(uav.id);
        
        let colorStr = '#3b82f6'; // Idle (blue)
        if (uav.mode === "serving") colorStr = '#22c55e'; // Green
        else if (uav.mode === "repositioning") colorStr = '#eab308'; // Yellow
        const color = Cesium.Color.fromCssColorString(colorStr);
        const billboardImage = getDronePin(colorStr);
        
        const position = Cesium.Cartesian3.fromDegrees(uav.lon, uav.lat, 1000);
        
        // Model is always grey
        const modelColor = Cesium.Color.fromCssColorString('#888888');

        if (!uavEntities[uav.id]) {
            const positionProperty = new Cesium.SampledPositionProperty();
            positionProperty.forwardExtrapolationType = Cesium.ExtrapolationType.HOLD;
            positionProperty.backwardExtrapolationType = Cesium.ExtrapolationType.HOLD;
            positionProperty.setInterpolationOptions({
                interpolationDegree: 2,
                interpolationAlgorithm: Cesium.HermitePolynomialApproximation
            });
            positionProperty.addSample(viewer.clock.currentTime, position);
            
            const orientationProperty = new Cesium.SampledProperty(Cesium.Quaternion);
            orientationProperty.forwardExtrapolationType = Cesium.ExtrapolationType.HOLD;
            orientationProperty.backwardExtrapolationType = Cesium.ExtrapolationType.HOLD;
            orientationProperty.setInterpolationOptions({
                interpolationDegree: 2,
                interpolationAlgorithm: Cesium.HermitePolynomialApproximation
            });
            const hpr = new Cesium.HeadingPitchRoll(0, 0, 0); 
            orientationProperty.addSample(viewer.clock.currentTime, Cesium.Transforms.headingPitchRollQuaternion(position, hpr));

            const marker = viewer.entities.add({
                id: `uav_${uav.id}`,
                name: `Fixed - ${String(uav.id + 1).padStart(2, '0')}`,
                position: positionProperty,
                orientation: orientationProperty,
                point: {
                    pixelSize: 6,
                    color: color,
                    outlineColor: Cesium.Color.BLACK,
                    outlineWidth: 1,
                    heightReference: Cesium.HeightReference.NONE,
                    // The simple dot appears only from high orbit (800km+)
                    distanceDisplayCondition: new Cesium.DistanceDisplayCondition(800000.0, 50000000.0),
                    // Prevent dot from clipping into mountains at low view angles
                    disableDepthTestDistance: Number.POSITIVE_INFINITY
                },
                billboard: {
                    image: billboardImage,
                    scale: 0.8,
                    verticalOrigin: Cesium.VerticalOrigin.CENTER,
                    // The SVG UI appears between the 3D Tracking view and the Extreme Orbit view
                    distanceDisplayCondition: new Cesium.DistanceDisplayCondition(2000.0, 800000.0),
                    // Prevent SVG from clipping into mountains at low view angles
                    disableDepthTestDistance: Number.POSITIVE_INFINITY
                },
                model: {
                    uri: 'Fixed V2.glb',
                    minimumPixelSize: 100,
                    maximumScale: 50.0,
                    color: modelColor,
                    colorBlendMode: Cesium.ColorBlendMode.MIX,
                    colorBlendAmount: 0.5,
                    castShadows: false,
                    receiveShadows: false,
                    // The 3D model is hidden when fully zoomed out to save GPU, popping in at 20km
                    distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0.0, 20000.0)
                }
            });
            
            const tether = viewer.entities.add({
                polyline: {
                    positions: new Cesium.CallbackProperty((time) => {
                        try {
                            const currentPos = positionProperty.getValue(time);
                            if (!currentPos) return [];
                            const carto = Cesium.Cartographic.fromCartesian(currentPos);
                            if (!carto) return [];
                            const groundPos = Cesium.Cartesian3.fromRadians(carto.longitude, carto.latitude, 0);
                            return [groundPos, currentPos];
                        } catch (e) {
                            return [];
                        }
                    }, false),
                    width: 1,
                    material: color.withAlpha(0.3)
                }
            });
            marker._tether = tether;
            
            uavEntities[uav.id] = marker;
            // Store previous position to calculate heading
            marker._lastLon = uav.lon;
            marker._lastLat = uav.lat;
            marker._lastMode = colorStr;
        } else {
            const marker = uavEntities[uav.id];
            
            // The simulation backend updates at roughly 10Hz (100ms).
            // To completely eliminate camera tracking stuttering, we must rigidly space out samples by exactly 0.1s.
            let targetTime;
            const now = viewer.clock.currentTime;
            
            if (!marker._lastTargetTime) {
                // Initialize the buffer 300ms (0.3s) into the future to completely absorb network jitter
                targetTime = Cesium.JulianDate.addSeconds(now, 0.3, new Cesium.JulianDate());
            } else {
                targetTime = Cesium.JulianDate.addSeconds(marker._lastTargetTime, 0.1, new Cesium.JulianDate());
                
                // Buffer Drift Check: The playback head (now) must never overtake targetTime.
                const diff = Cesium.JulianDate.secondsDifference(targetTime, now);
                // If the future buffer shrinks below 100ms (danger of stuttering/starvation) 
                // or grows beyond 500ms (too much lag buildup), force a smooth resync.
                if (diff < 0.1 || diff > 0.5) {
                    targetTime = Cesium.JulianDate.addSeconds(now, 0.3, new Cesium.JulianDate());
                }
            }
            marker._lastTargetTime = targetTime;
            
            marker.position.addSample(targetTime, position);

            // Prune old samples to prevent unbounded growth (Hermite interpolation
            // cost scales with sample count). Keep last 30 samples (~3s at 10Hz).
            if (marker.position._property && marker.position._property._times &&
                marker.position._property._times.length > 60) {
                const times = marker.position._property._times;
                const values = marker.position._property._values;
                const excess = times.length - 30;
                times.splice(0, excess);
                values.splice(0, excess * 3); // Cartesian3 = 3 floats per sample
            }
            if (marker.orientation._times && marker.orientation._times.length > 60) {
                const times = marker.orientation._times;
                const values = marker.orientation._values;
                const excess = times.length - 30;
                times.splice(0, excess);
                values.splice(0, excess * 4); // Quaternion = 4 floats per sample
            }

            // Calculate orientation dynamically from movement vector
            const dx = uav.lon - marker._lastLon;
            const dy = uav.lat - marker._lastLat;
            
            // INCREASE THRESHOLD to 0.002 to prevent 10Hz jitter / stuttering
            const movementDist = Math.abs(dx) + Math.abs(dy);
            if (movementDist > 0.002) {
                // Correct for map projection distortion (longitude shrinks towards the poles)
                const latRad = Cesium.Math.toRadians(uav.lat);
                const dxScaled = dx * Math.cos(latRad);
                const mathAngle = Math.atan2(dy, dxScaled); 
                
                // Convert math angle to Cesium heading.
                // The user noted they point exactly backwards. We will rotate by +180 deg (Math.PI)
                let heading = (Math.PI / 2) - mathAngle + Math.PI; 
                
                // Add smoothing logic so the heading doesn't snap violently (interpolate current vs target)
                if (!marker._lastHeading) marker._lastHeading = heading;
                
                // Normalize angle wrap-around
                let diff = heading - marker._lastHeading;
                while (diff > Math.PI) diff -= Math.PI * 2;
                while (diff < -Math.PI) diff += Math.PI * 2;
                
                // Low-pass filter (smooth by 30% per tick)
                heading = marker._lastHeading + (diff * 0.3);
                marker._lastHeading = heading;

                const pitch = 0.0;
                const roll = 0.0;
                const hpr = new Cesium.HeadingPitchRoll(heading, pitch, roll);
                
                // Compute quaternion at the new target position and interpolate smoothly to it
                const quat = Cesium.Transforms.headingPitchRollQuaternion(position, hpr);
                marker.orientation.addSample(targetTime, quat);
                
                marker._lastLon = uav.lon;
                marker._lastLat = uav.lat;
            }
            
            if (marker._lastMode !== colorStr) {
                marker.billboard.image = getDronePin(colorStr);
                marker.point.color = color;
                if (marker._tether) {
                    marker._tether.polyline.material = color.withAlpha(0.3);
                }
                marker._lastMode = colorStr;
            }
        }
    });
    
    const _uavCountEl = document.getElementById('uavCount');
    const _zoneCountEl = document.getElementById('zoneCount');
    if (_uavCountEl) _uavCountEl.textContent = state.uavs.length;
    if (_zoneCountEl) _zoneCountEl.textContent = state.zones.length;
    
    // Determine currently tracked drone ID
    let currentTrackedId = null;
    if (trackedDroneEntity) {
        currentTrackedId = parseInt(trackedDroneEntity.id.replace('uav_', ''));
    }
    
    // Update Sidebar Drone List (legacy — only if element exists)
    const listContainer = document.getElementById('droneListContainer');
    if (!listContainer) { /* React owns the assets panel now */ }
    else if (state.uavs.length === 0) {
        listContainer.innerHTML = '<div class="empty-state">No UAVs Active.</div>';
    } else {
        // Remove empty state message if it is there
        const emptyState = listContainer.querySelector('.empty-state');
        if (emptyState) listContainer.removeChild(emptyState);
        
        // Track which IDs are in the latest state
        const activeIds = new Set(state.uavs.map(u => u.id));
        
        // Remove cards for offline drones
        Array.from(listContainer.children).forEach(card => {
            const id = parseInt(card.dataset.id);
            if (!activeIds.has(id)) {
                listContainer.removeChild(card);
            }
        });
        
        // Update or create cards for online drones
        state.uavs.forEach(u => {
            let card = listContainer.querySelector(`[data-id="${u.id}"]`);
            if (!card) {
                // Initial creation
                card = document.createElement('div');
                card.className = 'drone-card';
                card.dataset.id = u.id;
                
                card.clickTimer = null;
                card.draggable = true;
                card.addEventListener('dragstart', (e) => {
                    e.dataTransfer.setData('uavId', String(u.id));
                    e.dataTransfer.effectAllowed = 'link';
                });

                card.addEventListener('click', (e) => {
                    if (card.clickTimer) clearTimeout(card.clickTimer);
                    card.clickTimer = setTimeout(() => {
                        const entity = viewer.entities.getById(`uav_${u.id}`);
                        if (!entity) return;
                        if (e.shiftKey) {
                            MapToolController._triggerDroneSelectionAdditive(entity);
                        } else {
                            triggerDroneSelection(entity, 'macro');
                        }
                    }, 250);
                });
                card.addEventListener('dblclick', (e) => {
                    e.preventDefault(); // Prevent text selection
                    if (card.clickTimer) clearTimeout(card.clickTimer);
                    const entity = viewer.entities.getById(`uav_${u.id}`);
                    if (entity) triggerDroneSelection(entity, 'thirdPerson');
                });
                
                listContainer.appendChild(card);
            }
            
            // Check tracking / secondary-selection state
            const isTracked   = (u.id === currentTrackedId);
            const entityId    = `uav_${u.id}`;
            const selIds      = AppState.state.selection.assetIds;
            const isSecondary = !isTracked && selIds.includes(entityId) && selIds[0] !== entityId;
            const cardBg          = isTracked   ? 'rgba(250, 204, 21, 0.15)'  : isSecondary ? 'rgba(34, 211, 238, 0.1)'  : '';
            const cardBorderColor = isTracked   ? 'rgba(250, 204, 21, 0.5)'   : isSecondary ? 'rgba(34, 211, 238, 0.4)'  : '';
            const idColor         = isTracked   ? '#facc15'                   : isSecondary ? '#22d3ee'                   : '';

            // Re-render inner content only if status or selection state changes
            const selState = isTracked ? 'primary' : isSecondary ? 'secondary' : 'none';
            if (card.dataset.mode !== u.mode || card.dataset.selState !== selState) {
                let innerHTML = `
                    <div class="drone-card-header">
                        <span class="drone-card-id" style="color: ${idColor}">UAV-${u.id}</span>
                        <span class="drone-card-status status-${u.mode}">${u.mode}</span>
                    </div>
                `;
                
                if (isTracked) {
                    innerHTML += `
                        <div class="drone-details">
                            <div class="stats">
                                <div class="stat-row">
                                    <span class="stat-label">Altitude:</span>
                                    <span class="stat-value">2.00 km</span>
                                </div>
                                <div class="stat-row">
                                    <span class="stat-label">Coordinates:</span>
                                    <span class="stat-value">${u.lon.toFixed(4)}, ${u.lat.toFixed(4)}</span>
                                </div>
                            </div>
                            <div class="split-btn-group">
                                <button class="btn-primary" id="inlineSetWaypointBtn_${u.id}">Set Waypoint</button>
                                <button class="btn-tertiary" id="inlineRangeBtn_${u.id}">Range</button>
                                <button class="btn-secondary" id="inlineDetailWaypointBtn_${u.id}" title="Detail Set Waypoint">🎯</button>
                            </div>
                        </div>
                    `;
                }
                
                card.innerHTML = innerHTML;
                card.dataset.mode = u.mode;
                card.dataset.selState = selState;

                // Apply background/border for primary (yellow), secondary (cyan), or neither
                card.style.background   = cardBg;
                card.style.borderColor  = cardBorderColor;

                if (isTracked) {
                    
                    // Attach dynamic waypoint listener to the newly generated buttons
                    const wpBtn = card.querySelector('.btn-primary');
                    const detailBtn = card.querySelector('.btn-secondary');
                    
                    if (wpBtn) {
                        wpBtn.addEventListener('click', (e) => {
                            e.stopPropagation(); // Don't trigger the card's tracking click
                            const isWaypoint = MapToolController.getActiveTool() === 'set_waypoint';
                            if (!isWaypoint) {
                                MapToolController.setTool('set_waypoint');
                                wpBtn.textContent = 'Select Target...';
                                wpBtn.style.background = 'rgba(34, 197, 94, 0.2)';
                                wpBtn.style.borderColor = 'rgba(34, 197, 94, 0.5)';
                                wpBtn.style.color = '#22c55e';
                            } else {
                                MapToolController.setTool('select');
                                wpBtn.textContent = 'Set Waypoint';
                                wpBtn.style.background = '';
                                wpBtn.style.borderColor = '';
                                wpBtn.style.color = '';
                            }
                        });

                        // Sync visual state if currently in waypoint mode
                        if (MapToolController.getActiveTool() === 'set_waypoint') {
                            wpBtn.textContent = 'Select Target...';
                            wpBtn.style.background = 'rgba(34, 197, 94, 0.2)';
                            wpBtn.style.borderColor = 'rgba(34, 197, 94, 0.5)';
                            wpBtn.style.color = '#22c55e';
                        }
                    }
                    
                    if (detailBtn) {
                        detailBtn.addEventListener('click', (e) => {
                            e.stopPropagation();
                            openDetailMapModal(u);
                        });
                    }
                    
                    const rangeBtn = card.querySelector('.btn-tertiary');
                    if (rangeBtn) {
                        const isRangeActive = !!droneRangeVisuals[u.id];
                        if (isRangeActive) {
                            rangeBtn.style.background = 'rgba(56, 189, 248, 0.4)';
                            rangeBtn.style.borderColor = 'rgba(56, 189, 248, 0.6)';
                            rangeBtn.style.color = '#fff';
                        }
                        
                        rangeBtn.addEventListener('click', (e) => {
                            e.stopPropagation();
                            if (droneRangeVisuals[u.id]) {
                                // Toggle OFF
                                droneRangeVisuals[u.id].forEach(entity => viewer.entities.remove(entity));
                                delete droneRangeVisuals[u.id];
                                rangeBtn.style.background = '';
                                rangeBtn.style.borderColor = '';
                                rangeBtn.style.color = '';
                            } else {
                                // Toggle ON: Draw the dash-range cone (10 stacked expanding rings)
                                droneRangeVisuals[u.id] = [];
                                
                                const numRings = 10;
                                const maxRadius = 50000; // 50km
                                const maxAlt = 2000; // assumed 2km cruise alt from stats text
                                
                                for (let i = 0; i < numRings; i++) {
                                    // Scale from 0 to 1
                                    const t = i / (numRings - 1); // 0 = at drone (highest), 1 = at ground (widest)
                                    
                                    // The radius grows from 0 to 50km
                                    const radius = Math.max(1, t * maxRadius); // Avoid exactly 0 radius
                                    
                                    // The altitude drops from 2000m down to 0m
                                    const height = (1 - t) * maxAlt;
                                    
                                    const ring = viewer.entities.add({
                                        position: new Cesium.CallbackProperty(() => {
                                            let targetPos = null;
                                            // 1. Check if the drone has an active waypoint
                                            if (droneWaypoints[u.id] && droneWaypoints[u.id].waypoint) {
                                                targetPos = droneWaypoints[u.id].waypoint.position.getValue(viewer.clock.currentTime);
                                            }
                                            
                                            // 2. Fallback to drone's current position if no waypoint or if waypoint has no valid position yet
                                            if (!targetPos) {
                                                const droneEntity = viewer.entities.getById(`uav_${u.id}`);
                                                if (droneEntity) {
                                                    targetPos = droneEntity.position.getValue(viewer.clock.currentTime);
                                                }
                                            }
                                            
                                            if (targetPos) {
                                                // Extract ground pos beneath the chosen target
                                                const carto = Cesium.Cartographic.fromCartesian(targetPos);
                                                return Cesium.Cartesian3.fromRadians(carto.longitude, carto.latitude, height);
                                            }
                                            return null;
                                        }, false),
                                        ellipse: {
                                            semiMajorAxis: radius,
                                            semiMinorAxis: radius,
                                            height: height,
                                            fill: false,
                                            outline: true,
                                            outlineColor: Cesium.Color.fromCssColorString('#38bdf8').withAlpha(0.9 - (0.5 * t)),
                                            outlineWidth: 4
                                        }
                                    });
                                    droneRangeVisuals[u.id].push(ring);
                                }
                                
                                rangeBtn.style.background = 'rgba(56, 189, 248, 0.4)';
                                rangeBtn.style.borderColor = 'rgba(56, 189, 248, 0.6)';
                                rangeBtn.style.color = '#fff';
                            }
                            viewer.scene.requestRender();
                        });
                    }
                }
            }
            // Apply current filter — hide card if it doesn't match the active status filter
            card.style.display = (_assetStatusFilter === 'all' || u.mode === _assetStatusFilter) ? '' : 'none';
        });
    }

    Object.keys(uavEntities).forEach(id => {
        if (!currentUavIds.has(parseInt(id))) {
            const marker = uavEntities[id];
            if (marker._tether) viewer.entities.remove(marker._tether);
            viewer.entities.remove(marker);
            delete uavEntities[id];
            
            // Clean up range visuals if drone is deleted
            if (droneRangeVisuals[id]) {
                droneRangeVisuals[id].forEach(entity => viewer.entities.remove(entity));
                delete droneRangeVisuals[id];
            }
        }
    });

    // First, run through all drones to auto-clear reached targets
    state.uavs.forEach(u => {
        if (u.mode !== 'repositioning' && droneWaypoints[u.id]) {
            viewer.entities.remove(droneWaypoints[u.id].waypoint);
            viewer.entities.remove(droneWaypoints[u.id].trajectory);
            delete droneWaypoints[u.id];
        }
    });

    // Global waypoint toggle sync
    Object.keys(droneWaypoints).forEach(idStr => {
        const id = parseInt(idStr);
        const wp = droneWaypoints[id];
        const isVisible = showAllWaypoints || (id === currentTrackedId);
        wp.waypoint.show = isVisible;
        wp.trajectory.show = isVisible;
    });

    viewer.scene.requestRender();
}

// 4.5 3D Compass Projection Cursor
let _assetStatusFilter = 'all'; // 'all' | 'idle' | 'serving' | 'repositioning'
let _compassScale = 1.0;
// 'canvas' = flat perspective-correct rings with arc-clipping; 'ground' = Cesium clampToGround entities
// Default is 'ground' (terrain-adaptive); 'canvas' (halo-adaptive/merge) is toggled ON via the ○ button
let _haloMode = 'ground';
let _secondaryGroundRings = []; // Cesium entities used in 'ground' mode
let _lensActive = false;
let _lensViewer = null;
let currentMousePosition = null;
// trackedDroneEntity is the canonical read-path for legacy code (compass, drone cards, etc.)
// MapToolController owns mutations; this var is synced by reading from the controller each frame.
let trackedDroneEntity = null;
let mapClickTimer = null;

function getCompassCenter() {
    if (trackedDroneEntity) {
        const dronePos = trackedDroneEntity.position.getValue(viewer.clock.currentTime);
        if (dronePos) {
            let carto = Cesium.Cartographic.fromCartesian(dronePos);
            carto.height = 0;
            return Cesium.Cartographic.toCartesian(carto);
        }
    }
    return currentMousePosition;
}

const compassEntity = viewer.entities.add({
    id: 'compass',
    // The Compass Needle
    polyline: {
        positions: new Cesium.CallbackProperty(() => {
            const center = getCompassCenter();
            if (!center) return [];
            
            const transform = Cesium.Transforms.eastNorthUpToFixedFrame(center);
            let fwd = new Cesium.Cartesian3(0.0, 2000.0 * _compassScale, 0.0);
            
            if (trackedDroneEntity) {
                // If we are tracking a drone, use its explicitly cached _lastHeading
                // The drone heading is standard CW from North in radians.
                // We need to rotate the default +Y (North) vector by this amount.
                // In ENU, +Y is North, +X is East, so CW rotation applies correctly.
                let heading = 0.0;
                
                // Get the raw marker from the uavEntities dictionary
                const markerId = trackedDroneEntity.id.replace('uav_', '');
                if (uavEntities[markerId] && uavEntities[markerId]._lastHeading !== undefined) {
                    heading = uavEntities[markerId]._lastHeading;
                    
                    // The CAD drone has a +180 deg offset in its model orientation,
                    // so we subtract it back out to get the true travel heading for the compass needle.
                    heading -= Math.PI; 
                }

                // Apply Z-axis rotation (yaw/heading) in the local ENU frame
                const rotMatrix = Cesium.Matrix3.fromRotationZ(-heading);
                Cesium.Matrix3.multiplyByVector(rotMatrix, fwd, fwd);
            }
            
            let worldFwd = new Cesium.Cartesian3();
            Cesium.Matrix4.multiplyByPoint(transform, fwd, worldFwd);
            
            return [center, worldFwd];
        }, false),
        width: 3,
        material: Cesium.Color.fromCssColorString('#facc15'),
        clampToGround: true
    }
});

const compassRingEntity = viewer.entities.add({
    id: 'compassRing',
    polyline: {
        show: true, // visible by default (ground/terrain mode); canvas overlay takes over when ○ is ON
        positions: new Cesium.CallbackProperty(() => {
            const center = getCompassCenter();
            if (!center) return [];
            
            const radius = 1500.0 * _compassScale;
            const segments = 64; // High res circle
            const transform = Cesium.Transforms.eastNorthUpToFixedFrame(center);
            const pts = [];
            let local = new Cesium.Cartesian3();
            for (let i = 0; i <= segments; i++) {
                const angle = (i / segments) * Math.PI * 2;
                local.x = Math.cos(angle) * radius;
                local.y = Math.sin(angle) * radius;
                local.z = 0;
                pts.push(Cesium.Matrix4.multiplyByPoint(transform, local, new Cesium.Cartesian3()));
            }
            return pts;
        }, false),
        width: 3,
        material: Cesium.Color.fromCssColorString('#facc15').withAlpha(0.6),
        clampToGround: true
    }
});

// ── Paint-mode Red X Crosshair (projected on globe like compass) ──
let _paintCrosshairActive = false;

function _makeCrosshairArm(angleDeg) {
    return viewer.entities.add({
        id: '_paint_crosshair_' + angleDeg,
        polyline: {
            positions: new Cesium.CallbackProperty(() => {
                if (!_paintCrosshairActive) return [];
                const center = currentMousePosition;
                if (!center) return [];
                const armLen = 1200.0 * _compassScale;
                const transform = Cesium.Transforms.eastNorthUpToFixedFrame(center);
                const rad = Cesium.Math.toRadians(angleDeg);
                const local = new Cesium.Cartesian3(Math.sin(rad) * armLen, Math.cos(rad) * armLen, 0);
                const tip = Cesium.Matrix4.multiplyByPoint(transform, local, new Cesium.Cartesian3());
                const localNeg = new Cesium.Cartesian3(-local.x, -local.y, 0);
                const tipNeg = Cesium.Matrix4.multiplyByPoint(transform, localNeg, new Cesium.Cartesian3());
                return [tipNeg, center, tip];
            }, false),
            width: 2,
            material: Cesium.Color.fromCssColorString('#ef4444').withAlpha(0.8),
            clampToGround: true
        }
    });
}
const _crosshairArm1 = _makeCrosshairArm(45);
const _crosshairArm2 = _makeCrosshairArm(-45);

// Listen for tool changes to toggle crosshair
if (typeof MapToolController !== 'undefined' && MapToolController.onToolChange) {
    MapToolController.onToolChange((toolId) => {
        _paintCrosshairActive = toolId === 'paint_target';
        viewer.scene.requestRender();
    });
}

AppState.subscribe('selection.changed', () => {
    _updateGroundRings();
    viewer.scene.requestRender();
});

// ── Halo Canvas Overlay ─────────────────────────────────────────────────────
// All selection rings (compass ring + secondary drone rings) are drawn here as a
// merged union outline: where two rings overlap, the arc segments inside each other
// are clipped away, producing a single continuous "blob" outline (Palantir-style).
// The Cesium compassRingEntity polyline is hidden; the canvas takes over rendering.

const _haloCanvas = document.createElement('canvas');
_haloCanvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none;z-index:5;';
document.getElementById('cesiumContainer').appendChild(_haloCanvas);

// _updateGroundRings: rebuild secondary Cesium clampToGround ring entities for 'ground' mode.
// Called on selection change and when toggling halo mode.
function _updateGroundRings() {
    _secondaryGroundRings.forEach(e => viewer.entities.remove(e));
    _secondaryGroundRings = [];
    if (_haloMode !== 'ground') return;
    AppState.state.selection.assetIds.slice(1).forEach(droneId => {
        const ringEnt = viewer.entities.add({
            polyline: {
                positions: new Cesium.CallbackProperty(() => {
                    const ent = viewer.entities.getById(droneId);
                    if (!ent) return [];
                    const dp = ent.position.getValue(viewer.clock.currentTime);
                    if (!dp) return [];
                    const carto = Cesium.Cartographic.fromCartesian(dp);
                    carto.height = 0;
                    const center = Cesium.Cartographic.toCartesian(carto);
                    const radius = 1500.0 * _compassScale;
                    const xf = Cesium.Transforms.eastNorthUpToFixedFrame(center);
                    const pts = [];
                    const local = new Cesium.Cartesian3();
                    for (let i = 0; i <= 64; i++) {
                        const angle = (i / 64) * Math.PI * 2;
                        local.x = Math.cos(angle) * radius;
                        local.y = Math.sin(angle) * radius;
                        local.z = 0;
                        pts.push(Cesium.Matrix4.multiplyByPoint(xf, local, new Cesium.Cartesian3()));
                    }
                    return pts;
                }, false),
                width: 2,
                material: Cesium.Color.fromCssColorString('#22d3ee').withAlpha(0.6),
                clampToGround: true
            }
        });
        _secondaryGroundRings.push(ringEnt);
    });
}

function _renderHalos() {
    const ctx = _haloCanvas.getContext('2d');
    if (_haloMode === 'ground') {
        ctx.clearRect(0, 0, _haloCanvas.width, _haloCanvas.height);
        return;
    }

    const scene = viewer.scene;
    const w = viewer.canvas.clientWidth;
    const h = viewer.canvas.clientHeight;
    if (_haloCanvas.width !== w || _haloCanvas.height !== h) {
        _haloCanvas.width = w;
        _haloCanvas.height = h;
    }
    ctx.clearRect(0, 0, w, h);

    // Build world-space ring descriptors
    const rings = [];
    const compassCenter = getCompassCenter();
    if (compassCenter) {
        rings.push({ center: compassCenter, radius: 1500.0 * _compassScale, color: '#facc15', alpha: 0.6, lw: 3 });
    }
    const ids = AppState.state.selection.assetIds;
    ids.slice(1).forEach(id => {
        const ent = viewer.entities.getById(id);
        if (!ent) return;
        const dp = ent.position.getValue(viewer.clock.currentTime);
        if (!dp) return;
        const carto = Cesium.Cartographic.fromCartesian(dp);
        carto.height = 0;
        rings.push({ center: Cesium.Cartographic.toCartesian(carto), radius: 1500.0 * _compassScale, color: '#22d3ee', alpha: 0.6, lw: 2 });
    });
    if (!rings.length) return;

    // Sample N points per ring in ENU world space (ellipsoid surface, z=0).
    // Clip segments that fall inside another ring, then project to canvas.
    const SAMPLES = 128;
    const TWO_PI = Math.PI * 2;
    const tmp3 = new Cesium.Cartesian3();

    for (let ri = 0; ri < rings.length; ri++) {
        const { center, radius, color, alpha, lw } = rings[ri];
        const xf = Cesium.Transforms.eastNorthUpToFixedFrame(center);

        // Pre-compute 3D world positions for each sample
        const worldPts = new Array(SAMPLES);
        for (let s = 0; s < SAMPLES; s++) {
            const a = (s / SAMPLES) * TWO_PI;
            tmp3.x = Math.cos(a) * radius;
            tmp3.y = Math.sin(a) * radius;
            tmp3.z = 0;
            worldPts[s] = Cesium.Matrix4.multiplyByPoint(xf, tmp3, new Cesium.Cartesian3());
        }

        // Visibility: sample point is visible if it's NOT inside any other ring
        const vis = new Array(SAMPLES);
        for (let s = 0; s < SAMPLES; s++) {
            let blocked = false;
            for (let rj = 0; rj < rings.length; rj++) {
                if (rj === ri) continue;
                if (Cesium.Cartesian3.distance(worldPts[s], rings[rj].center) < rings[rj].radius) {
                    blocked = true; break;
                }
            }
            vis[s] = !blocked;
        }

        // Find start index just after first invisible sample (avoids splitting a run)
        let startIdx = 0, anyHidden = false;
        for (let s = 0; s < SAMPLES; s++) {
            if (!vis[s]) { startIdx = (s + 1) % SAMPLES; anyHidden = true; break; }
        }

        ctx.strokeStyle = color;
        ctx.globalAlpha = alpha;
        ctx.lineWidth = lw;
        ctx.lineCap = 'round';

        if (!anyHidden) {
            // Entire ring visible — draw as one projected polyline
            ctx.beginPath();
            let started = false;
            for (let s = 0; s < SAMPLES; s++) {
                const sc = Cesium.SceneTransforms.wgs84ToWindowCoordinates(scene, worldPts[s]);
                if (!sc) { started = false; continue; }
                if (!started) { ctx.moveTo(sc.x, sc.y); started = true; }
                else ctx.lineTo(sc.x, sc.y);
            }
            // Close ring back to first visible projected point
            const sc0 = Cesium.SceneTransforms.wgs84ToWindowCoordinates(scene, worldPts[0]);
            if (sc0 && started) ctx.lineTo(sc0.x, sc0.y);
            ctx.stroke();
        } else {
            // Draw only visible arc segments as projected polyline runs
            let inRun = false, runPts = [];
            for (let k = 0; k <= SAMPLES; k++) {
                const s = (startIdx + k) % SAMPLES;
                const isVis = vis[s] && k < SAMPLES;
                if (isVis && !inRun) { inRun = true; runPts = []; }
                if (inRun) {
                    if (isVis) {
                        const sc = Cesium.SceneTransforms.wgs84ToWindowCoordinates(scene, worldPts[s]);
                        if (sc) runPts.push(sc); else inRun = false; // off-screen breaks run
                    }
                    if (!isVis || k === SAMPLES) {
                        if (runPts.length >= 2) {
                            ctx.beginPath();
                            ctx.moveTo(runPts[0].x, runPts[0].y);
                            for (let p = 1; p < runPts.length; p++) ctx.lineTo(runPts[p].x, runPts[p].y);
                            ctx.stroke();
                        }
                        inRun = false; runPts = [];
                    }
                }
            }
        }

        ctx.globalAlpha = 1;
        ctx.lineCap = 'butt';
    }
}

// ── Asset Filters (toggle collapse + status filter pills) ──
(function initAssetFilters() {
    const toggle = document.getElementById('assetFiltersToggle');
    const body   = document.getElementById('assetFiltersBody');
    const arrow  = document.getElementById('assetFiltersArrow');
    if (!toggle || !body || !arrow) return;

    // Toggle expand/collapse on header click
    toggle.addEventListener('click', () => {
        const open = body.classList.toggle('expanded');
        arrow.classList.toggle('expanded', open);
    });

    // Filter pill clicks — update _assetStatusFilter and re-render list immediately
    document.querySelectorAll('.filter-pill').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-pill').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            _assetStatusFilter = btn.dataset.filter;
            // Re-apply visibility to all existing drone cards without waiting for next WS tick
            document.querySelectorAll('#droneListContainer .drone-card').forEach(card => {
                card.style.display = (_assetStatusFilter === 'all' || card.dataset.mode === _assetStatusFilter) ? '' : 'none';
            });
        });
    });
})();

// ◯ button: OFF = terrain-projected ground halos (default); ON = flat+merge canvas halos
(function initHaloModeToggle() {
    const btn = document.getElementById('haloModeBtn');
    if (!btn) return;
    // Default is ground mode: button is dim/off, compass ring entity visible, ground rings built
    btn.style.opacity = '0.5';
    _updateGroundRings(); // build secondary ground rings for initial selection
    btn.addEventListener('click', () => {
        _haloMode = _haloMode === 'canvas' ? 'ground' : 'canvas';
        const isCanvas = _haloMode === 'canvas';
        compassRingEntity.polyline.show = !isCanvas;
        _updateGroundRings();
        // ON (bright) = canvas/merge mode; OFF (dim) = ground/terrain mode
        btn.style.opacity = isCanvas ? '1' : '0.5';
        viewer.scene.requestRender();
    });
})();

// ─── TARGET SYSTEM ────────────────────────────────────────────────────────────

const _targets = [];       // [{ id, lon, lat, topCone, botCone, lensTopCone, lensBotCone }]
window._targets = _targets; // Expose for React SearchBar target search
let _targetIdCounter = 0;

// NOTE: Cesium's DataSourceCollection does NOT support sharing one DataSource
// across two Viewer instances — the second .add() detaches it from the first.
// Instead we add entities directly to each viewer's own .entities collection
// and mirror them when the satellite lens viewer is opened.

function _diamondEntities(targetViewer, lon, lat, id) {
    const aboveGround = 80;   // metres above terrain surface
    const halfH  = 55;   // half-height of each cone
    const radius = 35;   // equatorial (widest) radius
    const color   = Cesium.Color.fromCssColorString('#f97316').withAlpha(0.88);
    const outline = Cesium.Color.fromCssColorString('#fdba74');
    const suffix  = targetViewer === viewer ? 'main' : 'lens';

    // Sample terrain height so diamonds sit above terrain, not ellipsoid
    let terrainH = 0;
    const carto = Cesium.Cartographic.fromDegrees(lon, lat);
    const globe = targetViewer.scene.globe;
    if (globe) {
        const sampledH = globe.getHeight(carto);
        if (sampledH !== undefined) terrainH = sampledH;
    }
    const alt = terrainH + aboveGround;

    // Upper cone: topRadius=0 → pointy tip at top, wide base at equator
    const topPos  = Cesium.Cartesian3.fromDegrees(lon, lat, alt + halfH / 2);
    const topCone = targetViewer.entities.add({
        id: `target_top_${id}_${suffix}`,
        position: topPos,
        cylinder: {
            length: halfH, topRadius: 0, bottomRadius: radius,
            material: color, outline: true, outlineColor: outline,
            outlineWidth: 1, numberOfVerticalLines: 0,
        },
    });

    // Lower cone: flip 180° pitch so tip points down
    const botPos  = Cesium.Cartesian3.fromDegrees(lon, lat, alt - halfH / 2);
    const flipped = Cesium.Transforms.headingPitchRollQuaternion(
        botPos, new Cesium.HeadingPitchRoll(0, Math.PI, 0));
    const botCone = targetViewer.entities.add({
        id: `target_bot_${id}_${suffix}`,
        position: botPos,
        orientation: flipped,
        cylinder: {
            length: halfH, topRadius: 0, bottomRadius: radius,
            material: color, outline: true, outlineColor: outline,
            outlineWidth: 1, numberOfVerticalLines: 0,
        },
    });

    return { topCone, botCone };
}

function _createTargetDiamond(lon, lat, type) {
    const id = ++_targetIdCounter;
    const targetType = type || 'unknown';

    // Add to main viewer
    const { topCone, botCone } = _diamondEntities(viewer, lon, lat, id);

    // Mirror to lens immediately if it's already open
    let lensTopCone = null, lensBotCone = null;
    if (_lensViewer) {
        ({ topCone: lensTopCone, botCone: lensBotCone } = _diamondEntities(_lensViewer, lon, lat, id));
        _lensViewer.scene.requestRender();
    }

    const target = { id, lon, lat, type: targetType, topCone, botCone, lensTopCone, lensBotCone };
    _targets.push(target);
    _renderTargetList();
    viewer.scene.requestRender();
    return target;
}

// Called by initSatelliteLens after _lensViewer is created to back-fill any
// targets that were placed before the lens was first opened.
function _syncTargetsToLens() {
    _targets.forEach(t => {
        if (t.lensTopCone) return; // already mirrored
        const { topCone, botCone } = _diamondEntities(_lensViewer, t.lon, t.lat, t.id);
        t.lensTopCone = topCone;
        t.lensBotCone = botCone;
    });
}

function _removeTarget(id) {
    const idx = _targets.findIndex(t => t.id === id);
    if (idx === -1) return;
    const t = _targets.splice(idx, 1)[0];
    viewer.entities.remove(t.topCone);
    viewer.entities.remove(t.botCone);
    if (_lensViewer) {
        if (t.lensTopCone) _lensViewer.entities.remove(t.lensTopCone);
        if (t.lensBotCone) _lensViewer.entities.remove(t.lensBotCone);
        _lensViewer.scene.requestRender();
    }
    _renderTargetList();
    viewer.scene.requestRender();
}

function _renderTargetList() {
    const container = document.getElementById('targetListContainer');
    if (!container) return;
    if (_targets.length === 0) {
        container.innerHTML = '<div class="empty-state">No targets. Use + to paint.</div>';
        return;
    }
    container.innerHTML = '';
    _targets.forEach(t => {
        const card = document.createElement('div');
        card.className = 'target-card';
        card.innerHTML = `
            <div class="target-card-diamond"></div>
            <span class="target-card-id">TGT-${String(t.id).padStart(3, '0')}</span>
            <span class="target-card-coords">${t.lat.toFixed(3)}° ${t.lon.toFixed(3)}°</span>
            <button class="target-card-remove" title="Remove target">✕</button>
        `;
        card.querySelector('.target-card-remove').addEventListener('click', (e) => {
            e.stopPropagation();
            _removeTarget(t.id);
        });
        card.addEventListener('click', () => {
            viewer.camera.flyTo({
                destination: Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 5000),
                orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 },
                duration: 1.2
            });
        });
        container.appendChild(card);
    });
}

(function initTargets() {
    // Wire paint button
    const paintBtn = document.getElementById('paintTargetBtn');
    if (!paintBtn) return;

    // Register paint_target tool with MapToolController
    MapToolController.registerTool({
        id: 'paint_target',
        label: 'Paint Target',
        hint: 'Click globe to place a target diamond.',

        onActivate() {
            paintBtn.classList.add('active');
            viewer.canvas.classList.add('paint-target-cursor');
        },
        onDeactivate() {
            paintBtn.classList.remove('active');
            viewer.canvas.classList.remove('paint-target-cursor');
        },
        onLeftClick(movement) {
            let cartesian = viewer.scene.pickPosition(movement.position);
            if (!cartesian) {
                cartesian = viewer.camera.pickEllipsoid(movement.position, viewer.scene.globe.ellipsoid);
            }
            if (!cartesian) return;
            const carto = Cesium.Cartographic.fromCartesian(cartesian);
            const lon = Cesium.Math.toDegrees(carto.longitude);
            const lat = Cesium.Math.toDegrees(carto.latitude);
            _createTargetDiamond(lon, lat);
            // Stay in paint mode for multi-target placement
        },
    });

    paintBtn.addEventListener('click', () => {
        const current = MapToolController.getActiveTool();
        if (current === 'paint_target') {
            MapToolController.setTool('select');
        } else {
            MapToolController.setTool('paint_target');
        }
    });

    // Wire collapsible target filters
    const toggle = document.getElementById('targetFiltersToggle');
    const body   = document.getElementById('targetFiltersBody');
    const arrow  = document.getElementById('targetFiltersArrow');
    if (toggle && body && arrow) {
        toggle.addEventListener('click', () => {
            const expanded = body.classList.toggle('expanded');
            arrow.classList.toggle('expanded', expanded);
        });
    }
})();

// Satellite lens — Bing aerial clipped to compass ring, toggled from the dropdown menu
(function initSatelliteLens() {
    const lensEl = document.createElement('div');
    lensEl.id = 'satellite-lens';
    lensEl.style.display = 'none';
    document.getElementById('cesiumContainer').appendChild(lensEl);
})();

function _toggleSatelliteLens() {
    _lensActive = !_lensActive;
    const lensEl = document.getElementById('satellite-lens');
    if (_lensActive) {
        if (!_lensViewer) {
            const creditSink = document.createElement('div');
            _lensViewer = new Cesium.Viewer(lensEl, {
                animation: false, baseLayerPicker: false, fullscreenButton: false,
                geocoder: false, homeButton: false, infoBox: false,
                sceneModePicker: false, selectionIndicator: false, timeline: false,
                navigationHelpButton: false,
                creditContainer: creditSink, creditViewport: creditSink,
            });
            _lensViewer.imageryLayers.removeAll();
            Cesium.IonImageryProvider.fromAssetId(2).then(provider => {
                _lensViewer.imageryLayers.addImageryProvider(provider);
                _lensViewer.scene.requestRender();
            });
            _lensViewer.scene.requestRenderMode = true;
            _lensViewer.scene.maximumRenderTimeChange = Infinity;
            _lensViewer.scene.screenSpaceCameraController.enableInputs = false;
            // Back-fill any targets painted before the lens was first opened
            _syncTargetsToLens();
            _lensViewer.entities.add({
                id: 'lens_compass',
                polyline: {
                    positions: new Cesium.CallbackProperty(() => {
                        const center = getCompassCenter();
                        if (!center) return [];
                        const transform = Cesium.Transforms.eastNorthUpToFixedFrame(center);
                        let fwd = new Cesium.Cartesian3(0.0, 2000.0 * _compassScale, 0.0);
                        if (trackedDroneEntity) {
                            let heading = 0.0;
                            const markerId = trackedDroneEntity.id.replace('uav_', '');
                            if (uavEntities[markerId] && uavEntities[markerId]._lastHeading !== undefined) {
                                heading = uavEntities[markerId]._lastHeading - Math.PI;
                            }
                            const rotMatrix = Cesium.Matrix3.fromRotationZ(-heading);
                            Cesium.Matrix3.multiplyByVector(rotMatrix, fwd, fwd);
                        }
                        const worldFwd = new Cesium.Cartesian3();
                        Cesium.Matrix4.multiplyByPoint(transform, fwd, worldFwd);
                        return [center, worldFwd];
                    }, false),
                    width: 3, material: Cesium.Color.fromCssColorString('#facc15'), clampToGround: false
                }
            });
            _lensViewer.entities.add({
                id: 'lens_compassRing',
                polyline: {
                    positions: new Cesium.CallbackProperty(() => {
                        const center = getCompassCenter();
                        if (!center) return [];
                        const radius = 1500.0 * _compassScale;
                        const xf = Cesium.Transforms.eastNorthUpToFixedFrame(center);
                        const pts = [], local = new Cesium.Cartesian3();
                        for (let i = 0; i <= 64; i++) {
                            const a = (i / 64) * Math.PI * 2;
                            local.x = Math.cos(a) * radius; local.y = Math.sin(a) * radius; local.z = 0;
                            pts.push(Cesium.Matrix4.multiplyByPoint(xf, local, new Cesium.Cartesian3()));
                        }
                        return pts;
                    }, false),
                    width: 3, material: Cesium.Color.fromCssColorString('#facc15').withAlpha(0.6), clampToGround: false
                }
            });
            _lensViewer.entities.add({
                id: 'lens_drone',
                position: new Cesium.CallbackProperty(() =>
                    trackedDroneEntity ? trackedDroneEntity.position.getValue(viewer.clock.currentTime) : undefined, false),
                billboard: {
                    image: new Cesium.CallbackProperty(() => {
                        if (!trackedDroneEntity) return getDronePin('#3b82f6');
                        const marker = uavEntities[trackedDroneEntity.id.replace('uav_', '')];
                        return getDronePin((marker && marker._lastMode) ? marker._lastMode : '#3b82f6');
                    }, false),
                    verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                    heightReference: Cesium.HeightReference.NONE,
                    scale: 1.0,
                    show: new Cesium.CallbackProperty(() => !!trackedDroneEntity, false)
                }
            });
        }
        lensEl.style.display = 'block';
        viewer.scene.requestRender();
    } else {
        lensEl.style.display = 'none';
    }
}

// Shift+scroll to resize the compass cursor
viewer.canvas.addEventListener('wheel', (e) => {
    if (!e.shiftKey) return;
    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    _compassScale = Math.max(0.1, Math.min(10.0, _compassScale * factor));
    viewer.scene.requestRender();
}, { passive: false });

// Macro tracking state now lives in MapToolController
viewer.scene.preUpdate.addEventListener(function(scene, time) {
    // Sync the legacy trackedDroneEntity variable from the controller
    trackedDroneEntity = MapToolController.getTrackedDroneEntity();
    // Delegate macro camera nudging to the controller
    MapToolController.tickMacroTracking();
});

// Mouse move now handled by MapToolController; sync currentMousePosition for compass
// Request continuous renders during paint mode so crosshair follows mouse smoothly
viewer.canvas.addEventListener('mousemove', () => {
    if (_paintCrosshairActive) {
        viewer.scene.requestRender();
    }
});

viewer.scene.postRender.addEventListener(() => {
    if (MapToolController._currentMousePosition) {
        currentMousePosition = MapToolController._currentMousePosition;
    }
    _renderHalos();

    if (!_lensActive || !_lensViewer) return;
    const center = getCompassCenter();
    if (!center) return;
    const transform = Cesium.Transforms.eastNorthUpToFixedFrame(center);
    const segments = 48;
    const polygonPts = [];
    for (let i = 0; i < segments; i++) {
        const angle = (i / segments) * Math.PI * 2;
        const worldPt = Cesium.Matrix4.multiplyByPoint(transform,
            new Cesium.Cartesian3(Math.cos(angle) * 1500.0 * _compassScale, Math.sin(angle) * 1500.0 * _compassScale, 0.0),
            new Cesium.Cartesian3());
        const screenPt = Cesium.SceneTransforms.wgs84ToWindowCoordinates(viewer.scene, worldPt);
        if (!screenPt) return;
        polygonPts.push(`${screenPt.x}px ${screenPt.y}px`);
    }
    document.getElementById('satellite-lens').style.clipPath = `polygon(${polygonPts.join(', ')})`;
    _lensViewer.camera.position  = viewer.camera.position.clone();
    _lensViewer.camera.direction = viewer.camera.direction.clone();
    _lensViewer.camera.up        = viewer.camera.up.clone();
    _lensViewer.camera.right     = viewer.camera.right.clone();
    _lensViewer.scene.requestRender();
});

// 5. WebSocket Logic
let ws = null;
let wsReconnectDelay = 1000;
const connStatus = document.getElementById('connStatus');

function connectWebSocket() {
    const wsUrl = `ws://localhost:8012/ws/stream`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        if (connStatus) { connStatus.textContent = "Uplink Active"; connStatus.className = "stat-value connected"; }
        wsReconnectDelay = 1000; // reset on success
        MapToolController.setWebSocket(ws);
    };

    ws.onclose = () => {
        if (connStatus) { connStatus.textContent = "Signal Lost"; connStatus.className = "stat-value disconnected"; }
        setTimeout(connectWebSocket, wsReconnectDelay);
        wsReconnectDelay = Math.min(wsReconnectDelay * 2, 30000);
    };

    ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === "state") {
            // Buffer snapshot for timeline scrubbing
            if (typeof AppState !== 'undefined') {
                AppState.pushSnapshot(payload.data);
            }

            // Only update the 3D map if we're in live mode (not scrubbing)
            if (typeof AppState === 'undefined' || AppState.state.timeMode === 'live') {
                updateSimulation(payload.data);
            }

            // Bridge live sim state into AppState for React panels (throttled to ~2Hz, only in live mode)
            if (!window._lastReactBridgeMs) window._lastReactBridgeMs = 0;
            if (!window._prevUavPos) window._prevUavPos = {};
            const _now = Date.now();
            const _isLive = typeof AppState === 'undefined' || AppState.state.timeMode === 'live';
            if (_isLive && typeof AppState !== 'undefined' && payload.data.uavs && (_now - window._lastReactBridgeMs) > 500) {
                window._lastReactBridgeMs = _now;
                payload.data.uavs.forEach(u => {
                    // Compute heading from position delta (sim doesn't send vx/vy)
                    const prev = window._prevUavPos[u.id];
                    let hdg = 0;
                    if (prev) {
                        const dlon = u.lon - prev.lon;
                        const dlat = u.lat - prev.lat;
                        if (Math.abs(dlon) > 0.0001 || Math.abs(dlat) > 0.0001) {
                            hdg = ((Math.atan2(dlon * Math.cos(u.lat * Math.PI / 180), dlat) * 180 / Math.PI) + 360) % 360;
                        } else {
                            hdg = prev.hdg || 0; // Keep last heading when stationary
                        }
                    }
                    window._prevUavPos[u.id] = { lon: u.lon, lat: u.lat, hdg: hdg };

                    // Update the canonical uav_N entry (React filters on this prefix)
                    AppState.updateAsset({
                        id: `uav_${u.id}`,
                        name: `Fixed - ${String(u.id + 1).padStart(2, '0')}`,
                        type: 'quadrotor',
                        mode: u.mode,
                        status: u.mode === 'serving' ? 'on_task' : u.mode === 'repositioning' ? 'transiting' : 'idle',
                        health: 'nominal',
                        position: { lat: u.lat, lon: u.lon, alt_m: 1000 },
                        heading_deg: hdg,
                        battery_pct: typeof u.battery_pct === 'number' ? u.battery_pct : 100 - (u.id * 0.3) - (_now % 60000) / 60000 * 2,
                        link_quality: typeof u.link_quality === 'number' ? u.link_quality : 0.92 + Math.sin(u.id + _now / 10000) * 0.06,
                    });
                });
            }
        }
    };
}
connectWebSocket();

// 5.1 New Event WebSocket (for domain events)
if (typeof WsClient !== 'undefined') {
    WsClient.connect();
}

// 5.2 Timeline scrub → replay historical snapshots on the 3D map
//     Uses a lightweight renderer that directly sets entity positions
//     WITHOUT adding samples to the SampledPositionProperty interpolation buffer.
function scrubToSnapshot(state) {
    viewer.scene.requestRender();

    // Update zones + flows normally (these are stateless)
    initOrUpdateZonesPrimitive(state.zones);
    flowLines.forEach(f => viewer.entities.remove(f));
    flowLines.length = 0;
    state.flows.forEach(flow => {
        const line = viewer.entities.add({
            polyline: {
                positions: Cesium.Cartesian3.fromDegreesArrayHeights([
                    flow.source[0], flow.source[1], 2000,
                    flow.target[0], flow.target[1], 2000
                ]),
                width: 3,
                material: new Cesium.PolylineGlowMaterialProperty({
                    glowPower: 0.2,
                    color: Cesium.Color.CYAN
                }),
                arcType: Cesium.ArcType.GEODESIC
            }
        });
        flowLines.push(line);
    });

    // Bridge scrub state into AppState so React panels show historical data
    if (typeof AppState !== 'undefined') {
        state.uavs.forEach(u => {
            const prev = window._prevUavPos ? window._prevUavPos[u.id] : null;
            let hdg = prev ? prev.hdg || 0 : 0;
            if (prev) {
                const dlon = u.lon - prev.lon;
                const dlat = u.lat - prev.lat;
                if (Math.abs(dlon) > 0.0001 || Math.abs(dlat) > 0.0001) {
                    hdg = ((Math.atan2(dlon * Math.cos(u.lat * Math.PI / 180), dlat) * 180 / Math.PI) + 360) % 360;
                }
            }
            AppState.updateAsset({
                id: `uav_${u.id}`,
                name: `UAV-${String(u.id).padStart(2, '0')}`,
                type: 'quadrotor',
                mode: u.mode,
                status: u.mode === 'serving' ? 'on_task' : u.mode === 'repositioning' ? 'transiting' : 'idle',
                health: 'nominal',
                position: { lat: u.lat, lon: u.lon, alt_m: 1000 },
                heading_deg: hdg,
                battery_pct: 100 - (u.id * 0.3),
                link_quality: 0.92,
            });
        });
    }

    // Directly set UAV positions without touching the interpolation buffer
    state.uavs.forEach(uav => {
        const marker = uavEntities[uav.id];
        if (!marker) return;
        const position = Cesium.Cartesian3.fromDegrees(uav.lon, uav.lat, 1000);
        // Temporarily replace the SampledPositionProperty with a constant
        if (!marker._livePosProperty) {
            marker._livePosProperty = marker.position; // stash the real one
        }
        marker.position = new Cesium.ConstantPositionProperty(position);

        // Update color
        let colorStr = '#3b82f6';
        if (uav.mode === "serving") colorStr = '#22c55e';
        else if (uav.mode === "repositioning") colorStr = '#eab308';
        if (marker._lastMode !== colorStr) {
            marker.billboard.image = getDronePin(colorStr);
            marker.point.color = Cesium.Color.fromCssColorString(colorStr);
            marker._lastMode = colorStr;
        }
    });
    viewer.scene.requestRender();
}

function restoreLivePositions() {
    // Restore the SampledPositionProperty on each marker and reset timing
    Object.keys(uavEntities).forEach(id => {
        const marker = uavEntities[id];
        if (marker._livePosProperty) {
            marker.position = marker._livePosProperty;
            delete marker._livePosProperty;
        }
        // Reset the interpolation buffer timing so next WS frame re-syncs cleanly
        marker._lastTargetTime = null;
    });
    viewer.scene.requestRender();
}

if (typeof AppState !== 'undefined') {
    AppState.subscribe('time.cursorChanged', (ms) => {
        if (ms === null) {
            // Returned to live — restore interpolation properties
            restoreLivePositions();
            return;
        }
        const snapshot = AppState.getSnapshotAt(ms);
        if (snapshot) {
            scrubToSnapshot(snapshot);
        }
    });
}

// 5.3 Initialize Panel Modules
if (typeof Toolbar !== 'undefined') {
    Toolbar.init();
    // Move scrub controls into timeline drawer header
    const drawerHeader = document.querySelector('.ws-timeline-drawer-header');
    const controls = Toolbar.getControlsElement();
    if (drawerHeader && controls) drawerHeader.appendChild(controls);
}
if (typeof MissionPanel !== 'undefined') MissionPanel.init();
if (typeof AlertsPanel !== 'undefined') AlertsPanel.init();
if (typeof InspectorPanel !== 'undefined') InspectorPanel.init();
if (typeof TimelinePanel !== 'undefined') TimelinePanel.init();
if (typeof MacrogridPanel !== 'undefined') MacrogridPanel.init();

// 6. UI Interaction
let showAllWaypoints = false;

document.getElementById('toggleGridBtn').addEventListener('click', (e) => {
    gridVisState = (gridVisState + 1) % 3;

    if (zonesPrimitive) {
        zonesPrimitive.show = (gridVisState === 2);
    }
    if (zoneBordersPrimitive) {
        zoneBordersPrimitive.show = (gridVisState === 1 || gridVisState === 2);
    }

    const btn = e.target;
    btn.classList.remove('square-btn-on', 'square-btn-outlines');
    if (gridVisState === 2) {
        btn.classList.add('square-btn-on');
    } else if (gridVisState === 1) {
        btn.classList.add('square-btn-outlines');
    }
    viewer.scene.requestRender();
});

document.getElementById('toggleWaypointsBtn').addEventListener('click', (e) => {
    showAllWaypoints = !showAllWaypoints;
    const btn = e.target;
    if (showAllWaypoints) {
        btn.classList.add('square-btn-on');
    } else {
        btn.classList.remove('square-btn-on');
    }
    
    // Force immediate visual update
    let currentTrackedId = null;
    if (trackedDroneEntity) {
        currentTrackedId = parseInt(trackedDroneEntity.id.replace('uav_', ''));
    }
    Object.keys(droneWaypoints).forEach(idStr => {
        const id = parseInt(idStr);
        const wp = droneWaypoints[id];
        const isVisible = showAllWaypoints || (id === currentTrackedId);
        wp.waypoint.show = isVisible;
        wp.trajectory.show = isVisible;
    });
    viewer.scene.requestRender();
});

// Tab switching is now handled by WorkspaceShell

// Overscroll bounce effect for Drone List
const tabDrones = document.getElementById('tab-drones');
const droneListContainer = document.getElementById('droneListContainer');
let isBouncing = false;
let hasBouncedTop = false;
let hasBouncedBottom = false;

tabDrones.addEventListener('wheel', (e) => {
    if (isBouncing) return;
    
    const isAtTop = tabDrones.scrollTop <= 0;
    const isAtBottom = tabDrones.scrollTop + tabDrones.clientHeight >= tabDrones.scrollHeight - 1;

    // Reset bounce flags if user scrolls away from the boundaries
    if (!isAtTop) hasBouncedTop = false;
    if (!isAtBottom) hasBouncedBottom = false;
    
    if (e.deltaY < 0 && isAtTop && !hasBouncedTop) {
        isBouncing = true;
        hasBouncedTop = true;
        droneListContainer.classList.add('scroll-bounce-top');
        setTimeout(() => {
            droneListContainer.classList.remove('scroll-bounce-top');
            isBouncing = false;
        }, 400);
    } else if (e.deltaY > 0 && isAtBottom && !hasBouncedBottom) {
        isBouncing = true;
        hasBouncedBottom = true;
        droneListContainer.classList.add('scroll-bounce-bottom');
        setTimeout(() => {
            droneListContainer.classList.remove('scroll-bounce-bottom');
            isBouncing = false;
        }, 400);
    }
}, { passive: true });

document.getElementById('resetQueueBtn').addEventListener('click', () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: "reset" }));
    }
});

// returnGlobalBtn and decoupleCameraBtn handlers now live in MapToolController

// triggerDroneSelection now lives in MapToolController._triggerDroneSelection
function triggerDroneSelection(entity, viewMode = 'macro') {
    MapToolController._triggerDroneSelection(entity, viewMode);
}

// Click handlers, waypoint placement, and isSettingWaypoint now live in MapToolController.
// droneWaypoints is accessed via MapToolController.getDroneWaypoints() for legacy reads.
let isSettingWaypoint = false; // legacy read-bridge; toggled by waypoint button code below
const droneWaypoints = MapToolController.getDroneWaypoints();

// Sidebar resizing is now handled by WorkspaceShell splitters

// ----------------------------------------------------
// GRID 9: DETAIL WAYPOINT MODAL LOGIC (Picture-in-Picture)
// ----------------------------------------------------

// 1. Initialize the secondary viewer in the hidden modal
const detailViewer = new Cesium.Viewer('detailMapContainer', {
    terrain: Cesium.Terrain.fromWorldTerrain(),
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    infoBox: false,
    navigationHelpButton: false,
    sceneModePicker: false,
    timeline: false,
    animation: false,
    fullscreenButton: false,
    selectionIndicator: false
});

// Configure Palantir-style Cinematic Lighting & Dark Mode for the detail viewer matching the main viewer exactly
detailViewer.imageryLayers.removeAll();
const detailBaseLayer = detailViewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
    url: 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'
}));
detailBaseLayer.brightness = 1.8;
detailBaseLayer.gamma = 1.2;
detailViewer.scene.globe.baseColor = Cesium.Color.BLACK;
detailViewer.scene.backgroundColor = Cesium.Color.BLACK;
detailViewer.scene.globe.enableLighting = true; 
detailViewer.scene.globe.depthTestAgainstTerrain = true; 
detailViewer.scene.skyAtmosphere.hueShift = -0.5; 
detailViewer.scene.skyAtmosphere.brightnessShift = -0.8;
detailViewer.scene.fog.enabled = true;
detailViewer.scene.fog.density = 0.0001;

// Lock the camera entirely so the user cannot accidentally pan/zoom/tilt the detail map
detailViewer.scene.screenSpaceCameraController.enableRotate = false;
detailViewer.scene.screenSpaceCameraController.enableTranslate = false;
detailViewer.scene.screenSpaceCameraController.enableZoom = false;
detailViewer.scene.screenSpaceCameraController.enableTilt = false;
detailViewer.scene.screenSpaceCameraController.enableLook = false;

// Freeze time to match the main viewer so the sun/shadows don't move and create a sliding illusion
detailViewer.clock.currentTime = Cesium.JulianDate.fromIso8601("2023-06-21T10:00:00Z");
detailViewer.clock.shouldAnimate = false;

// 2. State & Constraints
let detailActiveDroneId = null;
const CONSTRAINT_RADIUS_METERS = 150000.0; // 150 km

// 3. Create the Range Constraint Ring (150km Red Circle)
const rangeConstraintEntity = detailViewer.entities.add({
    name: 'Range Constraint',
    position: Cesium.Cartesian3.fromDegrees(0, 0), // Default, will update dynamically
    ellipse: {
        semiMajorAxis: CONSTRAINT_RADIUS_METERS,
        semiMinorAxis: CONSTRAINT_RADIUS_METERS,
        material: Cesium.Color.RED.withAlpha(0.15),
        outline: true,
        outlineColor: Cesium.Color.RED.withAlpha(0.6),
        outlineWidth: 2,
        height: 0 // Keep locked to surface
    }
});

// Create a visual marker for the drone itself in the detail view
const detailDroneMarker = detailViewer.entities.add({
    name: 'Detail Target Drone',
    position: Cesium.Cartesian3.fromDegrees(0, 0),
    billboard: {
        image: getDronePin('#facc15'), // Gold star/pin
        scale: 0.8,
        verticalOrigin: Cesium.VerticalOrigin.CENTER
    }
});

// 4. Modal Open/Close wiring
const detailModal = document.getElementById('detailMapModal');
const closeDetailBtn = document.getElementById('closeDetailMapBtn');

closeDetailBtn.addEventListener('click', () => {
    detailModal.style.display = 'none';
    detailActiveDroneId = null;
});

window.openDetailMapModal = function(droneData) {
    if (!droneData) return;
    
    // Unhide the modal
    detailModal.style.display = 'flex';
    detailActiveDroneId = droneData.id;
    
    // The modal was display:none, so its clientWidth was 0.
    // We must force Cesium to resize its WebGL context now that it has physical layout bounds.
    detailViewer.resize();
    
    const dronePos = Cesium.Cartesian3.fromDegrees(droneData.lon, droneData.lat);
    
    // Move the constraint circle and marker to the exact drone position
    rangeConstraintEntity.position = dronePos;
    detailDroneMarker.position = dronePos;
    
    // Instantly teleport the overhead camera without triggering animation drift
    detailViewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(droneData.lon, droneData.lat, 400000.0), // 400km up
        orientation: {
            heading: 0.0,
            pitch: Cesium.Math.toRadians(-90.0), // Look straight down
            roll: 0.0
        }
    });
};

// 5. Constrained Picking Logic inside the Detail Viewer
detailViewer.screenSpaceEventHandler.setInputAction(function onDetailMapClick(movement) {
    if (!detailActiveDroneId) return;
    
    // Pick the globe coordinates where the user clicked inside the detail map
    let cartesian = detailViewer.scene.pickPosition(movement.position);
    if (!cartesian) {
        cartesian = detailViewer.camera.pickEllipsoid(movement.position, detailViewer.scene.globe.ellipsoid);
    }
    
    if (cartesian) {
        // Find the center point of our active drone
        const centerPos = rangeConstraintEntity.position.getValue(Cesium.JulianDate.now());
        
        // Calculate raw 3D distance
        const distanceMeters = Cesium.Cartesian3.distance(centerPos, cartesian);
        
        if (distanceMeters <= CONSTRAINT_RADIUS_METERS) {
            // VALID CLICK (inside the 150km ring)
            
            // Extract Lon/Lat for the backend
            const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
            const lon = Cesium.Math.toDegrees(cartographic.longitude);
            const lat = Cesium.Math.toDegrees(cartographic.latitude);
            
            // Delegate waypoint placement to MapToolController (handles WS + visuals)
            MapToolController._placeWaypoint(detailActiveDroneId, cartesian);
            
            // Close the form
            detailModal.style.display = 'none';
            detailActiveDroneId = null;
            
        } else {
            // INVALID CLICK (Outside the 150km range constraint)
            // Visually flash the ring to let the user know they clicked out of bounds
            const origMat = rangeConstraintEntity.ellipse.material;
            rangeConstraintEntity.ellipse.material = Cesium.Color.fromCssColorString('#fbbf24').withAlpha(0.6); // Flash yellow/amber
            
            setTimeout(() => {
                rangeConstraintEntity.ellipse.material = origMat;
            }, 150);
        }
    }
}, Cesium.ScreenSpaceEventType.LEFT_CLICK);
