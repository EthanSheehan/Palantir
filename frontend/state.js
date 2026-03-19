/**
 * AMS Application State Store
 * Centralized state with pub/sub for reactive updates.
 * No framework — plain JS.
 */
const AppState = (() => {
    const _state = {
        // Entity maps (id -> object)
        assets: new Map(),
        missions: new Map(),
        tasks: new Map(),
        commands: new Map(),
        alerts: new Map(),
        reservations: new Map(),
        recommendations: new Map(),

        // Selection (centralized)
        selection: {
            assetId: null,       // primary selected drone (singular, always = assetIds[0])
            assetIds: [],        // ordered multi-selection: [primary, ...secondaries]
            missionId: null,
            taskId: null,
            commandId: null,
            alertId: null,
        },

        // Time
        timeCursor: null,
        timeMode: 'live',  // 'live' | 'replay' | 'preview'
        playbackSpeed: 1,

        // Connection
        connected: false,
        eventWsConnected: false,

        // Filters
        filters: {
            assetStatus: null,
            missionState: null,
            alertSeverity: null,
        },
    };

    // Subscribers: path -> [callback]
    const _subscribers = {};

    function subscribe(path, callback) {
        if (!_subscribers[path]) _subscribers[path] = [];
        _subscribers[path].push(callback);
        return () => {
            _subscribers[path] = _subscribers[path].filter(cb => cb !== callback);
        };
    }

    function _notify(path, data) {
        // Notify exact path
        if (_subscribers[path]) {
            _subscribers[path].forEach(cb => { try { cb(data); } catch(e) { console.error(e); } });
        }
        // Notify wildcard subscribers
        const parts = path.split('.');
        for (let i = parts.length - 1; i >= 0; i--) {
            const wildcard = parts.slice(0, i).join('.') + '.*';
            if (_subscribers[wildcard]) {
                _subscribers[wildcard].forEach(cb => { try { cb(data, path); } catch(e) { console.error(e); } });
            }
        }
        // Global subscribers
        if (_subscribers['*']) {
            _subscribers['*'].forEach(cb => { try { cb(data, path); } catch(e) { console.error(e); } });
        }
    }

    // ── Mutations ──

    function updateAsset(asset) {
        _state.assets.set(asset.id, asset);
        _notify('assets.updated', asset);
    }

    function updateMission(mission) {
        _state.missions.set(mission.id, mission);
        _notify('missions.updated', mission);
    }

    function updateTask(task) {
        _state.tasks.set(task.id, task);
        _notify('tasks.updated', task);
    }

    function updateCommand(cmd) {
        _state.commands.set(cmd.id, cmd);
        _notify('commands.updated', cmd);
    }

    function updateAlert(alert) {
        _state.alerts.set(alert.id, alert);
        _notify('alerts.updated', alert);
    }

    function updateReservation(res) {
        _state.reservations.set(res.id, res);
        _notify('reservations.updated', res);
    }

    function updateRecommendation(rec) {
        _state.recommendations.set(rec.id, rec);
        _notify('recommendations.updated', rec);
    }

    function select(type, id) {
        const key = type + 'Id';
        if (_state.selection[key] !== undefined) {
            _state.selection[key] = id;
            // Keep assetIds in sync with assetId (single-select resets multi-set)
            if (type === 'asset') {
                _state.selection.assetIds = id ? [id] : [];
            }
            _notify('selection.changed', { type, id, ids: _state.selection.assetIds });
        }
    }

    function selectMulti(ids) {
        // ids: ordered array, index 0 = primary drone
        _state.selection.assetIds = ids.slice();
        _state.selection.assetId  = ids.length > 0 ? ids[0] : null;
        _notify('selection.changed', { type: 'asset', id: _state.selection.assetId, ids: _state.selection.assetIds });
    }

    function clearSelection(type) {
        if (type) {
            select(type, null);
        } else {
            Object.keys(_state.selection).forEach(k => {
                _state.selection[k] = Array.isArray(_state.selection[k]) ? [] : null;
            });
            _notify('selection.changed', { type: 'all', id: null, ids: [] });
        }
    }

    function setConnected(val) {
        _state.connected = val;
        _notify('connection.changed', val);
    }

    function setEventWsConnected(val) {
        _state.eventWsConnected = val;
        _notify('connection.events', val);
    }

    function setTimeMode(mode) {
        _state.timeMode = mode;
        _notify('time.modeChanged', mode);
    }

    function setTimeCursor(ms) {
        _state.timeCursor = ms;
        if (ms === null) {
            _state.timeMode = 'live';
            _notify('time.modeChanged', 'live');
        } else if (_state.timeMode === 'live') {
            _state.timeMode = 'scrub';
            _notify('time.modeChanged', 'scrub');
        }
        _notify('time.cursorChanged', ms);
    }

    // ── Snapshot buffer for scrub replay (last 10 min at ~1Hz) ──
    const _snapshotBuffer = [];
    let _lastSnapshotMs = 0;
    const SNAPSHOT_INTERVAL_MS = 1000;
    const SNAPSHOT_MAX_AGE_MS = 10 * 60 * 1000;

    function pushSnapshot(simData) {
        const now = Date.now();
        if (now - _lastSnapshotMs < SNAPSHOT_INTERVAL_MS) return;
        _lastSnapshotMs = now;
        _snapshotBuffer.push({ time: now, data: JSON.parse(JSON.stringify(simData)) });
        // Trim old entries
        const cutoff = now - SNAPSHOT_MAX_AGE_MS;
        while (_snapshotBuffer.length > 0 && _snapshotBuffer[0].time < cutoff) {
            _snapshotBuffer.shift();
        }
    }

    function getSnapshotAt(ms) {
        if (_snapshotBuffer.length === 0) return null;
        // Binary search for closest snapshot
        let lo = 0, hi = _snapshotBuffer.length - 1;
        while (lo < hi) {
            const mid = (lo + hi) >> 1;
            if (_snapshotBuffer[mid].time < ms) lo = mid + 1;
            else hi = mid;
        }
        // Check if lo-1 is closer
        if (lo > 0 && Math.abs(_snapshotBuffer[lo - 1].time - ms) < Math.abs(_snapshotBuffer[lo].time - ms)) {
            lo = lo - 1;
        }
        return _snapshotBuffer[lo].data;
    }

    function getSnapshotBufferRange() {
        if (_snapshotBuffer.length === 0) return null;
        return { start: _snapshotBuffer[0].time, end: _snapshotBuffer[_snapshotBuffer.length - 1].time };
    }

    // ── Event reducer ──

    function handleEvent(event) {
        const type = event.type || '';

        if (type === 'connection.established') {
            // Initial snapshot
            const assets = event.payload?.assets || [];
            assets.forEach(a => _state.assets.set(a.id, a));
            _notify('assets.snapshot', Array.from(_state.assets.values()));
            return;
        }

        if (type.startsWith('asset.')) {
            if (type === 'asset.created') {
                updateAsset(event.payload.asset || event.payload);
            } else if (type === 'asset.telemetry_received') {
                const existing = _state.assets.get(event.entity_id);
                if (existing) {
                    if (event.payload.position) {
                        existing.position = event.payload.position;
                    }
                    if (event.payload.velocity) {
                        existing.velocity = event.payload.velocity;
                    }
                    if (event.payload.heading_deg !== undefined) {
                        existing.heading_deg = event.payload.heading_deg;
                    }
                    if (event.payload.battery_pct !== undefined) {
                        existing.battery_pct = event.payload.battery_pct;
                    }
                    if (event.payload.link_quality !== undefined) {
                        existing.link_quality = event.payload.link_quality;
                    }
                    _state.assets.set(event.entity_id, existing);
                    _notify('assets.telemetry', existing);
                }
            } else if (type === 'asset.status_changed') {
                const existing = _state.assets.get(event.entity_id);
                if (existing) {
                    existing.status = event.payload.new_status;
                    _state.assets.set(event.entity_id, existing);
                    _notify('assets.updated', existing);
                }
            }
        }

        if (type.startsWith('mission.')) {
            if (type === 'mission.created') {
                updateMission(event.payload.mission || event.payload);
            } else if (type === 'mission.state_changed') {
                const existing = _state.missions.get(event.entity_id);
                if (existing) {
                    existing.state = event.payload.new_state;
                    _state.missions.set(event.entity_id, existing);
                    _notify('missions.updated', existing);
                }
            }
        }

        if (type.startsWith('task.')) {
            if (type === 'task.created') {
                updateTask(event.payload.task || event.payload);
            } else if (type === 'task.state_changed') {
                const existing = _state.tasks.get(event.entity_id);
                if (existing) {
                    existing.state = event.payload.new_state;
                    _state.tasks.set(event.entity_id, existing);
                    _notify('tasks.updated', existing);
                }
            }
        }

        if (type.startsWith('command.')) {
            if (type === 'command.created') {
                updateCommand(event.payload.command || event.payload);
            } else {
                const existing = _state.commands.get(event.entity_id);
                if (existing) {
                    existing.state = event.payload.new_state || existing.state;
                    _state.commands.set(event.entity_id, existing);
                    _notify('commands.updated', existing);
                }
            }
        }

        if (type.startsWith('alert.')) {
            if (type === 'alert.created') {
                updateAlert(event.payload.alert || event.payload);
            } else {
                const existing = _state.alerts.get(event.entity_id);
                if (existing) {
                    if (type === 'alert.acknowledged') existing.state = 'acknowledged';
                    if (type === 'alert.cleared') existing.state = 'cleared';
                    _state.alerts.set(event.entity_id, existing);
                    _notify('alerts.updated', existing);
                }
            }
        }

        if (type.startsWith('timeline.')) {
            if (type === 'timeline.reservation_created') {
                updateReservation(event.payload.reservation || event.payload);
            } else if (type === 'timeline.reservation_updated') {
                _notify('reservations.updated', event.payload);
            } else if (type === 'timeline.conflict_detected') {
                _notify('timeline.conflict', event.payload);
            }
        }

        if (type === 'macrogrid.recommendation_emitted') {
            updateRecommendation(event.payload);
        }
    }

    return {
        get state() { return _state; },
        subscribe,
        updateAsset, updateMission, updateTask, updateCommand,
        updateAlert, updateReservation, updateRecommendation,
        select, selectMulti, clearSelection,
        setConnected, setEventWsConnected, setTimeMode, setTimeCursor,
        pushSnapshot, getSnapshotAt, getSnapshotBufferRange,
        handleEvent,
    };
})();
// Expose on window for ES module access (const doesn't create window properties)
window.AppState = AppState;
