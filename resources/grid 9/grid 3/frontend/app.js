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

// Configure Grid-Sentinel-style Cinematic Lighting & Dark Mode
viewer.scene.globe.baseColor = Cesium.Color.BLACK;
viewer.scene.backgroundColor = Cesium.Color.BLACK;
viewer.scene.globe.enableLighting = true; 

// Freeze time at noon UTC during the summer solstice so Europe is fully illuminated
viewer.clock.currentTime = Cesium.JulianDate.fromIso8601("2023-06-21T10:00:00Z");
viewer.clock.shouldAnimate = false;

viewer.scene.sun.show = false;
viewer.scene.moon.show = false;
viewer.scene.skyAtmosphere.hueShift = -0.5; 
viewer.scene.skyAtmosphere.brightnessShift = -0.8;
viewer.scene.fog.enabled = true;
viewer.scene.fog.density = 0.0001;



viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(24.9668, 43.0, 500000.0), 
    orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-45.0),
        roll: 0.0
    },
    duration: 0 
});

// 2. Data Structures for ultra-fast rendering
let zonesPrimitive = null;
const zoneAttributesCache = {}; // Cache to prevent lookup overhead
const flowLines = []; 
const uavEntities = {};

const svgCache = {};
function getDronePin(statusColor) {
    if (svgCache[statusColor]) return svgCache[statusColor];
    const svg = `<svg fill="none" height="48" width="40" xmlns="http://www.w3.org/2000/svg"><rect x="6" y="6" width="28" height="28" stroke="#3b82f6" stroke-width="2"/><circle cx="20" cy="20" r="4" fill="#3b82f6"/><rect x="6" y="40" width="28" height="6" fill="${statusColor}"/></svg>`;
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
        const instances = [];
        
        stateZones.forEach(z => {
            const zoneId = `z_${z.x_idx}_${z.y_idx}`;
            const width = z.width || 0.192;
            const height = z.height || 0.094;
            const halfW = width / 2;
            const halfH = height / 2;
            
            const hierarchy = new Cesium.PolygonHierarchy(Cesium.Cartesian3.fromDegreesArray([
                z.lon - halfW, z.lat - halfH,
                z.lon + halfW, z.lat - halfH,
                z.lon + halfW, z.lat + halfH,
                z.lon - halfW, z.lat + halfH
            ]));
            
            const color = getImbalanceColor(z.imbalance);
            
            instances.push(new Cesium.GeometryInstance({
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
        });
        
        zonesPrimitive = viewer.scene.primitives.add(new Cesium.GroundPrimitive({
            geometryInstances: instances,
            appearance: new Cesium.PerInstanceColorAppearance({
                flat: true,
                translucent: true
            }),
            asynchronous: false // load immediately 
        }));
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
                    color: Cesium.Color.CYAN // Grid-Sentinel style flows
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
            const marker = viewer.entities.add({
                id: `uav_${uav.id}`,
                name: `UAV-${uav.id}`,
                position: position,
                point: {
                    pixelSize: 6,
                    color: color,
                    outlineColor: Cesium.Color.BLACK,
                    outlineWidth: 1,
                    heightReference: Cesium.HeightReference.NONE,
                    // The simple dot appears only from high orbit (200km+)
                    distanceDisplayCondition: new Cesium.DistanceDisplayCondition(200000.0, 50000000.0)
                },
                billboard: {
                    image: billboardImage,
                    scale: 0.8,
                    verticalOrigin: Cesium.VerticalOrigin.CENTER,
                    // The SVG UI appears between the 3D Tracking view and the Extreme Orbit view
                    distanceDisplayCondition: new Cesium.DistanceDisplayCondition(2000.0, 200000.0)
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
                },
                polyline: {
                    positions: [
                        Cesium.Cartesian3.fromDegrees(uav.lon, uav.lat, 0),
                        position
                    ],
                    width: 1,
                    material: color.withAlpha(0.3)
                },
                // The camera offset when tracking this entity (behind and slightly above)
                viewFrom: new Cesium.Cartesian3(-300.0, 0.0, 150.0)
            });
            uavEntities[uav.id] = marker;
            // Store previous position to calculate heading
            marker._lastLon = uav.lon;
            marker._lastLat = uav.lat;
            marker._lastMode = colorStr;
        } else {
            const marker = uavEntities[uav.id];
            marker.position = position;
            marker.polyline.positions = [
                Cesium.Cartesian3.fromDegrees(uav.lon, uav.lat, 0),
                position
            ];
            
            // Calculate orientation dynamically from movement vector
            const dx = uav.lon - marker._lastLon;
            const dy = uav.lat - marker._lastLat;
            
            // INCREASE THRESHOLD to 0.002 to prevent 10Hz jitter / stuttering
            const movementDist = Math.abs(dx) + Math.abs(dy);
            if (movementDist > 0.002) {
                const mathAngle = Math.atan2(dy, dx); 
                
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
                marker.orientation = Cesium.Transforms.headingPitchRollQuaternion(position, hpr);
                
                marker._lastLon = uav.lon;
                marker._lastLat = uav.lat;
            }
            
            if (marker._lastMode !== colorStr) {
                marker.billboard.image = getDronePin(colorStr);
                marker.point.color = color;
                marker.polyline.material = color.withAlpha(0.3);
                marker._lastMode = colorStr;
            }
        }
    });
    
    document.getElementById('uavCount').textContent = state.uavs.length;
    document.getElementById('zoneCount').textContent = state.zones.length;
    
    Object.keys(uavEntities).forEach(id => {
        if (!currentUavIds.has(parseInt(id))) {
            viewer.entities.remove(uavEntities[id]);
            delete uavEntities[id];
        }
    });

    viewer.scene.requestRender();
}

// 5. WebSocket Logic
let ws = null;
const connStatus = document.getElementById('connStatus');

function connectWebSocket() {
    const wsUrl = `ws://localhost:8005/ws/stream`;
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
            updateSimulation(payload.data);
        }
    };
}
connectWebSocket();

// 6. UI Interaction
document.getElementById('resetQueueBtn').addEventListener('click', () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: "reset" }));
    }
});

// Third-Person UAV Tracking logic
viewer.screenSpaceEventHandler.setInputAction(function onLeftClick(movement) {
    const pickedObject = viewer.scene.pick(movement.position);
    if (Cesium.defined(pickedObject) && pickedObject.id && pickedObject.id.name && pickedObject.id.name.startsWith('UAV')) {
        const entity = pickedObject.id;
        document.getElementById('returnGlobalBtn').style.display = 'inline-block';
        
        // Temporarily disable tracking while we smoothly fly into position
        viewer.trackedEntity = undefined;
        
        // Cesium will automatically use the entity's `viewFrom` offset for this flight
        viewer.flyTo(entity, {
            duration: 1.5 
        }).then(function() {
            // Once the flight completes, lock the camera to the moving entity
            viewer.trackedEntity = entity;
        });
    }
}, Cesium.ScreenSpaceEventType.LEFT_CLICK);

document.getElementById('returnGlobalBtn').addEventListener('click', () => {
    viewer.trackedEntity = undefined;
    document.getElementById('returnGlobalBtn').style.display = 'none';
    
    // Smoothly fly back out to the macro scale
    viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(24.9668, 43.0, 500000.0), 
        orientation: {
            heading: Cesium.Math.toRadians(0),
            pitch: Cesium.Math.toRadians(-45.0),
            roll: 0.0
        },
        duration: 2.0 
    });
});

viewer.screenSpaceEventHandler.setInputAction(function onLeftDoubleClick(movement) {
    // If we're tracking an entity, don't allow double-click spikes, as it messes up the camera
    if (viewer.trackedEntity) return;

    // Drill pick to pierce through any drone geometries that might be occluding the click
    const pickedObjects = viewer.scene.drillPick(movement.position);
    let hitTerrain = false;

    // We still try pickPosition to get exact lat/lon, but only act if we hit the globe, not a drone model
    var cartesian = viewer.scene.pickPosition(movement.position);
    
    if (!cartesian) {
        // Fallback if not hitting geometry directly
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
                lat: lat
            }));
            
            const entity = viewer.entities.add({
                position: cartesian,
                cylinder: {
                    length: 5000.0,
                    topRadius: 1000.0,
                    bottomRadius: 1000.0,
                    material: Cesium.Color.RED.withAlpha(0.5),
                    outline: true,
                    outlineColor: Cesium.Color.RED
                }
            });
            viewer.scene.requestRender();
            
            setTimeout(() => {
                viewer.entities.remove(entity);
                viewer.scene.requestRender();
            }, 500);
        }
    }
}, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);

document.getElementById('addSpikeBtn').addEventListener('click', () => {
    const lon = 24.9668 + (Math.random() - 0.5) * 5.0; 
    const lat = 45.9432 + (Math.random() - 0.5) * 3.0; 
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            action: "spike",
            lon: lon,
            lat: lat
        }));
    }
});
