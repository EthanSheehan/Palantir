const MAX_MESSAGES = 50;

const SEVERITY_STYLES = {
    INFO:     { color: '#06b6d4', border: '#06b6d4' },
    WARNING:  { color: '#f59e0b', border: '#f59e0b' },
    CRITICAL: { color: '#ef4444', border: '#ef4444' },
};

export function initAssistant() {
    const log = document.getElementById('assistant-log');
    if (!log) return;

    // Listen for ASSISTANT_MESSAGE payloads
    document.addEventListener('ws:assistant', (e) => {
        const payload = e.detail;
        const severity = (payload.severity || 'INFO').toUpperCase();
        const style = SEVERITY_STYLES[severity] || SEVERITY_STYLES.INFO;
        const timestamp = payload.timestamp || new Date().toLocaleTimeString();

        appendMessage(log, timestamp, payload.text, style);
    });

    // Listen for state events to capture SITREP_RESPONSE and HITL_UPDATE
    document.addEventListener('ws:state', (e) => {
        const simState = e.detail;
        if (!simState) return;

        if (simState.sitrep_response) {
            const ts = new Date().toLocaleTimeString();
            appendMessage(log, ts, `SITREP: ${simState.sitrep_response}`, SEVERITY_STYLES.INFO);
        }

        if (simState.hitl_update) {
            const ts = new Date().toLocaleTimeString();
            const style = simState.hitl_update.severity === 'CRITICAL'
                ? SEVERITY_STYLES.CRITICAL
                : SEVERITY_STYLES.WARNING;
            appendMessage(log, ts, `HITL: ${simState.hitl_update.text || simState.hitl_update}`, style);
        }
    });
}

function appendMessage(log, timestamp, text, style) {
    const msgEl = document.createElement('div');
    msgEl.className = 'assistant-msg';
    msgEl.style.borderLeftColor = style.border;

    const ts = document.createElement('span');
    ts.className = 'assistant-msg-time';
    ts.style.color = style.color;
    ts.textContent = `[${timestamp}]`;
    msgEl.appendChild(ts);

    msgEl.appendChild(document.createTextNode(' ' + text));

    log.appendChild(msgEl);

    // Enforce max messages — remove oldest
    while (log.children.length > MAX_MESSAGES) {
        log.removeChild(log.firstChild);
    }

    // Auto-scroll to bottom
    log.scrollTop = log.scrollHeight;
}
