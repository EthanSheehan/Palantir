import { state } from './state.js';

const connStatus = document.getElementById('connStatus');

export function connectWebSocket() {
    const wsUrl = 'ws://localhost:8000/ws';
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        connStatus.textContent = 'Uplink Active';
        connStatus.className = 'stat-value connected';
        state.ws.send(JSON.stringify({ type: 'IDENTIFY', client_type: 'DASHBOARD' }));
    };

    state.ws.onclose = () => {
        connStatus.textContent = 'Signal Lost';
        connStatus.className = 'stat-value disconnected';
        setTimeout(connectWebSocket, 1000);
    };

    state.ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);

        if (payload.type === 'ASSISTANT_MESSAGE') {
            document.dispatchEvent(new CustomEvent('ws:assistant', { detail: payload }));
            return;
        }

        if (payload.type === 'HITL_UPDATE') {
            document.dispatchEvent(new CustomEvent('ws:hitl_update', { detail: payload }));
            return;
        }

        if (payload.type === 'state') {
            document.dispatchEvent(new CustomEvent('ws:state', { detail: payload.data }));
        }
    };
}

export function sendMessage(msg) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify(msg));
    }
}
