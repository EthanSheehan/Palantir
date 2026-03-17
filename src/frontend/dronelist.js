import { state } from './state.js';
import { toggleRangeRings } from './rangerings.js';
import { triggerDroneSelection } from './drones.js';

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

        if (card.dataset.mode !== u.mode || card.dataset.tracked !== String(isTracked)) {
            _renderDroneCard(card, u, isTracked);
        }
    });
}

function _renderDroneCard(card, u, isTracked) {
    const altKm = ((u.altitude_m || 1000) / 1000).toFixed(2);
    const sensorStr = u.sensor_type || 'EO/IR';
    const trackedTgt = u.tracked_target_id ? `TGT-${u.tracked_target_id}` : '--';
    const idColor = isTracked ? '#facc15' : '';

    card.textContent = '';

    const header = document.createElement('div');
    header.className = 'drone-card-header';

    const idSpan = document.createElement('span');
    idSpan.className = 'drone-card-id';
    if (idColor) idSpan.style.color = idColor;
    idSpan.textContent = `UAV-${u.id}`;
    header.appendChild(idSpan);

    const statusSpan = document.createElement('span');
    statusSpan.className = `drone-card-status status-${u.mode}`;
    statusSpan.textContent = u.mode;
    header.appendChild(statusSpan);

    card.appendChild(header);

    if (isTracked) {
        const details = _buildTrackedDetails(u, altKm, sensorStr, trackedTgt);
        card.appendChild(details);
    }

    card.dataset.mode = u.mode;
    card.dataset.tracked = String(isTracked);

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
