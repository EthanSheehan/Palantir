/**
 * Mission Panel — list missions, create, transition state
 */
const MissionPanel = (() => {
    let _container = null;

    function init() {
        _container = document.getElementById('missionListContainer');
        if (!_container) return;

        AppState.subscribe('missions.*', render);

        // Create mission form handler
        const form = document.getElementById('createMissionForm');
        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const name = document.getElementById('missionName').value;
                const type = document.getElementById('missionType').value;
                const priority = document.getElementById('missionPriority').value;
                const objective = document.getElementById('missionObjective').value;
                try {
                    await ApiClient.createMission({ name, type, priority, objective });
                    form.reset();
                    _loadMissions();
                } catch (err) {
                    console.error('Create mission failed:', err);
                }
            });
        }

        _loadMissions();
    }

    async function _loadMissions() {
        try {
            const data = await ApiClient.listMissions();
            data.missions.forEach(m => AppState.updateMission(m));
            render();
        } catch (e) {
            // API might not be ready yet
        }
    }

    function render() {
        if (!_container) return;
        const missions = Array.from(AppState.state.missions.values())
            .sort((a, b) => {
                const pri = { critical: 0, high: 1, normal: 2, low: 3 };
                return (pri[a.priority] || 2) - (pri[b.priority] || 2);
            });

        if (missions.length === 0) {
            _container.innerHTML = '<div class="empty-state">No missions. Create one below.</div>';
            return;
        }

        _container.innerHTML = missions.map(m => {
            const taskCount = (m.task_ids || []).length;
            const assetCount = (m.assigned_asset_ids || []).length;
            const isSelected = AppState.state.selection.missionId === m.id;

            return `
                <div class="mission-card ${isSelected ? 'selected' : ''}"
                     onclick="AppState.select('mission','${m.id}')">
                    <div class="mission-card-header">
                        <span class="mission-name">${m.name || m.id}</span>
                        <span class="mission-badge state-${m.state}">${m.state}</span>
                    </div>
                    <div class="mission-card-meta">
                        <span class="priority-${m.priority}">${m.priority}</span>
                        <span>${m.type}</span>
                        <span>${taskCount} tasks</span>
                        <span>${assetCount} assets</span>
                    </div>
                    <div class="mission-card-actions">
                        ${_getActions(m)}
                    </div>
                </div>
            `;
        }).join('');
    }

    function _getActions(m) {
        const actions = [];
        switch (m.state) {
            case 'draft':
                actions.push(`<button class="btn btn-xs" onclick="event.stopPropagation(); MissionPanel.propose('${m.id}')">Propose</button>`);
                break;
            case 'proposed':
                actions.push(`<button class="btn btn-xs btn-green" onclick="event.stopPropagation(); MissionPanel.approve('${m.id}')">Approve</button>`);
                break;
            case 'approved':
                actions.push(`<button class="btn btn-xs" onclick="event.stopPropagation(); MissionPanel.queue('${m.id}')">Queue</button>`);
                break;
            case 'active':
                actions.push(`<button class="btn btn-xs" onclick="event.stopPropagation(); MissionPanel.pause('${m.id}')">Pause</button>`);
                actions.push(`<button class="btn btn-xs btn-red" onclick="event.stopPropagation(); MissionPanel.abort('${m.id}')">Abort</button>`);
                break;
            case 'paused':
                actions.push(`<button class="btn btn-xs btn-green" onclick="event.stopPropagation(); MissionPanel.resume('${m.id}')">Resume</button>`);
                actions.push(`<button class="btn btn-xs btn-red" onclick="event.stopPropagation(); MissionPanel.abort('${m.id}')">Abort</button>`);
                break;
        }
        return actions.join('');
    }

    async function propose(id) { try { await ApiClient.proposeMission(id); _loadMissions(); } catch(e) { console.error(e); } }
    async function approve(id) { try { await ApiClient.approveMission(id); _loadMissions(); } catch(e) { console.error(e); } }
    async function queue(id) {
        try {
            // Queue is approve -> queued, but our API has approve endpoint
            // Need to transition: approved -> queued directly
            const res = await fetch(`http://${location.hostname}:8012/api/v1/missions/${id}/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
            _loadMissions();
        } catch(e) { console.error(e); }
    }
    async function pause(id) { try { await ApiClient.pauseMission(id); _loadMissions(); } catch(e) { console.error(e); } }
    async function resume(id) { try { await ApiClient.resumeMission(id); _loadMissions(); } catch(e) { console.error(e); } }
    async function abort(id) { try { await ApiClient.abortMission(id); _loadMissions(); } catch(e) { console.error(e); } }

    return { init, render, propose, approve, queue, pause, resume, abort };
})();
