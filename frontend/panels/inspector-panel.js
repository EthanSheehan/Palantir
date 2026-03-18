/**
 * Inspector Panel — context-sensitive detail view for selected entity
 */
const InspectorPanel = (() => {
    let _container = null;

    function init() {
        _container = document.getElementById('inspectorContent');
        if (!_container) return;

        AppState.subscribe('selection.changed', render);
        AppState.subscribe('assets.updated', (asset) => {
            if (AppState.state.selection.assetId === asset.id) render();
        });
        AppState.subscribe('missions.updated', (mission) => {
            if (AppState.state.selection.missionId === mission.id) render();
        });
        AppState.subscribe('commands.updated', () => render());
        AppState.subscribe('alerts.updated', () => render());
    }

    function render() {
        if (!_container) return;
        const sel = AppState.state.selection;

        if (sel.assetId) {
            _renderAsset(sel.assetId);
        } else if (sel.missionId) {
            _renderMission(sel.missionId);
        } else if (sel.alertId) {
            _renderAlert(sel.alertId);
        } else {
            _container.innerHTML = '<div class="inspector-empty">Select an entity to inspect</div>';
        }
    }

    function _renderAsset(id) {
        const a = AppState.state.assets.get(id);
        if (!a) { _container.innerHTML = ''; return; }

        const pos = a.position || {};
        const vel = a.velocity || {};
        _container.innerHTML = `
            <div class="inspector-section">
                <h3>${a.name || a.id}</h3>
                <div class="inspector-badge status-${a.status}">${a.status}</div>
            </div>
            <div class="inspector-section">
                <div class="inspector-row"><span>Type</span><span>${a.type}</span></div>
                <div class="inspector-row"><span>Mode</span><span>${a.mode}</span></div>
                <div class="inspector-row"><span>Health</span><span>${a.health}</span></div>
            </div>
            <div class="inspector-section">
                <h4>Telemetry</h4>
                <div class="inspector-row"><span>Lon</span><span>${(pos.lon || 0).toFixed(5)}</span></div>
                <div class="inspector-row"><span>Lat</span><span>${(pos.lat || 0).toFixed(5)}</span></div>
                <div class="inspector-row"><span>Alt</span><span>${(pos.alt_m || 0).toFixed(0)} m</span></div>
                <div class="inspector-row"><span>Heading</span><span>${(a.heading_deg || 0).toFixed(1)}°</span></div>
                <div class="inspector-row"><span>Speed</span><span>${Math.sqrt((vel.vx_mps||0)**2 + (vel.vy_mps||0)**2).toFixed(1)} m/s</span></div>
            </div>
            <div class="inspector-section">
                <h4>Systems</h4>
                <div class="inspector-row"><span>Battery</span><span class="mono">${(a.battery_pct || 0).toFixed(1)}%</span></div>
                <div class="inspector-bar"><div class="inspector-bar-fill" style="width:${a.battery_pct || 0}%; background:${a.battery_pct > 30 ? '#22c55e' : '#ef4444'}"></div></div>
                <div class="inspector-row"><span>Link</span><span class="mono">${((a.link_quality || 0) * 100).toFixed(0)}%</span></div>
            </div>
            <div class="inspector-section">
                <h4>Assignment</h4>
                <div class="inspector-row"><span>Mission</span><span>${a.assigned_mission_id || 'None'}</span></div>
                <div class="inspector-row"><span>Task</span><span>${a.assigned_task_id || 'None'}</span></div>
            </div>
        `;
    }

    function _renderMission(id) {
        const m = AppState.state.missions.get(id);
        if (!m) { _container.innerHTML = ''; return; }

        const tasks = Array.from(AppState.state.tasks.values()).filter(t => t.mission_id === id);
        _container.innerHTML = `
            <div class="inspector-section">
                <h3>${m.name || m.id}</h3>
                <div class="inspector-badge state-${m.state}">${m.state}</div>
            </div>
            <div class="inspector-section">
                <div class="inspector-row"><span>Type</span><span>${m.type}</span></div>
                <div class="inspector-row"><span>Priority</span><span>${m.priority}</span></div>
                <div class="inspector-row"><span>Created by</span><span>${m.created_by}</span></div>
                <div class="inspector-row"><span>Approved by</span><span>${m.approved_by || '-'}</span></div>
            </div>
            <div class="inspector-section">
                <h4>Objective</h4>
                <p class="inspector-text">${m.objective || 'No objective set'}</p>
            </div>
            <div class="inspector-section">
                <h4>Tasks (${tasks.length})</h4>
                ${tasks.map(t => `
                    <div class="inspector-row clickable" onclick="AppState.select('task','${t.id}')">
                        <span>${t.type}</span>
                        <span class="inspector-badge state-${t.state}">${t.state}</span>
                    </div>
                `).join('')}
            </div>
            <div class="inspector-section">
                <h4>Assets (${(m.assigned_asset_ids || []).length})</h4>
                ${(m.assigned_asset_ids || []).map(aid => `
                    <div class="inspector-row clickable" onclick="AppState.select('asset','${aid}')">
                        <span>${aid}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    function _renderAlert(id) {
        const a = AppState.state.alerts.get(id);
        if (!a) { _container.innerHTML = ''; return; }

        _container.innerHTML = `
            <div class="inspector-section">
                <h3>Alert</h3>
                <div class="inspector-badge severity-${a.severity}">${a.severity}</div>
                <div class="inspector-badge state-${a.state}">${a.state}</div>
            </div>
            <div class="inspector-section">
                <div class="inspector-row"><span>Type</span><span>${a.type}</span></div>
                <div class="inspector-row"><span>Source</span><span>${a.source_type}: ${a.source_id}</span></div>
                <div class="inspector-row"><span>Created</span><span>${a.created_at}</span></div>
            </div>
            <div class="inspector-section">
                <h4>Message</h4>
                <p class="inspector-text">${a.message}</p>
            </div>
            ${a.state === 'open' ? `<button class="btn btn-sm" onclick="ApiClient.acknowledgeAlert('${a.id}')">Acknowledge</button>` : ''}
            ${a.state === 'acknowledged' ? `<button class="btn btn-sm" onclick="ApiClient.clearAlert('${a.id}')">Clear</button>` : ''}
        `;
    }

    return { init, render };
})();
