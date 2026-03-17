import { state } from './state.js';
import { sendMessage } from './websocket.js';
import { getDronePin, placeWaypointFromDetail } from './drones.js';

const STADIA_URL = 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}.png?api_key=74c21d3f-b418-4db6-9318-ffb876f1f071';
const CONSTRAINT_RADIUS_METERS = 150000.0;

let detailViewer = null;
let detailActiveDroneId = null;
let rangeConstraintEntity = null;
let detailDroneMarker = null;

export function initDetailMap() {
    detailViewer = new Cesium.Viewer('detailMapContainer', {
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

    detailViewer.imageryLayers.removeAll();
    detailViewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({ url: STADIA_URL }));

    detailViewer.scene.globe.baseColor = Cesium.Color.BLACK;
    detailViewer.scene.backgroundColor = Cesium.Color.BLACK;
    detailViewer.scene.globe.enableLighting = true;
    detailViewer.scene.globe.depthTestAgainstTerrain = true;
    detailViewer.scene.skyAtmosphere.hueShift = -0.5;
    detailViewer.scene.skyAtmosphere.brightnessShift = -0.8;
    detailViewer.scene.fog.enabled = true;
    detailViewer.scene.fog.density = 0.0001;

    detailViewer.scene.screenSpaceCameraController.enableRotate = false;
    detailViewer.scene.screenSpaceCameraController.enableTranslate = false;
    detailViewer.scene.screenSpaceCameraController.enableZoom = false;
    detailViewer.scene.screenSpaceCameraController.enableTilt = false;
    detailViewer.scene.screenSpaceCameraController.enableLook = false;

    detailViewer.clock.currentTime = Cesium.JulianDate.fromIso8601('2023-06-21T10:00:00Z');
    detailViewer.clock.shouldAnimate = false;

    rangeConstraintEntity = detailViewer.entities.add({
        name: 'Range Constraint',
        position: Cesium.Cartesian3.fromDegrees(0, 0),
        ellipse: {
            semiMajorAxis: CONSTRAINT_RADIUS_METERS,
            semiMinorAxis: CONSTRAINT_RADIUS_METERS,
            material: Cesium.Color.RED.withAlpha(0.15),
            outline: true,
            outlineColor: Cesium.Color.RED.withAlpha(0.6),
            outlineWidth: 2,
            height: 0
        }
    });

    detailDroneMarker = detailViewer.entities.add({
        name: 'Detail Target Drone',
        position: Cesium.Cartesian3.fromDegrees(0, 0),
        billboard: {
            image: getDronePin('#facc15'),
            scale: 0.8,
            verticalOrigin: Cesium.VerticalOrigin.CENTER
        }
    });

    const detailModal = document.getElementById('detailMapModal');
    document.getElementById('closeDetailMapBtn').addEventListener('click', () => {
        detailModal.style.display = 'none';
        detailActiveDroneId = null;
    });

    detailViewer.screenSpaceEventHandler.setInputAction(function onDetailMapClick(movement) {
        if (!detailActiveDroneId) return;

        let cartesian = detailViewer.scene.pickPosition(movement.position);
        if (!cartesian) {
            cartesian = detailViewer.camera.pickEllipsoid(movement.position, detailViewer.scene.globe.ellipsoid);
        }

        if (cartesian) {
            const centerPos = rangeConstraintEntity.position.getValue(Cesium.JulianDate.now());
            const distanceMeters = Cesium.Cartesian3.distance(centerPos, cartesian);

            if (distanceMeters <= CONSTRAINT_RADIUS_METERS) {
                const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
                const lon = Cesium.Math.toDegrees(cartographic.longitude);
                const lat = Cesium.Math.toDegrees(cartographic.latitude);

                sendMessage({ action: 'move_drone', drone_id: detailActiveDroneId, target_lon: lon, target_lat: lat });
                placeWaypointFromDetail(detailActiveDroneId, cartesian);

                detailModal.style.display = 'none';
                detailActiveDroneId = null;
            } else {
                const origMat = rangeConstraintEntity.ellipse.material;
                rangeConstraintEntity.ellipse.material = Cesium.Color.fromCssColorString('#fbbf24').withAlpha(0.6);
                setTimeout(() => { rangeConstraintEntity.ellipse.material = origMat; }, 150);
            }
        }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    document.addEventListener('drone:openDetailMap', (e) => {
        openDetailMapModal(e.detail);
    });
}

function openDetailMapModal(droneData) {
    if (!droneData) return;
    const detailModal = document.getElementById('detailMapModal');
    detailModal.style.display = 'flex';
    detailActiveDroneId = droneData.id;
    detailViewer.resize();
    const dronePos = Cesium.Cartesian3.fromDegrees(droneData.lon, droneData.lat);
    rangeConstraintEntity.position = dronePos;
    detailDroneMarker.position = dronePos;
    detailViewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(droneData.lon, droneData.lat, 400000.0),
        orientation: { heading: 0.0, pitch: Cesium.Math.toRadians(-90.0), roll: 0.0 }
    });
}

// Keep global compat for any legacy references
window.openDetailMapModal = openDetailMapModal;
