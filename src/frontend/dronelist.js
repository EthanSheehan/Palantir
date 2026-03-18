import { state } from './state.js';
import { toggleRangeRings } from './rangerings.js';
import { triggerDroneSelection } from './drones.js';
import { sendMessage } from './websocket.js';

export function updateDroneList(uavs) {
    const viewer = state.viewer;
    const listContainer = document.getElementById('droneListContainer');

    let currentTrackedId = null;
    if (state.trackedDroneEntity) {
        currentTrackedId = parseInt(state.trackedDroneEntity.id.replace('uav_', ''));
    }

    if (uavs.length === 0) {
        listContainer.textContent = '';
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'empty-state';
        emptyDiv.textContent = 'No UAVs Active.';
        listContainer.appendChild(emptyDiv);
        return;
    }

    const emptyState = listContainer.querySelector('.empty-state');
    if (emptyState) listContainer.removeChild(emptyState);

    const activeIds = new Set(uavs.map(u => u.id));

    Array.from(listContainer.children).forEach(card => {
        const id = parseInt(card.dataset.id);
        if (!activeIds.has(id)) listContainer.removeChild(card);
    });

    uavs.forEach(u => {
        let card = listContainer.querySelector(`[data-id="${u.id}"]`);
        if (!card) {
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
                e.preventDefault();
                if (card.clickTimer) clearTimeout(card.clickTimer);
                const entity = viewer.entities.getById(`uav_${u.id}`);
                if (entity) triggerDroneSelection(entity, 'thirdPerson');
            });

            listContainer.appendChild(card);
        }

        const isTracked = (u.id === currentTrackedId);

        if (card.dataset.mode !== u.mode || card.dataset.tracked !== String(isTracked) || card.dataset.targetId !== String(u.tracked_target_id || '')) {
            _renderDroneCard(card, u, isTracked);
        }
    });
}

const MODE_STYLES = {
    IDLE:          { color: '#3b82f6', label: 'IDLE' },
    SEARCH:        { color: '#22c55e', label: 'SEARCH' },
    FOLLOW:        { color: '#a78bfa', label: 'FOLLOW' },
    PAINT:         { color: '#ef4444', label: 'PAINT' },
    INTERCEPT:     { color: '#ff6400', label: 'INTERCEPT' },
    REPOSITIONING: { color: '#eab308', label: 'TRANSIT' },
    RTB:           { color: '#64748b', label: 'RTB' },
};

function _renderDroneCard(card, u, isTracked) {
    const altKm = ((u.altitude_m || 1000) / 1000).toFixed(2);
    const sensorStr = u.sensor_type || 'EO/IR';
    const trackedTgt = u.tracked_target_id ? `TGT-${u.tracked_target_id}` : '--';
    const idColor = isTracked ? '#facc15' : '';
    const modeStyle = MODE_STYLES[u.mode] || { color: '#94a3b8', label: u.mode };

    card.textContent = '';

    const header = document.createElement('div');
    header.className = 'drone-card-header';

    const idSpan = document.createElement('span');
    idSpan.className = 'drone-card-id';
    if (idColor) idSpan.style.color = idColor;
    idSpan.textContent = `UAV-${u.id}`;
    header.appendChild(idSpan);

    const statusSpan = document.createElement('span');
    statusSpan.className = 'drone-card-status';
    statusSpan.style.color = modeStyle.color;
    statusSpan.style.borderColor = modeStyle.color;
    statusSpan.textContent = modeStyle.label;
    header.appendChild(statusSpan);

    card.appendChild(header);

    // Show target association for active modes
    if (u.tracked_target_id && ['FOLLOW', 'PAINT', 'INTERCEPT'].includes(u.mode)) {
        const tgtRow = document.createElement('div');
        tgtRow.className = 'drone-card-target';
        tgtRow.style.color = modeStyle.color;
        const verbMap = { FOLLOW: 'FOLLOWING', PAINT: 'PAINTING', INTERCEPT: 'INTERCEPTING' };
        tgtRow.textContent = `${verbMap[u.mode] || u.mode} TGT-${u.tracked_target_id}`;
        card.appendChild(tgtRow);
    }

    if (isTracked) {
        const details = _buildTrackedDetails(u, altKm, sensorStr, trackedTgt);
        card.appendChild(details);
    }

    card.dataset.mode = u.mode;
    card.dataset.tracked = String(isTracked);
    card.dataset.targetId = u.tracked_target_id || '';

    if (isTracked) {
        card.style.background = 'rgba(250, 204, 21, 0.15)';
        card.style.borderColor = 'rgba(250, 204, 21, 0.5)';
        _attachCardListeners(card, u);
    } else {
        card.style.background = '';
        card.style.borderColor = '';
    }
}

function _buildTrackedDetails(u, altKm, sensorStr, trackedTgt) {
    const details = document.createElement('div');
    details.className = 'drone-details';

    const statsDiv = document.createElement('div');
    statsDiv.className = 'stats';
    const rows = [
        ['Altitude:', `${altKm} km`],
        ['Sensor:', sensorStr],
        ['Tracking:', trackedTgt],
        ['Coordinates:', `${u.lon.toFixed(4)}, ${u.lat.toFixed(4)}`]
    ];
    rows.forEach(([label, value]) => {
        const row = document.createElement('div');
        row.className = 'stat-row';
        const lbl = document.createElement('span');
        lbl.className = 'stat-label';
        lbl.textContent = label;
        const val = document.createElement('span');
        val.className = 'stat-value';
        val.textContent = value;
        row.appendChild(lbl);
        row.appendChild(val);
        statsDiv.appendChild(row);
    });
    details.appendChild(statsDiv);

    // Mode command buttons
    const modeGroup = document.createElement('div');
    modeGroup.className = 'drone-mode-group';

    const modes = [
        { label: 'SEARCH', action: 'scan_area', color: '#22c55e', needsTarget: false },
        { label: 'FOLLOW', action: 'follow_target', color: '#a78bfa', needsTarget: true },
        { label: 'PAINT', action: 'paint_target', color: '#ef4444', needsTarget: true },
        { label: 'INTERCEPT', action: 'intercept_target', color: '#ff6400', needsTarget: true },
    ];

    const activeAction = { SEARCH: 'scan_area', FOLLOW: 'follow_target', PAINT: 'paint_target', INTERCEPT: 'intercept_target' };

    modes.forEach(m => {
        const btn = document.createElement('button');
        btn.className = 'drone-mode-btn';
        btn.dataset.action = m.action;
        btn.dataset.needsTarget = m.needsTarget;
        btn.textContent = m.label;
        btn.style.borderColor = m.color;
        btn.style.color = m.color;
        if (activeAction[u.mode] === m.action) {
            btn.classList.add('drone-mode-active');
            btn.style.background = m.color.replace(')', ', 0.25)').replace('rgb', 'rgba');
        }
        modeGroup.appendChild(btn);
    });
    details.appendChild(modeGroup);

    // Utility buttons row
    const btnGroup = document.createElement('div');
    btnGroup.className = 'split-btn-group';

    const wpBtn = document.createElement('button');
    wpBtn.className = 'btn-primary';
    wpBtn.id = `inlineSetWaypointBtn_${u.id}`;
    wpBtn.textContent = 'Set Waypoint';
    btnGroup.appendChild(wpBtn);

    const rangeBtn = document.createElement('button');
    rangeBtn.className = 'btn-tertiary';
    rangeBtn.id = `inlineRangeBtn_${u.id}`;
    rangeBtn.textContent = 'Range';
    btnGroup.appendChild(rangeBtn);

    const detailBtn = document.createElement('button');
    detailBtn.className = 'btn-secondary';
    detailBtn.id = `inlineDetailWaypointBtn_${u.id}`;
    detailBtn.title = 'Detail Set Waypoint';
    detailBtn.textContent = '\u{1F3AF}';
    btnGroup.appendChild(detailBtn);

    details.appendChild(btnGroup);
    return details;
}

function _attachCardListeners(card, u) {
    // Mode command buttons
    card.querySelectorAll('.drone-mode-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const action = btn.dataset.action;
            const needsTarget = btn.dataset.needsTarget === 'true';

            if (needsTarget && !state.selectedTargetId) {
                btn.textContent = 'Pick target';
                btn.style.animation = 'pulse 0.5s';
                setTimeout(() => { btn.style.animation = ''; }, 500);
                return;
            }

            const msg = { action, drone_id: parseInt(u.id) };
            if (needsTarget) msg.target_id = state.selectedTargetId;
            sendMessage(msg);
        });
    });

    const wpBtn = card.querySelector('.btn-primary');
    const detailBtn = card.querySelector('.btn-secondary');
    const rangeBtn = card.querySelector('.btn-tertiary');

    if (wpBtn) {
        wpBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            state.isSettingWaypoint = !state.isSettingWaypoint;
            if (state.isSettingWaypoint) {
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

        if (state.isSettingWaypoint) {
            wpBtn.textContent = 'Select Target...';
            wpBtn.style.background = 'rgba(34, 197, 94, 0.2)';
            wpBtn.style.borderColor = 'rgba(34, 197, 94, 0.5)';
            wpBtn.style.color = '#22c55e';
        }
    }

    if (detailBtn) {
        detailBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            document.dispatchEvent(new CustomEvent('drone:openDetailMap', { detail: u }));
        });
    }

    if (rangeBtn) {
        rangeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleRangeRings(u, rangeBtn);
        });
    }
}
