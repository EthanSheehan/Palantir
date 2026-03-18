/**
 * Timeline Panel — swimlane view of asset reservations
 * Canvas-based renderer with video-editor-style playhead scrubbing.
 */
const TimelinePanel = (() => {
    let _canvas = null;
    let _ctx2d = null;
    let _container = null;

    // View state
    let _viewStartMs = Date.now() - 30 * 60 * 1000;  // 30 min ago
    let _viewEndMs = Date.now() + 60 * 60 * 1000;     // 1 hour ahead

    // Pan drag state
    let _isPanning = false;
    let _panStartX = 0;
    let _panStartViewStart = 0;
    let _panMoved = false;

    // Playhead / scrub state
    let _playheadMs = null;   // null = live (no playhead)
    let _isScrubbing = false;

    // Hover state for lane remove buttons
    let _hoveredLaneIdx = -1;
    let _currentAssets = []; // kept in sync by render() for event handler use

    const REMOVE_BTN_X = 2;  // left edge of × button (before the label)

    const PLAYHEAD_HIT_PX = 8; // px tolerance for grabbing the playhead

    const PHASE_COLORS = {
        idle: '#64748b',
        launch: '#f97316',
        transit: '#3b82f6',
        hold: '#eab308',
        task_execution: '#22c55e',
        'return': '#06b6d4',
        recovery: '#a855f7',
        charging: '#f59e0b',
        maintenance: '#ef4444',
    };

    const LANE_HEIGHT = 28;
    const HEADER_WIDTH = 80;
    const TOP_MARGIN = 24;

    function _xToMs(x) {
        const range = _viewEndMs - _viewStartMs;
        const dataW = _canvas.width - HEADER_WIDTH;
        return _viewStartMs + (x - HEADER_WIDTH) / dataW * range;
    }

    function _msToX(ms) {
        const range = _viewEndMs - _viewStartMs;
        const dataW = _canvas.width - HEADER_WIDTH;
        return HEADER_WIDTH + (ms - _viewStartMs) / range * dataW;
    }

    function _isNearPlayhead(clientX) {
        if (_playheadMs === null) return false;
        const rect = _canvas.getBoundingClientRect();
        const canvasX = clientX - rect.left;
        const playheadX = _msToX(_playheadMs);
        return Math.abs(canvasX - playheadX) <= PLAYHEAD_HIT_PX;
    }

    function init() {
        _container = document.getElementById('timelinePanel');
        _canvas = document.getElementById('timelineCanvas');
        if (!_canvas) return;

        _ctx2d = _canvas.getContext('2d');

        // ── Zoom ──
        _canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const zoomFactor = e.deltaY > 0 ? 1.2 : 0.8;
            const range = _viewEndMs - _viewStartMs;
            // Anchor zoom on scrub bar (yellow) if active, otherwise current time (red)
            const anchorMs = (_playheadMs !== null) ? _playheadMs : Date.now();
            // Fall back to viewport center if anchor is off-screen
            const pivot = (anchorMs >= _viewStartMs && anchorMs <= _viewEndMs)
                ? anchorMs
                : _viewStartMs + range / 2;
            const newRange = range * zoomFactor;
            const pivotRatio = (pivot - _viewStartMs) / range;
            _viewStartMs = pivot - pivotRatio * newRange;
            _viewEndMs = _viewStartMs + newRange;
            render();
        });

        // ── Mouse down: decide scrub vs pan ──
        _canvas.addEventListener('mousedown', (e) => {
            const rect = _canvas.getBoundingClientRect();
            const canvasX = e.clientX - rect.left;

            if (canvasX <= HEADER_WIDTH) return; // ignore header area

            if (_isNearPlayhead(e.clientX)) {
                // Grab the playhead → scrub mode
                _isScrubbing = true;
                _canvas.style.cursor = 'ew-resize';
            } else {
                // Start a pan drag
                _isPanning = true;
                _panMoved = false;
                _panStartX = e.clientX;
                _panStartViewStart = _viewStartMs;
                _canvas.style.cursor = 'grabbing';
            }
        });

        // ── Mouse move: scrub or pan ──
        _canvas.addEventListener('mousemove', (e) => {
            if (_isScrubbing) {
                const rect = _canvas.getBoundingClientRect();
                const canvasX = Math.max(HEADER_WIDTH, Math.min(e.clientX - rect.left, _canvas.width));
                _playheadMs = _xToMs(canvasX);
                // Clamp to not go past "now"
                _playheadMs = Math.min(_playheadMs, Date.now());
                AppState.setTimeCursor(_playheadMs);
                render();
                return;
            }

            if (_isPanning) {
                const dx = e.clientX - _panStartX;
                if (Math.abs(dx) > 3) _panMoved = true;
                const range = _viewEndMs - _viewStartMs;
                const pxPerMs = (_canvas.width - HEADER_WIDTH) / range;
                const shiftMs = -dx / pxPerMs;
                _viewStartMs = _panStartViewStart + shiftMs;
                _viewEndMs = _viewStartMs + range;
                render();
                return;
            }

            // Hover cursor hint
            if (_isNearPlayhead(e.clientX)) {
                _canvas.style.cursor = 'ew-resize';
            } else {
                const rect = _canvas.getBoundingClientRect();
                const canvasX = e.clientX - rect.left;
                const canvasY = e.clientY - rect.top;
                if (canvasX < HEADER_WIDTH) {
                    const laneIdx = Math.floor((canvasY - TOP_MARGIN) / LANE_HEIGHT);
                    const newHover = (laneIdx >= 0 && laneIdx < _currentAssets.length) ? laneIdx : -1;
                    if (newHover !== _hoveredLaneIdx) {
                        _hoveredLaneIdx = newHover;
                        render();
                    }
                    _canvas.style.cursor = (newHover >= 0 && canvasX >= REMOVE_BTN_X && canvasX < REMOVE_BTN_X + (LANE_HEIGHT - 8)) ? 'pointer' : 'default';
                } else {
                    if (_hoveredLaneIdx !== -1) { _hoveredLaneIdx = -1; render(); }
                    _canvas.style.cursor = 'crosshair';
                }
            }
        });

        // ── Mouse up: finish scrub/pan, or click-to-place ──
        window.addEventListener('mouseup', (e) => {
            if (_isScrubbing) {
                _isScrubbing = false;
                _canvas.style.cursor = 'crosshair';
                return;
            }

            if (_isPanning) {
                const wasPan = _panMoved;
                _isPanning = false;
                _canvas.style.cursor = 'crosshair';

                // If the mouse barely moved, treat as a click → place playhead
                if (!wasPan) {
                    const rect = _canvas.getBoundingClientRect();
                    const canvasX = e.clientX - rect.left;
                    if (canvasX > HEADER_WIDTH && canvasX < _canvas.width) {
                        _playheadMs = Math.min(_xToMs(canvasX), Date.now());
                        AppState.setTimeCursor(_playheadMs);
                        render();
                    }
                }
                return;
            }
        });

        // ── Mouse leave: clear lane hover ──
        _canvas.addEventListener('mouseleave', () => {
            if (_hoveredLaneIdx !== -1) { _hoveredLaneIdx = -1; render(); }
        });

        // ── Click on header × button: remove lane from selection ──
        _canvas.addEventListener('click', (e) => {
            const rect = _canvas.getBoundingClientRect();
            const canvasX = e.clientX - rect.left;
            const canvasY = e.clientY - rect.top;
            if (canvasX >= REMOVE_BTN_X && canvasX < REMOVE_BTN_X + (LANE_HEIGHT - 8)) {
                const laneIdx = Math.floor((canvasY - TOP_MARGIN) / LANE_HEIGHT);
                if (laneIdx >= 0 && laneIdx < _currentAssets.length) {
                    const removedId = _currentAssets[laneIdx].id;
                    const newIds = AppState.state.selection.assetIds.filter(id => id !== removedId);
                    AppState.selectMulti(newIds);
                }
            }
        });

        // ── Double-click: return to live ──
        _canvas.addEventListener('dblclick', (e) => {
            const rect = _canvas.getBoundingClientRect();
            const canvasX = e.clientX - rect.left;
            if (canvasX > HEADER_WIDTH) {
                _playheadMs = null;
                AppState.setTimeCursor(null);
                render();
            }
        });

        // ── Drag-and-drop: accept drone cards dragged from the ASSETS panel ──
        _container.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'link';
        });
        _container.addEventListener('drop', (e) => {
            e.preventDefault();
            const uavId = e.dataTransfer.getData('uavId');
            if (!uavId) return;
            const entityId = 'uav_' + uavId;
            // Access the global Cesium viewer (defined in app.js, available at event time)
            const entity = (typeof viewer !== 'undefined') ? viewer.entities.getById(entityId) : null;
            if (entity && typeof MapToolController !== 'undefined') {
                MapToolController._triggerDroneSelectionAdditive(entity);
            }
        });

        AppState.subscribe('reservations.*', render);
        AppState.subscribe('assets.snapshot', render);
        AppState.subscribe('selection.changed', render);

        // Listen for external "return to live" (e.g. toolbar button)
        AppState.subscribe('time.cursorChanged', (ms) => {
            if (ms === null && _playheadMs !== null) {
                _playheadMs = null;
                render();
            }
        });

        // Periodic refresh
        setInterval(() => {
            if (AppState.state.timeMode === 'live') {
                render();
            }
        }, 1000);

        _loadReservations();
    }

    async function _loadReservations() {
        try {
            const data = await ApiClient.listReservations();
            data.reservations.forEach(r => AppState.updateReservation(r));
            render();
        } catch (e) {}
    }

    function render() {
        if (!_canvas || !_ctx2d) return;

        // Resize canvas to container
        const rect = _container?.getBoundingClientRect();
        if (rect) {
            _canvas.width = rect.width;
            _canvas.height = rect.height;
        }

        const ctx = _ctx2d;
        const W = _canvas.width;
        const H = _canvas.height;

        ctx.clearRect(0, 0, W, H);
        // Semi-transparent fill lets the drawer's backdrop-filter blur show through
        ctx.fillStyle = 'rgba(8, 14, 28, 0.82)';
        ctx.fillRect(0, 0, W, H);

        const selectedAssetIds = AppState.state.selection.assetIds || [];
        const allAssets = Array.from(AppState.state.assets.values());
        const assetMap = new Map(allAssets.map(a => [a.id, a]));
        // Build in selection order so swimlanes match click sequence (primary first)
        const assets = selectedAssetIds.map(id => assetMap.get(id)).filter(Boolean);
        _currentAssets = assets;
        const reservations = Array.from(AppState.state.reservations.values());
        const range = _viewEndMs - _viewStartMs;
        const dataW = W - HEADER_WIDTH;

        // Draw time axis
        ctx.fillStyle = '#94a3b8';
        ctx.font = '10px Inter, monospace';
        const tickInterval = _getTickInterval(range);
        let tickTime = Math.ceil(_viewStartMs / tickInterval) * tickInterval;
        while (tickTime < _viewEndMs) {
            const x = HEADER_WIDTH + (tickTime - _viewStartMs) / range * dataW;
            ctx.fillStyle = '#1e293b';
            ctx.fillRect(x, TOP_MARGIN, 1, H);
            ctx.fillStyle = '#94a3b8';
            const d = new Date(tickTime);
            ctx.fillText(d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), x + 2, TOP_MARGIN - 4);
            tickTime += tickInterval;
        }

        // Draw snapshot buffer range (subtle tinted background)
        const bufRange = AppState.getSnapshotBufferRange();
        if (bufRange) {
            const bx1 = Math.max(HEADER_WIDTH, _msToX(bufRange.start));
            const bx2 = Math.min(W, _msToX(bufRange.end));
            if (bx2 > bx1) {
                ctx.fillStyle = 'rgba(250, 204, 21, 0.04)';
                ctx.fillRect(bx1, TOP_MARGIN, bx2 - bx1, H - TOP_MARGIN);
            }
        }

        // Draw current time marker (red "now" line)
        const nowX = HEADER_WIDTH + (Date.now() - _viewStartMs) / range * dataW;
        if (nowX >= HEADER_WIDTH && nowX <= W) {
            ctx.fillStyle = '#ef4444';
            ctx.fillRect(nowX, TOP_MARGIN, 2, H);
        }

        // Draw lanes
        assets.forEach((asset, i) => {
            const y = TOP_MARGIN + i * LANE_HEIGHT;
            if (y > H) return;

            // Lane background (semi-transparent to preserve glass effect)
            ctx.fillStyle = i % 2 === 0 ? 'rgba(15, 23, 42, 0.82)' : 'rgba(30, 41, 59, 0.45)';
            ctx.fillRect(0, y, W, LANE_HEIGHT);

            // Asset label (offset right when × is shown to avoid overlap)
            ctx.fillStyle = '#94a3b8';
            ctx.font = '11px Inter, monospace';
            const labelX = (i === _hoveredLaneIdx) ? REMOVE_BTN_X + (LANE_HEIGHT - 8) + 4 : 4;
            ctx.fillText(asset.name || asset.id, labelX, y + LANE_HEIGHT / 2 + 4);

            // × remove button (only visible on hover)
            if (i === _hoveredLaneIdx) {
                const bx = REMOVE_BTN_X;
                const by = y + 4;
                const bSize = LANE_HEIGHT - 8;
                ctx.fillStyle = 'rgba(239,68,68,0.18)';
                ctx.beginPath();
                ctx.roundRect(bx, by, bSize, bSize, 3);
                ctx.fill();
                ctx.fillStyle = '#f87171';
                ctx.font = 'bold 11px Inter, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('×', bx + bSize / 2, by + bSize / 2 + 4);
                ctx.textAlign = 'start';
            }

            // Draw reservations for this asset
            const assetRes = reservations.filter(r => r.asset_id === asset.id);
            assetRes.forEach(r => {
                const startMs = new Date(r.start_time).getTime();
                const endMs = new Date(r.end_time).getTime();
                const x1 = HEADER_WIDTH + Math.max(0, (startMs - _viewStartMs) / range * dataW);
                const x2 = HEADER_WIDTH + Math.min(dataW, (endMs - _viewStartMs) / range * dataW);
                if (x2 < HEADER_WIDTH || x1 > W) return;

                const blockW = Math.max(2, x2 - x1);
                ctx.fillStyle = PHASE_COLORS[r.phase] || '#64748b';
                ctx.globalAlpha = r.source === 'predicted' ? 0.5 : 0.8;
                ctx.fillRect(x1, y + 2, blockW, LANE_HEIGHT - 4);
                ctx.globalAlpha = 1.0;

                // Conflict highlight
                if (r.status === 'conflict') {
                    ctx.strokeStyle = '#ef4444';
                    ctx.lineWidth = 2;
                    ctx.strokeRect(x1, y + 2, blockW, LANE_HEIGHT - 4);
                }

                // Predicted = dashed border
                if (r.source === 'predicted') {
                    ctx.strokeStyle = '#ffffff44';
                    ctx.setLineDash([4, 4]);
                    ctx.strokeRect(x1, y + 2, blockW, LANE_HEIGHT - 4);
                    ctx.setLineDash([]);
                }
            });
        });

        // Draw header separator
        ctx.fillStyle = '#334155';
        ctx.fillRect(HEADER_WIDTH - 1, 0, 1, H);

        // ── Draw playhead (gold line + handle) ──
        if (_playheadMs !== null) {
            const phX = _msToX(_playheadMs);
            if (phX >= HEADER_WIDTH && phX <= W) {
                // Vertical line
                ctx.fillStyle = '#facc15';
                ctx.fillRect(phX - 1, TOP_MARGIN, 2, H - TOP_MARGIN);

                // Triangle handle at top
                ctx.beginPath();
                ctx.moveTo(phX - 6, TOP_MARGIN - 2);
                ctx.lineTo(phX + 6, TOP_MARGIN - 2);
                ctx.lineTo(phX, TOP_MARGIN + 8);
                ctx.closePath();
                ctx.fillStyle = '#facc15';
                ctx.fill();

                // Timestamp label
                const d = new Date(_playheadMs);
                const label = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                ctx.font = 'bold 10px Inter, monospace';
                const tw = ctx.measureText(label).width;
                const labelX = Math.min(Math.max(phX - tw / 2, HEADER_WIDTH + 2), W - tw - 4);
                ctx.fillStyle = 'rgba(8, 14, 28, 0.75)';
                ctx.fillRect(labelX - 2, 0, tw + 4, 12);
                ctx.fillStyle = '#facc15';
                ctx.fillText(label, labelX, 10);
            }
        }
    }

    function _getTickInterval(rangeMs) {
        if (rangeMs > 24 * 3600 * 1000) return 6 * 3600 * 1000;
        if (rangeMs > 6 * 3600 * 1000) return 3600 * 1000;
        if (rangeMs > 3600 * 1000) return 15 * 60 * 1000;
        if (rangeMs > 30 * 60 * 1000) return 5 * 60 * 1000;
        return 60 * 1000;
    }

    function resize() {
        if (!_canvas || !_container) return;
        const rect = _container.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
            _canvas.width = rect.width;
            _canvas.height = rect.height;
            render();
        }
    }

    return { init, render, resize };
})();
