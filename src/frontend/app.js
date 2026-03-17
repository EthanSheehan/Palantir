import { state } from './state.js';
import { initMap, initCompass, initMouseTracking, initMacroTracking, initOrUpdateZonesPrimitive } from './map.js';
import { connectWebSocket } from './websocket.js';
import { updateDrones, updateLockIndicators } from './drones.js';
import { updateDroneList } from './dronelist.js';
import { initMapClickHandlers } from './mapclicks.js';
import { updateTargets, getTargetEntities } from './targets.js';
import { updateEnemyList } from './enemies.js';
import { initSidebar } from './sidebar.js';
import { initAssistant } from './assistant.js';
import { initDetailMap } from './detailmap.js';
import { initStrikeBoard } from './strikeboard.js';
import { initTheater } from './theater.js';

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Cesium map
    const viewer = initMap();

    // 2. Initialize compass and tracking
    initCompass();
    initMouseTracking();
    initMacroTracking();

    // 3. Initialize UI modules
    initSidebar();
    initAssistant();
    initDetailMap();
    initStrikeBoard();
    initTheater();

    // 4. Flow lines buffer (managed here since it spans multiple ticks)
    const flowLines = [];

    // 5. Wire simulation state updates
    document.addEventListener('ws:state', (e) => {
        const simState = e.detail;
        viewer.scene.requestRender();

        initOrUpdateZonesPrimitive(simState.zones);

        flowLines.forEach(f => viewer.entities.remove(f));
        flowLines.length = 0;
        simState.flows.forEach(flow => {
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

        updateDrones(simState.uavs);
        updateDroneList(simState.uavs);

        document.getElementById('zoneCount').textContent = simState.zones.length;

        if (simState.targets) {
            updateTargets(simState.targets);
            updateEnemyList(simState.targets);
            updateLockIndicators(simState.uavs, getTargetEntities());
        }

        viewer.scene.requestRender();
    });

    // 6. Map click handlers and WebSocket
    initMapClickHandlers();
    connectWebSocket();
});
