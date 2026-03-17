const API_BASE = 'http://localhost:8000';

export function initTheater() {
    const select = document.getElementById('theaterSelect');
    if (!select) return;

    fetchTheaters(select);

    select.addEventListener('change', () => {
        const theater = select.value;
        const displayName = select.options[select.selectedIndex].text;
        logToAssistant(`Switching to ${displayName}...`);
        switchTheater(theater, displayName);
    });
}

async function fetchTheaters(select) {
    try {
        const res = await fetch(`${API_BASE}/api/theaters`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        while (select.firstChild) select.removeChild(select.firstChild);
        for (const name of data.theaters) {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = formatName(name);
            select.appendChild(opt);
        }
    } catch (err) {
        console.error('Failed to fetch theaters:', err);
        while (select.firstChild) select.removeChild(select.firstChild);
        const opt = document.createElement('option');
        opt.value = 'romania';
        opt.textContent = 'Romania (default)';
        select.appendChild(opt);
    }
}

async function switchTheater(theater, displayName) {
    try {
        const res = await fetch(`${API_BASE}/api/theater`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ theater }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        logToAssistant(`Theater switched to ${displayName}.`);
    } catch (err) {
        console.error('Failed to switch theater:', err);
        logToAssistant(`Failed to switch theater: ${err.message}`);
    }
}

function formatName(name) {
    return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function logToAssistant(text) {
    const log = document.getElementById('assistant-log');
    if (!log) return;
    const msg = document.createElement('div');
    msg.className = 'assistant-msg system';
    msg.textContent = text;
    log.appendChild(msg);
    log.scrollTop = log.scrollHeight;
}
