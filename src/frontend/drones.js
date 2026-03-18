import { state } from './state.js';
import { removeRangeRings } from './rangerings.js';

const uavEntities = {};
const svgCache = {};

// Expose for map.js compass heading lookup
window._uavEntities = uavEntities;

export function getDronePin(statusColor) {
    if (svgCache[statusColor]) return svgCache[statusColor];
    const svg = `<svg fill="none" height="78" width="70" viewBox="-15 -15 70 78" xmlns="http://www.w3.org/2000/svg"><rect x="-15" y="-15" width="70" height="78" fill="rgba(255,255,255,0.01)"/><rect x="6" y="6" width="28" height="28" stroke="#3b82f6" stroke-width="2"/><circle cx="20" cy="20" r="4" fill="#3b82f6"/><rect x="6" y="40" width="28" height="6" fill="${statusColor}"/></svg>`;
    const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    svgCache[statusColor] = url;
    return url;
}

export function updateDrones(uavs) {
    const viewer = state.viewer;
    const currentUavIds = new Set();

    uavs.forEach(uav => {
        currentUavIds.add(uav.id);

        let colorStr = '#3b82f6';
        if (uav.mode === 'SEARCH') colorStr = '#22c55e';
        else if (uav.mode === 'FOLLOW') colorStr = '#a78bfa';
        else if (uav.mode === 'PAINT') colorStr = '#ef4444';
        else if (uav.mode === 'INTERCEPT') colorStr = '#ff6400';
        else if (uav.mode === 'REPOSITIONING') colorStr = '#eab308';
        else if (uav.mode === 'RTB') colorStr = '#64748b';
        const color = Cesium.Color.fromCssColorString(colorStr);
        const billboardImage = getDronePin(colorStr);

        const altitude = uav.altitude_m || 1000;
        const position = Cesium.Cartesian3.fromDegrees(uav.lon, uav.lat, altitude);
        const modelColor = Cesium.Color.fromCssColorString('#888888');

        if (!uavEntities[uav.id]) {
            _createDroneEntity(viewer, uav, position, color, billboardImage, modelColor, colorStr);
        } else {
            _updateExistingDrone(viewer, uavEntities[uav.id], uav, position, colorStr, color);
        }
    });

    Object.keys(uavEntities).forEach(id => {
        if (!currentUavIds.has(parseInt(id))) {
            const marker = uavEntities[id];
            if (marker._tether) viewer.entities.remove(marker._tether);
            viewer.entities.remove(marker);
            delete uavEntities[id];
            removeRangeRings(id);
        }
    });

    uavs.forEach(u => {
        if (u.mode !== 'repositioning' && state.droneWaypoints[u.id]) {
            viewer.entities.remove(state.droneWaypoints[u.id].waypoint);
            viewer.entities.remove(state.droneWaypoints[u.id].trajectory);
            delete state.droneWaypoints[u.id];
        }
    });

    let currentTrackedId = null;
    if (state.trackedDroneEntity) {
        currentTrackedId = parseInt(state.trackedDroneEntity.id.replace('uav_', ''));
    }

    Object.keys(state.droneWaypoints).forEach(idStr => {
        const id = parseInt(idStr);
        const wp = state.droneWaypoints[id];
        const isVisible = state.showAllWaypoints || (id === currentTrackedId);
        wp.waypoint.show = isVisible;
        wp.trajectory.show = isVisible;
    });

    document.getElementById('uavCount').textContent = uavs.length;
}

function _createDroneEntity(viewer, uav, position, color, billboardImage, modelColor, colorStr) {
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
            distanceDisplayCondition: new Cesium.DistanceDisplayCondition(800000.0, 50000000.0),
            disableDepthTestDistance: Number.POSITIVE_INFINITY
        },
        billboard: {
            image: billboardImage,
            scale: 0.8,
            verticalOrigin: Cesium.VerticalOrigin.CENTER,
            distanceDisplayCondition: new Cesium.DistanceDisplayCondition(2000.0, 800000.0),
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
    marker._lastLon = uav.lon;
    marker._lastLat = uav.lat;
    marker._lastMode = colorStr;
}

function _updateExistingDrone(viewer, marker, uav, position, colorStr, color) {
    let targetTime;
    const now = viewer.clock.currentTime;

    // Place sample slightly ahead of now so interpolation smooths the path
    targetTime = Cesium.JulianDate.addSeconds(now, 0.15, new Cesium.JulianDate());
    marker._lastTargetTime = targetTime;
    marker.position.addSample(targetTime, position);

    const dx = uav.lon - marker._lastLon;
    const dy = uav.lat - marker._lastLat;
    const movementDist = Math.abs(dx) + Math.abs(dy);

    if (movementDist > 0.0005) {
        const latRad = Cesium.Math.toRadians(uav.lat);
        const dxScaled = dx * Math.cos(latRad);
        const mathAngle = Math.atan2(dy, dxScaled);
        let heading = (Math.PI / 2) - mathAngle + Math.PI;

        if (!marker._lastHeading) marker._lastHeading = heading;
        let hdiff = heading - marker._lastHeading;
        while (hdiff > Math.PI) hdiff -= Math.PI * 2;
        while (hdiff < -Math.PI) hdiff += Math.PI * 2;
        heading = marker._lastHeading + (hdiff * 0.6);
        marker._lastHeading = heading;

        const hpr = new Cesium.HeadingPitchRoll(heading, 0.0, 0.0);
        const quat = Cesium.Transforms.headingPitchRollQuaternion(position, hpr);
        marker.orientation.addSample(targetTime, quat);

        marker._lastLon = uav.lon;
        marker._lastLat = uav.lat;
    }

    if (uav.heading_deg !== undefined && movementDist <= 0.002) {
        const heading = Cesium.Math.toRadians(uav.heading_deg) + Math.PI;
        marker._lastHeading = heading;
        const hpr = new Cesium.HeadingPitchRoll(heading, 0.0, 0.0);
        const quat = Cesium.Transforms.headingPitchRollQuaternion(position, hpr);
        marker.orientation.addSample(targetTime, quat);
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

export function triggerDroneSelection(entity, viewMode = 'macro') {
    const viewer = state.viewer;
    document.getElementById('cameraControls').style.display = 'flex';
    state.trackedDroneEntity = entity;
    viewer.trackedEntity = undefined;

    if (viewer.camera.transform && !viewer.camera.transform.equals(Cesium.Matrix4.IDENTITY)) {
        viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
    }

    state.macroTrackedId = null;
    state.isMacroTrackingReady = false;
    state.lastDronePosition = null;

    state.selectedDroneId = entity.id.replace('uav_', '');
    document.dispatchEvent(new CustomEvent('drone:selected'));

    if (viewMode === 'thirdPerson') {
        entity.viewFrom = undefined;
        viewer.flyTo(entity, {
            duration: 1.5,
            offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-15), 150)
        }).then(function(result) {
            if (result && state.trackedDroneEntity === entity) {
                entity.viewFrom = new Cesium.Cartesian3(0, -100, 30);
                viewer.trackedEntity = entity;
            }
        });
    } else {
        entity.viewFrom = undefined;
        const currentHeading = viewer.camera.heading;
        const currentPitch = Math.min(viewer.camera.pitch, Cesium.Math.toRadians(-20));

        viewer.flyTo(entity, {
            duration: 1.5,
            offset: new Cesium.HeadingPitchRange(currentHeading, currentPitch, 10000)
        }).then(function(result) {
            if (result && state.trackedDroneEntity === entity) {
                state.macroTrackedId = parseInt(entity.id.replace('uav_', ''));
                state.isMacroTrackingReady = true;
            }
        });
    }
}

export function updateLockIndicators(uavs, targetEntities) {
    const viewer = state.viewer;
    uavs.forEach(uav => {
        const marker = uavEntities[uav.id];
        if (!marker) return;

        if (uav.mode === 'PAINT' && uav.tracked_target_id) {
            const targetEntity = targetEntities[uav.tracked_target_id];
            if (targetEntity && !targetEntity._lockRing) {
                targetEntity._lockRing = viewer.entities.add({
                    position: targetEntity.position,
                    ellipse: {
                        semiMajorAxis: 500,
                        semiMinorAxis: 500,
                        height: 50,
                        fill: false,
                        outline: true,
                        outlineColor: Cesium.Color.RED.withAlpha(0.8),
                        outlineWidth: 3
                    }
                });
            }
        } else if (uav.mode !== 'PAINT' && uav.tracked_target_id) {
            const targetEntity = targetEntities[uav.tracked_target_id];
            if (targetEntity && targetEntity._lockRing) {
                viewer.entities.remove(targetEntity._lockRing);
                targetEntity._lockRing = null;
            }
        }
    });
}

export function placeWaypointFromDetail(droneId, cartesian) {
    _placeWaypoint(state.viewer, droneId, cartesian);
}

function _placeWaypoint(viewer, dId, cartesian) {
    if (!state.droneWaypoints[dId]) {
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
                clampToGround: true
            }
        });

        state.droneWaypoints[dId] = { waypoint: waypointEntity, trajectory: trajectoryEntity };
    } else {
        state.droneWaypoints[dId].waypoint.position = cartesian;
    }
}
