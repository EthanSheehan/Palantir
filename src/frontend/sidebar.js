import { state } from './state.js';
import { sendMessage } from './websocket.js';

export function initSidebar() {
    initTabs();
    initResizer();
    initGridButtons();
    initWaypointToggle();
    initResetButton();
    initCameraControls();
    initActionButtons();
    initOverscrollBounce();
}

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(pane => pane.classList.remove('active-tab'));
            button.classList.add('active');
            document.getElementById(button.getAttribute('data-tab')).classList.add('active-tab');
        });
    });
}

function initResizer() {
    const sidebarResizer = document.getElementById('sidebarResizer');
    const sidePanel = document.getElementById('uiPanel');
    let isResizing = false;

    sidebarResizer.addEventListener('mousedown', (e) => {
        isResizing = true;
        sidebarResizer.classList.add('active');
        document.body.style.cursor = 'col-resize';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        let contentWidth = e.clientX - 48;
        if (contentWidth < 280) contentWidth = 280;
        if (contentWidth > 800) contentWidth = 800;
        sidePanel.style.width = `${contentWidth}px`;
        state.viewer.resize();
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            sidebarResizer.classList.remove('active');
            document.body.style.cursor = '';
        }
    });
}

function initGridButtons() {
    document.getElementById('toggleGridBtn').addEventListener('click', (e) => {
        state.gridVisState = (state.gridVisState + 1) % 3;

        if (state.zonesPrimitive) state.zonesPrimitive.show = (state.gridVisState === 2);
        if (state.zoneBordersPrimitive) state.zoneBordersPrimitive.show = (state.gridVisState === 1 || state.gridVisState === 2);

        const btn = e.target;
        if (state.gridVisState === 2) {
            btn.textContent = 'Grid Visibility: ON';
            btn.style.borderColor = 'rgba(56, 189, 248, 0.5)';
            btn.style.color = '#38bdf8';
        } else if (state.gridVisState === 1) {
            btn.textContent = 'Grid Visibility: SQUARES ONLY';
            btn.style.borderColor = 'rgba(167, 139, 250, 0.5)';
            btn.style.color = '#a78bfa';
        } else {
            btn.textContent = 'Grid Visibility: OFF';
            btn.style.borderColor = 'rgba(148, 163, 184, 0.2)';
            btn.style.color = '#e2e8f0';
        }
        state.viewer.scene.requestRender();
    });
}

function initWaypointToggle() {
    document.getElementById('toggleWaypointsBtn').addEventListener('click', (e) => {
        state.showAllWaypoints = !state.showAllWaypoints;
        const btn = e.target;
        btn.textContent = state.showAllWaypoints ? 'All Waypoints: ON' : 'All Waypoints: OFF';
        btn.style.borderColor = state.showAllWaypoints ? 'rgba(56, 189, 248, 0.5)' : 'rgba(148, 163, 184, 0.2)';
        btn.style.color = state.showAllWaypoints ? '#38bdf8' : '#e2e8f0';

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
        state.viewer.scene.requestRender();
    });
}

function initResetButton() {
    document.getElementById('resetQueueBtn').addEventListener('click', () => {
        sendMessage({ action: 'reset' });
    });
}

function initCameraControls() {
    document.getElementById('returnGlobalBtn').addEventListener('click', () => {
        _decoupleCamera();
        const b = state.theaterBounds;
        const lon = b ? (b.min_lon + b.max_lon) / 2 : 24.9668;
        const lat = b ? (b.min_lat + b.max_lat) / 2 : 41.2;
        const alt = b ? Math.max(b.max_lon - b.min_lon, b.max_lat - b.min_lat) * 80000 : 500000;
        state.viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(lon, lat, alt),
            orientation: { heading: Cesium.Math.toRadians(0), pitch: Cesium.Math.toRadians(-45.0), roll: 0.0 },
            duration: 1.5
        });
    });

    document.getElementById('decoupleCameraBtn').addEventListener('click', () => {
        _decoupleCamera();
    });
}

function _decoupleCamera() {
    if (state.trackedDroneEntity) state.trackedDroneEntity.viewFrom = undefined;
    state.trackedDroneEntity = null;
    state.viewer.trackedEntity = undefined;
    state.macroTrackedId = null;
    state.isMacroTrackingReady = false;
    state.isSettingWaypoint = false;
    state.selectedDroneId = null;

    state.viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
    document.getElementById('cameraControls').style.display = 'none';
    document.dispatchEvent(new CustomEvent('drone:selected'));
}

function initActionButtons() {
    // Action buttons now live in drone card (dronelist.js), no standalone action bar needed
}

function initOverscrollBounce() {
    const tabDrones = document.getElementById('tab-drones');
    const dlContainer = document.getElementById('droneListContainer');
    let isBouncing = false;
    let hasBouncedTop = false;
    let hasBouncedBottom = false;

    tabDrones.addEventListener('wheel', (e) => {
        if (isBouncing) return;
        const isAtTop = tabDrones.scrollTop <= 0;
        const isAtBottom = tabDrones.scrollTop + tabDrones.clientHeight >= tabDrones.scrollHeight - 1;
        if (!isAtTop) hasBouncedTop = false;
        if (!isAtBottom) hasBouncedBottom = false;

        if (e.deltaY < 0 && isAtTop && !hasBouncedTop) {
            isBouncing = true;
            hasBouncedTop = true;
            dlContainer.classList.add('scroll-bounce-top');
            setTimeout(() => { dlContainer.classList.remove('scroll-bounce-top'); isBouncing = false; }, 400);
        } else if (e.deltaY > 0 && isAtBottom && !hasBouncedBottom) {
            isBouncing = true;
            hasBouncedBottom = true;
            dlContainer.classList.add('scroll-bounce-bottom');
            setTimeout(() => { dlContainer.classList.remove('scroll-bounce-bottom'); isBouncing = false; }, 400);
        }
    }, { passive: true });
}
