/**
 * AMS REST API Client
 */
const ApiClient = (() => {
    const BASE = `http://${location.hostname}:8012/api/v1`;

    async function _fetch(path, options = {}) {
        const res = await fetch(`${BASE}${path}`, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ error: res.statusText }));
            throw new Error(err.detail || err.error?.message || res.statusText);
        }
        return res.json();
    }

    // ── Assets ──
    function listAssets(filters = {}) {
        const params = new URLSearchParams(filters).toString();
        return _fetch(`/assets${params ? '?' + params : ''}`);
    }

    function getAsset(id) {
        return _fetch(`/assets/${id}`);
    }

    // ── Missions ──
    function listMissions(filters = {}) {
        const params = new URLSearchParams(filters).toString();
        return _fetch(`/missions${params ? '?' + params : ''}`);
    }

    function getMission(id) {
        return _fetch(`/missions/${id}`);
    }

    function createMission(data) {
        return _fetch('/missions', { method: 'POST', body: JSON.stringify(data) });
    }

    function proposeMission(id) {
        return _fetch(`/missions/${id}/propose`, { method: 'POST' });
    }

    function approveMission(id, approvedBy = 'operator') {
        return _fetch(`/missions/${id}/approve`, {
            method: 'POST',
            body: JSON.stringify({ approved_by: approvedBy }),
        });
    }

    function pauseMission(id) {
        return _fetch(`/missions/${id}/pause`, { method: 'POST' });
    }

    function resumeMission(id) {
        return _fetch(`/missions/${id}/resume`, { method: 'POST' });
    }

    function abortMission(id) {
        return _fetch(`/missions/${id}/abort`, { method: 'POST' });
    }

    // ── Tasks ──
    function listTasks(missionId) {
        return _fetch(`/missions/${missionId}/tasks`);
    }

    function createTask(missionId, data) {
        return _fetch(`/missions/${missionId}/tasks`, { method: 'POST', body: JSON.stringify(data) });
    }

    // ── Commands ──
    function listCommands(filters = {}) {
        const params = new URLSearchParams(filters).toString();
        return _fetch(`/commands${params ? '?' + params : ''}`);
    }

    function createCommand(data) {
        return _fetch('/commands', { method: 'POST', body: JSON.stringify(data) });
    }

    function approveCommand(id, approvedBy = 'operator') {
        return _fetch(`/commands/${id}/approve`, {
            method: 'POST',
            body: JSON.stringify({ approved_by: approvedBy }),
        });
    }

    function cancelCommand(id) {
        return _fetch(`/commands/${id}/cancel`, { method: 'POST' });
    }

    // ── Timeline ──
    function listReservations(filters = {}) {
        const params = new URLSearchParams(filters).toString();
        return _fetch(`/timeline${params ? '?' + params : ''}`);
    }

    function listConflicts() {
        return _fetch('/timeline/conflicts');
    }

    // ── Alerts ──
    function listAlerts(filters = {}) {
        const params = new URLSearchParams(filters).toString();
        return _fetch(`/alerts${params ? '?' + params : ''}`);
    }

    function acknowledgeAlert(id) {
        return _fetch(`/alerts/${id}/acknowledge`, { method: 'POST' });
    }

    function clearAlert(id) {
        return _fetch(`/alerts/${id}/clear`, { method: 'POST' });
    }

    // ── Macro-grid ──
    function getZones() {
        return _fetch('/macrogrid/zones');
    }

    function getRecommendations() {
        return _fetch('/macrogrid/recommendations');
    }

    function convertRecommendation(recId) {
        return _fetch(`/macrogrid/recommendations/${recId}/convert`, { method: 'POST' });
    }

    // ── Events ──
    function queryEvents(filters = {}) {
        const params = new URLSearchParams(filters).toString();
        return _fetch(`/events${params ? '?' + params : ''}`);
    }

    return {
        listAssets, getAsset,
        listMissions, getMission, createMission, proposeMission,
        approveMission, pauseMission, resumeMission, abortMission,
        listTasks, createTask,
        listCommands, createCommand, approveCommand, cancelCommand,
        listReservations, listConflicts,
        listAlerts, acknowledgeAlert, clearAlert,
        getZones, getRecommendations, convertRecommendation,
        queryEvents,
    };
})();
