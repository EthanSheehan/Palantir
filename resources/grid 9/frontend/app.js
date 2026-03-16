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
viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
    url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}.png?api_key=74c21d3f-b418-4db6-9318-ffb876f1f071'
}));

// Configure Palantir-style Cinematic Lighting & Dark Mode
viewer.scene.globe.baseColor = Cesium.Color.BLACK;
viewer.scene.backgroundColor = Cesium.Color.BLACK;
viewer.scene.globe.enableLighting = true; 
viewer.scene.globe.depthTestAgainstTerrain = true; 

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



viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(24.9668, 41.2, 500000.0), 
    orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-45.0),
        roll: 0.0
    },
    duration: 0 
});

// 2. Data Structures for ultra-fast rendering
let zonesPrimitive = null;
let zoneBordersPrimitive = null;
let gridVisState = 2; // 2 = ON, 1 = OUTLINES ONLY, 0 = OFF
const zoneAttributesCache = {}; // Cache to prevent lookup overhead
const flowLines = []; 
const uavEntities = {};

// Dictionary to track active 3D Range visualizations { uavId: [Entity, Entity...] }
const droneRangeVisuals = {};

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
function getImbalanceColor(imbalance) {
    const imb = Math.max(-20, Math.min(20, imbalance));
    let color;
    if (imb < 0) {
        const intensity = Math.abs(imb) / 20.0;
        color = Cesium.Color.fromCssColorString('rgba(239, 68, 68, 1.0)').withAlpha(0.2 + (intensity * 0.4));
    } else if (imb > 0) {
        const intensity = imb / 20.0;
        color = Cesium.Color.fromCssColorString('rgba(59, 130, 246, 1.0)').withAlpha(0.2 + (intensity * 0.4));
    } else {
        color = new Cesium.Color(0, 0, 0, 0.0);
    }
    return color;
}

// Ensure the Primitive is built once, then we only update its instance attributes
function initOrUpdateZonesPrimitive(stateZones) {
    if (!zonesPrimitive) {
        console.log("Building GroundPrimitive for", stateZones.length, "zones.");
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

    // 4.2 Update Flows 
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
                    color: Cesium.Color.CYAN // Palantir style flows
                }),
                arcType: Cesium.ArcType.GEODESIC
            }
        });
        flowLines.push(line);
    });

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
                name: `UAV-${uav.id}`,
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
    
    document.getElementById('uavCount').textContent = state.uavs.length;
    document.getElementById('zoneCount').textContent = state.zones.length;
    
    // Determine currently tracked drone ID
    let currentTrackedId = null;
    if (trackedDroneEntity) {
        currentTrackedId = parseInt(trackedDroneEntity.id.replace('uav_', ''));
    }
    
    // Update Sidebar Drone List
    const listContainer = document.getElementById('droneListContainer');
    if (state.uavs.length === 0) {
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
                
                card.addEventListener('click', () => {
                    if (card.clickTimer) clearTimeout(card.clickTimer);
                    card.clickTimer = setTimeout(() => {
                        const entity = viewer.entities.getById(`uav_${u.id}`);
                        if (entity) triggerDroneSelection(entity, 'macro');
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
            
            // Check tracking state
            const isTracked = (u.id === currentTrackedId);
            const cardBg = isTracked ? 'rgba(250, 204, 21, 0.15)' : ''; 
            const cardBorderColor = isTracked ? 'rgba(250, 204, 21, 0.5)' : '';
            const idColor = isTracked ? '#facc15' : ''; // Pale gold
            
            // Re-render inner content only if status or tracking changes
            if (card.dataset.mode !== u.mode || card.dataset.tracked !== String(isTracked)) {
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
                card.dataset.tracked = String(isTracked);
                
                // Keep the styling updated
                if (isTracked) {
                    card.style.background = cardBg;
                    card.style.borderColor = cardBorderColor;
                    
                    // Attach dynamic waypoint listener to the newly generated buttons
                    const wpBtn = card.querySelector('.btn-primary');
                    const detailBtn = card.querySelector('.btn-secondary');
                    
                    if (wpBtn) {
                        wpBtn.addEventListener('click', (e) => {
                            e.stopPropagation(); // Don't trigger the card's tracking click
                            isSettingWaypoint = !isSettingWaypoint;
                            if (isSettingWaypoint) {
                                wpBtn.textContent = 'Select Target...';
                                wpBtn.style.background = 'rgba(34, 197, 94, 0.2)';
                                wpBtn.style.borderColor = 'rgba(34, 197, 94, 0.5)';
                                wpBtn.style.color = '#22c55e';
                            } else {
                                wpBtn.textContent = 'Set Waypoint';
                                wpBtn.style.background = '';
                                wpBtn.style.borderColor = '';
                                wpBtn.style.color = '';
                            }
                        });
                        
                        // Sync visual state if they are currently setting a waypoint
                        if (isSettingWaypoint) {
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
                                            outlineColor: Cesium.Color.fromCssColorString('#38bdf8').withAlpha(0.5 - (0.2 * t)),
                                            outlineWidth: 2
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
                } else {
                    card.style.background = '';
                    card.style.borderColor = '';
                }
            }
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
let currentMousePosition = null;
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
            let fwd = new Cesium.Cartesian3(0.0, 2000.0, 0.0);
            
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
        positions: new Cesium.CallbackProperty(() => {
            const center = getCompassCenter();
            if (!center) return [];
            
            const radius = 1500.0;
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

let macroTrackedId = null;
let isMacroTrackingReady = false;
let lastDronePosition = null;

viewer.scene.preUpdate.addEventListener(function(scene, time) {
    if (macroTrackedId && isMacroTrackingReady && !viewer.trackedEntity) {
        const drone = uavEntities[macroTrackedId];
        if (drone && drone.position) {
            const pos = drone.position.getValue(time);
            if (pos) {
                if (lastDronePosition) {
                    // Calculate exactly how far the drone moved this frame
                    const deltaX = pos.x - lastDronePosition.x;
                    const deltaY = pos.y - lastDronePosition.y;
                    const deltaZ = pos.z - lastDronePosition.z;
                    
                    // Nudge the camera by the exact same physical amount
                    viewer.camera.position.x += deltaX;
                    viewer.camera.position.y += deltaY;
                    viewer.camera.position.z += deltaZ;
                }
                lastDronePosition = pos;
            } else {
                lastDronePosition = null;
            }
        }
    } else {
        lastDronePosition = null;
    }
});

viewer.screenSpaceEventHandler.setInputAction(function onMouseMove(movement) {
    if (!trackedDroneEntity) {
        // Only track mouse if we aren't tracking a drone
        let cartesian = viewer.scene.pickPosition(movement.endPosition);
        if (!cartesian) {
            cartesian = viewer.camera.pickEllipsoid(movement.endPosition, viewer.scene.globe.ellipsoid);
        }
        
        if (cartesian) {
            currentMousePosition = cartesian;
            viewer.scene.requestRender();
        }
    }
}, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

// 5. WebSocket Logic
let ws = null;
const connStatus = document.getElementById('connStatus');

function connectWebSocket() {
    const wsUrl = `ws://localhost:8010/ws/stream`;
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        connStatus.textContent = "Uplink Active";
        connStatus.className = "stat-value connected";
    };
    
    ws.onclose = () => {
        connStatus.textContent = "Signal Lost";
        connStatus.className = "stat-value disconnected";
        setTimeout(connectWebSocket, 1000);
    };
    
    ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === "state") {
            console.log(`Received state with ${payload.data.uavs.length} uavs and ${payload.data.zones.length} zones`);
            if (payload.data.uavs.length > 0) {
                 console.log("First UAV:", payload.data.uavs[0]);
            }
            updateSimulation(payload.data);
        }
    };
}
connectWebSocket();

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
    if (gridVisState === 2) {
        btn.textContent = 'Grid Visibility: ON';
        btn.style.borderColor = 'rgba(56, 189, 248, 0.5)';
        btn.style.color = '#38bdf8';
    } else if (gridVisState === 1) {
        btn.textContent = 'Grid Visibility: SQUARES ONLY';
        btn.style.borderColor = 'rgba(167, 139, 250, 0.5)';
        btn.style.color = '#a78bfa';
    } else {
        btn.textContent = 'Grid Visibility: OFF';
        btn.style.borderColor = 'rgba(148, 163, 184, 0.2)';
        btn.style.color = '#e2e8f0';
    }
    viewer.scene.requestRender();
});

document.getElementById('toggleWaypointsBtn').addEventListener('click', (e) => {
    showAllWaypoints = !showAllWaypoints;
    const btn = e.target;
    if (showAllWaypoints) {
        btn.textContent = 'All Waypoints: ON';
        btn.style.borderColor = 'rgba(56, 189, 248, 0.5)';
        btn.style.color = '#38bdf8';
    } else {
        btn.textContent = 'All Waypoints: OFF';
        btn.style.borderColor = 'rgba(148, 163, 184, 0.2)';
        btn.style.color = '#e2e8f0';
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

document.querySelectorAll('.tab-btn').forEach(button => {
    button.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(pane => pane.classList.remove('active-tab'));
        button.classList.add('active');
        const targetId = button.getAttribute('data-tab');
        document.getElementById(targetId).classList.add('active-tab');
    });
});

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

document.getElementById('returnGlobalBtn').addEventListener('click', () => {
    if (trackedDroneEntity) {
        trackedDroneEntity.viewFrom = undefined;
    }
    trackedDroneEntity = null;
    viewer.trackedEntity = undefined;
    macroTrackedId = null;
    isMacroTrackingReady = false;
    isSettingWaypoint = false;
    
    viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
    viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(24.9668, 41.2, 500000.0), 
        orientation: {
            heading: Cesium.Math.toRadians(0),
            pitch: Cesium.Math.toRadians(-45.0),
            roll: 0.0
        },
        duration: 1.5 
    });
    
    document.getElementById('cameraControls').style.display = 'none';
});

document.getElementById('decoupleCameraBtn').addEventListener('click', () => {
    if (trackedDroneEntity) {
        trackedDroneEntity.viewFrom = undefined;
    }
    trackedDroneEntity = null;
    viewer.trackedEntity = undefined;
    macroTrackedId = null;
    isMacroTrackingReady = false;
    isSettingWaypoint = false;
    
    // Detach from the drone coordinate frame smoothly
    viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
    
    document.getElementById('cameraControls').style.display = 'none';
});

function triggerDroneSelection(entity, viewMode = 'macro') {
    document.getElementById('cameraControls').style.display = 'flex';
    
    // Instantly snap compass to the drone
    trackedDroneEntity = entity;
    
    // Temporarily disable tracking while we smoothly fly into position
    viewer.trackedEntity = undefined;
    
    // Release any lingering coordinate transforms
    if (viewer.camera.transform && !viewer.camera.transform.equals(Cesium.Matrix4.IDENTITY)) {
        viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
    }
    
    macroTrackedId = null;
    isMacroTrackingReady = false;
    lastDronePosition = null;
    
    if (viewMode === 'thirdPerson') {
        // Double Click: 3rd person view, locked closely behind and looking matching drone heading
        entity.viewFrom = undefined; 
        viewer.flyTo(entity, {
            duration: 1.5,
            offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-15), 150)
        }).then(function(result) {
            if (result && trackedDroneEntity === entity) {
                // Hard lock tracking only AFTER we smoothly arrive
                entity.viewFrom = new Cesium.Cartesian3(0, -100, 30); 
                viewer.trackedEntity = entity;
            }
        });
    } else {
        // Single Click: Moderate zoom (2km), preserve existing camera orientation
        entity.viewFrom = undefined; 
        
        const currentHeading = viewer.camera.heading;
        const currentPitch = Math.min(viewer.camera.pitch, Cesium.Math.toRadians(-20)); // Ensure we aren't completely flat
        
        // viewer.flyTo natively follows dynamic entities during the flight
        viewer.flyTo(entity, {
            duration: 1.5,
            offset: new Cesium.HeadingPitchRange(currentHeading, currentPitch, 10000) 
        }).then(function(result) {
            if (result && trackedDroneEntity === entity) {
                // Enable Cartesian nudging instead of trackedEntity snapping
                macroTrackedId = parseInt(entity.id.replace('uav_', ''));
                isMacroTrackingReady = true;
            }
        });
    }
}

// Third-Person UAV Tracking logic
let isSettingWaypoint = false;
const droneWaypoints = {}; // Dictionary to store per-drone waypoints as { waypoint: Entity, trajectory: Entity }

viewer.screenSpaceEventHandler.setInputAction(function onLeftClick(movement) {
    // Only intercept if we are actively setting a waypoint
    if (isSettingWaypoint && trackedDroneEntity) {
        let cartesian = viewer.scene.pickPosition(movement.position);
        if (!cartesian) {
            cartesian = viewer.camera.pickEllipsoid(movement.position, viewer.scene.globe.ellipsoid);
        }
        
        if (cartesian) {
            var cartographic = Cesium.Cartographic.fromCartesian(cartesian);
            var lon = Cesium.Math.toDegrees(cartographic.longitude);
            var lat = Cesium.Math.toDegrees(cartographic.latitude);
            
            const markerId = trackedDroneEntity.id.replace('uav_', '');
            const dId = parseInt(markerId);
            
            // Grab the inline button that was dynamically generated in the active drone card
            const inlineBtn = document.getElementById(`inlineSetWaypointBtn_${dId}`);
            
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    action: "move_drone",
                    drone_id: dId,
                    target_lon: lon,
                    target_lat: lat
                }));
            }
            
            // Draw destination marker and save to dictionary
            if (!droneWaypoints[dId]) {
                const waypointEntity = viewer.entities.add({
                    position: cartesian,
                    cylinder: {
                        length: 2000.0,
                        topRadius: 20.0,
                        bottomRadius: 20.0,
                        material: Cesium.Color.fromCssColorString('#22c55e').withAlpha(0.6),
                        outline: true,
                        outlineColor: Cesium.Color.fromCssColorString('#22c55e')
                    }
                });
                
                const trajectoryEntity = viewer.entities.add({
                    polyline: {
                        positions: new Cesium.CallbackProperty(() => {
                            const activeDrone = viewer.entities.getById(`uav_${dId}`);
                            if (!activeDrone || !waypointEntity) return [];
                            const start = activeDrone.position.getValue(viewer.clock.currentTime);
                            const end = waypointEntity.position.getValue(viewer.clock.currentTime);
                            if (start && end) return [start, end];
                            return [];
                        }, false),
                        width: 2,
                        material: new Cesium.PolylineDashMaterialProperty({
                            color: Cesium.Color.fromCssColorString('#22c55e'),
                            dashLength: 20.0
                        }),
                        clampToGround: true // Conform trajectory to terrain
                    }
                });
                
                droneWaypoints[dId] = {
                    waypoint: waypointEntity,
                    trajectory: trajectoryEntity
                };
            } else {
                droneWaypoints[dId].waypoint.position = cartesian;
            }
            
            
            // Turn off setting mode
            isSettingWaypoint = false;
            if (inlineBtn) {
                inlineBtn.textContent = 'Set Waypoint';
                inlineBtn.style.background = '';
                inlineBtn.style.borderColor = '';
                inlineBtn.style.color = '';
            }
            return; // Exit here so we don't accidentally click a drone underneath the waypoint location
        }
    }

    // Normal Map Clicking (Select Drone)
    const pickedObjects = viewer.scene.drillPick(movement.position);
    for (let i = 0; i < pickedObjects.length; i++) {
        const pickedObject = pickedObjects[i];
        if (Cesium.defined(pickedObject) && pickedObject.id) {
            const pickId = typeof pickedObject.id === 'string' ? pickedObject.id : pickedObject.id.id;
            
            if (pickId && typeof pickId === 'string' && pickId.startsWith('uav_')) {
                if (mapClickTimer) clearTimeout(mapClickTimer);
                mapClickTimer = setTimeout(() => {
                    const droneEntity = viewer.entities.getById(pickId);
                    if (droneEntity) triggerDroneSelection(droneEntity, 'macro');
                }, 250);
                return; // successfully found and selected drone
            }
        }
    }
}, Cesium.ScreenSpaceEventType.LEFT_CLICK);

// Add double-click handler for 3rd person 3D picking
viewer.screenSpaceEventHandler.setInputAction(function onLeftDoubleClick(movement) {
    if (mapClickTimer) clearTimeout(mapClickTimer);
    
    // If we're tracking an entity and double click the background, don't do anything spiked
    const pickedObjectsDrone = viewer.scene.drillPick(movement.position);
    for (let i = 0; i < pickedObjectsDrone.length; i++) {
        const pickedObject = pickedObjectsDrone[i];
        if (Cesium.defined(pickedObject) && pickedObject.id) {
            const pickId = typeof pickedObject.id === 'string' ? pickedObject.id : pickedObject.id.id;
            if (pickId && typeof pickId === 'string' && pickId.startsWith('uav_')) {
                const droneEntity = viewer.entities.getById(pickId);
                if (droneEntity) triggerDroneSelection(droneEntity, 'thirdPerson');
                return;
            }
        }
    }
    
    // Prevent double clicking the map from firing a spike event if we are in tracking mode
    // (Because double-clicking the map while tracking a drone usually means the user missed the drone model)
    if (trackedDroneEntity) return;

    // Drill pick to pierce through any drone geometries that might be occluding the click
    const pickedObjects = viewer.scene.drillPick(movement.position);
    let hitTerrain = false;

    // We still try pickPosition to get exact lat/lon, but only act if we hit the globe, not a drone model
    let cartesian = viewer.scene.pickPosition(movement.position);
    if (!cartesian) {
        cartesian = viewer.camera.pickEllipsoid(movement.position, viewer.scene.globe.ellipsoid);
    }
    
    if (cartesian) {
        var cartographic = Cesium.Cartographic.fromCartesian(cartesian);
        var lon = Cesium.Math.toDegrees(cartographic.longitude);
        var lat = Cesium.Math.toDegrees(cartographic.latitude);
        
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ 
                action: "spike",
                lon: lon,
                lat: lat,
                radius: 0.5,
                magnitude: 20
            }));
            
            // Draw visual spike representation
            const entity = viewer.entities.add({
                position: cartesian,
                cylinder: {
                    length: 10000.0,
                    topRadius: 3000.0,
                    bottomRadius: 3000.0,
                    material: Cesium.Color.RED.withAlpha(0.3),
                    outline: true,
                    outlineColor: Cesium.Color.RED.withAlpha(0.6)
                }
            });
            viewer.scene.requestRender();
            
            // Remove the spike visual after 500ms
            setTimeout(() => {
                viewer.entities.remove(entity);
                viewer.scene.requestRender();
            }, 500);
        }
    }
}, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);

// Sidebar Resizing Logic
const resizer = document.getElementById('sidebarResizer');
const sidebar = document.getElementById('uiPanel');
const cameraControls = document.getElementById('cameraControls');

let isResizing = false;

resizer.addEventListener('mousedown', (e) => {
    isResizing = true;
    resizer.classList.add('active');
    document.body.style.cursor = 'col-resize';
    // Prevent text selection while dragging
    e.preventDefault();
});

document.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    
    // Calculate new width for the CONTENT area (mouse X position minus 48px of padding)
    let contentWidth = e.clientX - 48;
    
    // Apply min/max constraints (280px to 800px)
    if (contentWidth < 280) contentWidth = 280;
    if (contentWidth > 800) contentWidth = 800;
    
    // Set new sidebar width natively (sans padding)
    sidebar.style.width = `${contentWidth}px`;
    
    // Tell Cesium to completely recalculate the viewport bounding box size for the canvas right now
    // This allows the 3D view to scale seamlessly without skewing during the drag event
    viewer.resize();
});

document.addEventListener('mouseup', () => {
    if (isResizing) {
        isResizing = false;
        resizer.classList.remove('active');
        document.body.style.cursor = '';
    }
});

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
detailViewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
    url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}.png?api_key=74c21d3f-b418-4db6-9318-ffb876f1f071'
}));
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
            
            // Fire the WS payload identical to a global map click
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    action: "move_drone",
                    drone_id: detailActiveDroneId,
                    target_lon: lon,
                    target_lat: lat
                }));
            }
            
            // Sync the local global map droneWaypoints dictionary so the green cylinder immediately appears on the main screen
            if (!droneWaypoints[detailActiveDroneId]) {
                const waypointEntity = viewer.entities.add({
                    position: cartesian,
                    cylinder: {
                        length: 2000.0,
                        topRadius: 20.0,
                        bottomRadius: 20.0,
                        material: Cesium.Color.fromCssColorString('#22c55e').withAlpha(0.6),
                        outline: true,
                        outlineColor: Cesium.Color.fromCssColorString('#22c55e')
                    }
                });
                
                const trajectoryEntity = viewer.entities.add({
                    polyline: {
                        positions: new Cesium.CallbackProperty(() => {
                            const activeDrone = viewer.entities.getById(`uav_${detailActiveDroneId}`);
                            if (!activeDrone || !waypointEntity) return [];
                            const start = activeDrone.position.getValue(viewer.clock.currentTime);
                            const end = waypointEntity.position.getValue(viewer.clock.currentTime);
                            if (start && end) return [start, end];
                            return [];
                        }, false),
                        width: 2,
                        material: new Cesium.PolylineDashMaterialProperty({
                            color: Cesium.Color.fromCssColorString('#22c55e'),
                            dashLength: 20.0
                        }),
                        clampToGround: true
                    }
                });
                
                droneWaypoints[detailActiveDroneId] = {
                    waypoint: waypointEntity,
                    trajectory: trajectoryEntity
                };
            } else {
                droneWaypoints[detailActiveDroneId].waypoint.position = cartesian;
            }
            
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
