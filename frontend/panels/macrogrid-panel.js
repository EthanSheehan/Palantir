/**
 * Macro-Grid Recommendation Panel
 */
const MacrogridPanel = (() => {
    let _container = null;

    function init() {
        _container = document.getElementById('macrogridListContainer');
        if (!_container) return;

        AppState.subscribe('recommendations.*', render);
        _loadRecommendations();

        // Refresh periodically
        setInterval(_loadRecommendations, 10000);
    }

    async function _loadRecommendations() {
        try {
            const data = await ApiClient.getRecommendations();
            data.recommendations.forEach(r => AppState.updateRecommendation(r));
            render();
        } catch (e) {}
    }

    function render() {
        if (!_container) return;
        const recs = Array.from(AppState.state.recommendations.values())
            .sort((a, b) => Math.abs(b.pressure_delta) - Math.abs(a.pressure_delta));

        if (recs.length === 0) {
            _container.innerHTML = '<div class="empty-state">No active recommendations</div>';
            return;
        }

        _container.innerHTML = recs.map(r => `
            <div class="rec-card">
                <div class="rec-header">
                    <span>Zone ${JSON.stringify(r.source_zone?.id)} → ${JSON.stringify(r.target_zone?.id)}</span>
                    <span class="rec-confidence">${(r.confidence * 100).toFixed(0)}%</span>
                </div>
                <div class="rec-meta">
                    <span>Move ${r.suggested_asset_count} asset(s)</span>
                    <span>Pressure: ${r.pressure_delta?.toFixed(1)}</span>
                </div>
                <button class="btn btn-xs" onclick="MacrogridPanel.convert('${r.id}')">Convert to Mission</button>
            </div>
        `).join('');
    }

    async function convert(recId) {
        try {
            const mission = await ApiClient.convertRecommendation(recId);
            AppState.updateMission(mission);
            console.log('Created rebalance mission:', mission.id);
        } catch (e) {
            console.error('Convert failed:', e);
        }
    }

    return { init, render, convert };
})();
