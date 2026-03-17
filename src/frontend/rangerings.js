import { state } from './state.js';

const droneRangeVisuals = {};

export function getDroneRangeVisuals() {
    return droneRangeVisuals;
}

export function toggleRangeRings(u, rangeBtn) {
    const viewer = state.viewer;

    if (droneRangeVisuals[u.id]) {
        droneRangeVisuals[u.id].forEach(entity => viewer.entities.remove(entity));
        delete droneRangeVisuals[u.id];
        rangeBtn.style.background = '';
        rangeBtn.style.borderColor = '';
        rangeBtn.style.color = '';
    } else {
        droneRangeVisuals[u.id] = [];
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
                    if (state.droneWaypoints[u.id] && state.droneWaypoints[u.id].waypoint) {
                        targetPos = state.droneWaypoints[u.id].waypoint.position.getValue(viewer.clock.currentTime);
                    }
                    if (!targetPos) {
                        const droneEntity = viewer.entities.getById(`uav_${u.id}`);
                        if (droneEntity) {
                            targetPos = droneEntity.position.getValue(viewer.clock.currentTime);
                        }
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
}

export function removeRangeRings(droneId) {
    const viewer = state.viewer;
    if (droneRangeVisuals[droneId]) {
        droneRangeVisuals[droneId].forEach(entity => viewer.entities.remove(entity));
        delete droneRangeVisuals[droneId];
    }
}
