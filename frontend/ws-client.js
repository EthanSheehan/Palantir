/**
 * AMS WebSocket Event Client
 * Connects to /ws/events for event-based state sync.
 */
const WsClient = (() => {
    let _ws = null;
    let _reconnectTimer = null;
    let _reconnectDelay = 2000;
    const _MAX_RECONNECT_DELAY = 30000;
    const WS_URL = `ws://${location.hostname}:8012/ws/events`;

    function connect() {
        if (_ws && _ws.readyState <= 1) return;

        _ws = new WebSocket(WS_URL);

        _ws.onopen = () => {
            console.log('[WsClient] Connected to /ws/events');
            AppState.setEventWsConnected(true);
            _reconnectDelay = 2000; // reset on success
            if (_reconnectTimer) {
                clearTimeout(_reconnectTimer);
                _reconnectTimer = null;
            }
        };

        _ws.onmessage = (evt) => {
            try {
                const event = JSON.parse(evt.data);
                AppState.handleEvent(event);
            } catch (e) {
                console.error('[WsClient] Parse error:', e);
            }
        };

        _ws.onclose = () => {
            console.log('[WsClient] Disconnected from /ws/events');
            AppState.setEventWsConnected(false);
            _scheduleReconnect();
        };

        _ws.onerror = () => {
            // Suppress noisy error logs during reconnect backoff
        };
    }

    function _scheduleReconnect() {
        if (!_reconnectTimer) {
            _reconnectTimer = setTimeout(() => {
                _reconnectTimer = null;
                connect();
            }, _reconnectDelay);
            // Exponential backoff: 2s → 4s → 8s → 16s → 30s max
            _reconnectDelay = Math.min(_reconnectDelay * 2, _MAX_RECONNECT_DELAY);
        }
    }

    function send(msg) {
        if (_ws && _ws.readyState === WebSocket.OPEN) {
            _ws.send(JSON.stringify(msg));
        }
    }

    function sendSpike(lon, lat) {
        send({ action: 'spike', lon, lat });
    }

    function sendMoveDrone(droneId, lon, lat) {
        send({ action: 'move_drone', drone_id: droneId, target_lon: lon, target_lat: lat });
    }

    function sendReset() {
        send({ action: 'reset' });
    }

    return {
        connect,
        send,
        sendSpike,
        sendMoveDrone,
        sendReset,
    };
})();
