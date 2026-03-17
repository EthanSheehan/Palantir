import { state } from './state.js';

const CESIUM_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJmNTg1MmY5OC05NWQ0LTQ0MDEtYTFmMy0yMWI0YzEwYzRiNjciLCJpZCI6NDAzNzE1LCJpYXQiOjE3NzM1MTczMjV9.pfteEFlBPi85hAolMWsVyZkuRTwSeg_-bF5dlTMcWHo';
const STADIA_URL = 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}.png?api_key=74c21d3f-b418-4db6-9318-ffb876f1f071';

const zoneAttributesCache = {};

export function initMap() {
    Cesium.Ion.defaultAccessToken = CESIUM_TOKEN;

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

    viewer.imageryLayers.removeAll();
    viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({ url: STADIA_URL }));

    viewer.scene.globe.baseColor = Cesium.Color.BLACK;
    viewer.scene.backgroundColor = Cesium.Color.BLACK;
    viewer.scene.globe.enableLighting = true;
    viewer.scene.globe.depthTestAgainstTerrain = true;

    viewer.clock.currentTime = Cesium.JulianDate.fromIso8601('2023-06-21T10:00:00Z');
    viewer.clock.shouldAnimate = true;
    viewer.clock.multiplier = 1.0;

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

    state.viewer = viewer;
    return viewer;
}

export function getImbalanceColor(imbalance) {
    const imb = Math.max(-20, Math.min(20, imbalance));
    if (imb < 0) {
        const intensity = Math.abs(imb) / 20.0;
        return Cesium.Color.fromCssColorString('rgba(239, 68, 68, 1.0)').withAlpha(0.2 + (intensity * 0.4));
    } else if (imb > 0) {
        const intensity = imb / 20.0;
        return Cesium.Color.fromCssColorString('rgba(59, 130, 246, 1.0)').withAlpha(0.2 + (intensity * 0.4));
    }
    return new Cesium.Color(0, 0, 0, 0.0);
}

export function initOrUpdateZonesPrimitive(stateZones) {
    const viewer = state.viewer;

    if (!state.zonesPrimitive) {
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

        state.zonesPrimitive = viewer.scene.primitives.add(new Cesium.GroundPrimitive({
            geometryInstances: fillInstances,
            appearance: new Cesium.PerInstanceColorAppearance({ flat: true, translucent: true }),
            asynchronous: false
        }));

        state.zoneBordersPrimitive = viewer.scene.primitives.add(new Cesium.GroundPolylinePrimitive({
            geometryInstances: borderInstances,
            appearance: new Cesium.PolylineMaterialAppearance({
                material: Cesium.Material.fromType('Color', {
                    color: new Cesium.Color(1.0, 1.0, 1.0, 0.15)
                })
            }),
            asynchronous: true
        }));

        state.zonesPrimitive.show = (state.gridVisState === 2);
        state.zoneBordersPrimitive.show = (state.gridVisState === 1 || state.gridVisState === 2);
    } else {
        stateZones.forEach(z => {
            const zoneId = `z_${z.x_idx}_${z.y_idx}`;
            const color = getImbalanceColor(z.imbalance);

            let attrs = zoneAttributesCache[zoneId];
            if (!attrs) {
                attrs = state.zonesPrimitive.getGeometryInstanceAttributes(zoneId);
                zoneAttributesCache[zoneId] = attrs;
                if (attrs) attrs._lastColor = null;
            }

            if (attrs) {
                const newColorStr = `${color.red},${color.green},${color.blue},${color.alpha}`;
                if (attrs._lastColor !== newColorStr) {
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

export function initCompass() {
    const viewer = state.viewer;

    viewer.entities.add({
        id: 'compass',
        polyline: {
            positions: new Cesium.CallbackProperty(() => {
                const center = getCompassCenter();
                if (!center) return [];

                const transform = Cesium.Transforms.eastNorthUpToFixedFrame(center);
                let fwd = new Cesium.Cartesian3(0.0, 2000.0, 0.0);

                if (state.trackedDroneEntity) {
                    let heading = 0.0;
                    const markerId = state.trackedDroneEntity.id.replace('uav_', '');
                    const uavEntities = window._uavEntities || {};
                    if (uavEntities[markerId] && uavEntities[markerId]._lastHeading !== undefined) {
                        heading = uavEntities[markerId]._lastHeading;
                        heading -= Math.PI;
                    }
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

    viewer.entities.add({
        id: 'compassRing',
        polyline: {
            positions: new Cesium.CallbackProperty(() => {
                const center = getCompassCenter();
                if (!center) return [];

                const radius = 1500.0;
                const segments = 64;
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
}

let currentMousePosition = null;

export function getCompassCenter() {
    if (state.trackedDroneEntity) {
        const dronePos = state.trackedDroneEntity.position.getValue(state.viewer.clock.currentTime);
        if (dronePos) {
            let carto = Cesium.Cartographic.fromCartesian(dronePos);
            carto.height = 0;
            return Cesium.Cartographic.toCartesian(carto);
        }
    }
    return currentMousePosition;
}

export function initMouseTracking() {
    state.viewer.screenSpaceEventHandler.setInputAction(function onMouseMove(movement) {
        if (!state.trackedDroneEntity) {
            let cartesian = state.viewer.scene.pickPosition(movement.endPosition);
            if (!cartesian) {
                cartesian = state.viewer.camera.pickEllipsoid(movement.endPosition, state.viewer.scene.globe.ellipsoid);
            }
            if (cartesian) {
                currentMousePosition = cartesian;
                state.viewer.scene.requestRender();
            }
        }
    }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);
}

export function initMacroTracking() {
    state.viewer.scene.preUpdate.addEventListener(function(scene, time) {
        if (state.macroTrackedId && state.isMacroTrackingReady && !state.viewer.trackedEntity) {
            const uavEntities = window._uavEntities || {};
            const drone = uavEntities[state.macroTrackedId];
            if (drone && drone.position) {
                const pos = drone.position.getValue(time);
                if (pos) {
                    if (state.lastDronePosition) {
                        state.viewer.camera.position.x += pos.x - state.lastDronePosition.x;
                        state.viewer.camera.position.y += pos.y - state.lastDronePosition.y;
                        state.viewer.camera.position.z += pos.z - state.lastDronePosition.z;
                    }
                    state.lastDronePosition = pos;
                } else {
                    state.lastDronePosition = null;
                }
            }
        } else {
            state.lastDronePosition = null;
        }
    });
}
