import { state } from './state.js';
import { sendMessage } from './websocket.js';
import { triggerDroneSelection, placeWaypointFromDetail } from './drones.js';

export function initMapClickHandlers() {
    const viewer = state.viewer;
    let mapClickTimer = null;

    viewer.screenSpaceEventHandler.setInputAction(function onLeftClick(movement) {
        if (state.isSettingWaypoint && state.trackedDroneEntity) {
            let cartesian = viewer.scene.pickPosition(movement.position);
            if (!cartesian) {
                cartesian = viewer.camera.pickEllipsoid(movement.position, viewer.scene.globe.ellipsoid);
            }

            if (cartesian) {
                const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
                const lon = Cesium.Math.toDegrees(cartographic.longitude);
                const lat = Cesium.Math.toDegrees(cartographic.latitude);

                const markerId = state.trackedDroneEntity.id.replace('uav_', '');
                const dId = parseInt(markerId);
                const inlineBtn = document.getElementById(`inlineSetWaypointBtn_${dId}`);

                sendMessage({ action: 'move_drone', drone_id: dId, target_lon: lon, target_lat: lat });
                placeWaypointFromDetail(dId, cartesian);

                state.isSettingWaypoint = false;
                if (inlineBtn) {
                    inlineBtn.textContent = 'Set Waypoint';
                    inlineBtn.style.background = '';
                    inlineBtn.style.borderColor = '';
                    inlineBtn.style.color = '';
                }
                return;
            }
        }

        const pickedObjects = viewer.scene.drillPick(movement.position);
        for (let i = 0; i < pickedObjects.length; i++) {
            const pickedObject = pickedObjects[i];
            if (Cesium.defined(pickedObject) && pickedObject.id) {
                const pickId = typeof pickedObject.id === 'string' ? pickedObject.id : pickedObject.id.id;

                if (pickId && typeof pickId === 'string') {
                    if (pickId.startsWith('uav_')) {
                        if (mapClickTimer) clearTimeout(mapClickTimer);
                        mapClickTimer = setTimeout(() => {
                            const droneEntity = viewer.entities.getById(pickId);
                            if (droneEntity) triggerDroneSelection(droneEntity, 'macro');
                        }, 250);
                        return;
                    }

                    if (pickId.startsWith('target_')) {
                        const tId = parseInt(pickId.replace('target_', ''));
                        state.selectedTargetId = tId;
                        document.dispatchEvent(new CustomEvent('target:selected', { detail: { id: tId } }));
                        return;
                    }
                }
            }
        }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    viewer.screenSpaceEventHandler.setInputAction(function onLeftDoubleClick(movement) {
        if (mapClickTimer) clearTimeout(mapClickTimer);

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

        if (state.trackedDroneEntity) return;

        let cartesian = viewer.scene.pickPosition(movement.position);
        if (!cartesian) {
            cartesian = viewer.camera.pickEllipsoid(movement.position, viewer.scene.globe.ellipsoid);
        }

        if (cartesian) {
            const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
            const lon = Cesium.Math.toDegrees(cartographic.longitude);
            const lat = Cesium.Math.toDegrees(cartographic.latitude);

            sendMessage({ action: 'spike', lon: lon, lat: lat, radius: 0.5, magnitude: 20 });

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
            setTimeout(() => {
                viewer.entities.remove(entity);
                viewer.scene.requestRender();
            }, 500);
        }
    }, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
}
