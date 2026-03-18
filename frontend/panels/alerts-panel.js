/**
 * Alerts Panel — operational alerts with severity and acknowledgement
 */
const AlertsPanel = (() => {
    let _container = null;

    function init() {
        _container = document.getElementById('alertsListContainer');
        if (!_container) return;

        AppState.subscribe('alerts.*', render);
        _loadAlerts();
    }

    async function _loadAlerts() {
        try {
            const data = await ApiClient.listAlerts();
            data.alerts.forEach(a => AppState.updateAlert(a));
            render();
        } catch (e) {
            // API might not be ready yet
        }
    }

    function render() {
        if (!_container) return;
        const alerts = Array.from(AppState.state.alerts.values())
            .filter(a => a.state !== 'cleared')
            .sort((a, b) => {
                const sev = { critical: 0, warning: 1, info: 2 };
                return (sev[a.severity] || 2) - (sev[b.severity] || 2);
            });

        if (alerts.length === 0) {
            _container.innerHTML = '<div class="empty-state">No active alerts</div>';
            return;
        }

        _container.innerHTML = alerts.map(a => {
            const icon = a.severity === 'critical' ? '🔴' : a.severity === 'warning' ? '🟡' : '🔵';
            const isSelected = AppState.state.selection.alertId === a.id;

            return `
                <div class="alert-card severity-${a.severity} ${isSelected ? 'selected' : ''}"
                     onclick="AppState.select('alert','${a.id}')">
                    <div class="alert-card-header">
                        <span>${icon} ${a.type.replace(/_/g, ' ')}</span>
                        <span class="alert-state">${a.state}</span>
                    </div>
                    <div class="alert-message">${a.message}</div>
                    <div class="alert-card-footer">
                        <span class="alert-source">${a.source_type}: ${a.source_id}</span>
                        ${a.state === 'open' ?
                            `<button class="btn btn-xs" onclick="event.stopPropagation(); AlertsPanel.ack('${a.id}')">ACK</button>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }

    async function ack(id) {
        try {
            await ApiClient.acknowledgeAlert(id);
            _loadAlerts();
        } catch (e) {
            console.error(e);
        }
    }

    return { init, render, ack };
})();
