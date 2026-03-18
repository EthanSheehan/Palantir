/**
 * Toolbar — time controls, scrub indicator (placed inside timeline drawer)
 */
const Toolbar = (() => {
    let _scrubLabel = null;
    let _liveBtn = null;
    let _controlsContainer = null;

    function init() {
        // Build a controls container that will be inserted into the timeline drawer header
        _controlsContainer = document.createElement('div');
        _controlsContainer.id = 'ws-timeline-controls';
        _controlsContainer.className = 'ws-timeline-controls';

        _scrubLabel = document.createElement('span');
        _scrubLabel.className = 'toolbar-scrub-label';
        _scrubLabel.style.display = 'none';
        _controlsContainer.appendChild(_scrubLabel);

        _liveBtn = document.createElement('button');
        _liveBtn.className = 'toolbar-live-btn';
        _liveBtn.textContent = 'RETURN TO LIVE';
        _liveBtn.style.display = 'none';
        _liveBtn.addEventListener('click', () => {
            AppState.setTimeCursor(null);
        });
        _controlsContainer.appendChild(_liveBtn);

        // React to cursor changes
        AppState.subscribe('time.cursorChanged', (ms) => {
            if (!_scrubLabel || !_liveBtn) return;
            if (ms === null) {
                _scrubLabel.style.display = 'none';
                _liveBtn.style.display = 'none';
            } else {
                const d = new Date(ms);
                const ts = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                _scrubLabel.textContent = `SCRUB: ${ts}`;
                _scrubLabel.style.display = 'inline-block';
                _liveBtn.style.display = 'inline-block';
            }
        });
    }

    function getControlsElement() {
        return _controlsContainer;
    }

    return { init, getControlsElement };
})();
