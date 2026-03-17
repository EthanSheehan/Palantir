import { sendMessage } from './websocket.js';

const STATUS_COLORS = {
    PENDING: { border: '#eab308', badge: 'strike-status-pending' },
    APPROVED: { border: '#22c55e', badge: 'strike-status-approved' },
    REJECTED: { border: '#ef4444', badge: 'strike-status-rejected' },
    RETASKED: { border: '#3b82f6', badge: 'strike-status-retasked' },
};

let cachedCoas = {};

export function initStrikeBoard() {
    document.addEventListener('ws:state', (e) => {
        const entries = e.detail.strike_board || [];
        updateStrikeBoard(entries);
    });

    document.addEventListener('ws:hitl_update', (e) => {
        const { coas, entry_id } = e.detail;
        if (coas && entry_id) {
            cachedCoas = { ...cachedCoas, [entry_id]: coas };
        }
    });
}

export function updateStrikeBoard(entries) {
    const container = document.getElementById('strike-board-log');
    if (!container) return;

    while (container.firstChild) container.removeChild(container.firstChild);

    if (!entries.length) {
        const empty = el('div', 'strike-empty', 'No active strike packages.');
        container.appendChild(empty);
        return;
    }

    const sorted = [...entries].sort((a, b) => {
        const order = { PENDING: 0, APPROVED: 1, RETASKED: 2, REJECTED: 3 };
        return (order[a.status] ?? 4) - (order[b.status] ?? 4);
    });

    sorted.forEach((entry) => container.appendChild(buildEntry(entry)));
}

// ── DOM helpers ──────────────────────────────────────────────────────────────

function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function actionBtn(label, cls, action, entryId, coaId) {
    const btn = el('button', `action-btn ${cls}`, label);
    btn.dataset.strikeAction = action;
    btn.dataset.entryId = entryId;
    if (coaId) btn.dataset.coaId = coaId;
    btn.addEventListener('click', handleAction);
    return btn;
}

// ── Entry rendering ──────────────────────────────────────────────────────────

function buildEntry(entry) {
    const sc = STATUS_COLORS[entry.status] || STATUS_COLORS.PENDING;
    const confidence = Math.round((entry.detection_confidence || 0) * 100);
    const priority = (entry.priority_score || 0).toFixed(1);

    const card = el('div', 'strike-entry');
    card.style.borderLeftColor = sc.border;

    // Header row
    const header = el('div', 'strike-entry-header');
    header.appendChild(el('span', 'strike-entry-type', entry.target_type));
    header.appendChild(el('span', 'strike-entry-id', entry.id));
    header.appendChild(el('span', `strike-status-badge ${sc.badge}`, entry.status));
    card.appendChild(header);

    // Meta row
    const meta = el('div', 'strike-entry-meta');
    meta.appendChild(el('span', null, `Confidence: ${confidence}%`));
    meta.appendChild(el('span', null, `Priority: ${priority}`));
    meta.appendChild(el('span', null, `ROE: ${entry.roe_evaluation || '--'}`));
    card.appendChild(meta);

    // Action buttons for PENDING entries
    if (entry.status === 'PENDING') {
        const actions = el('div', 'strike-actions');
        actions.appendChild(actionBtn('APPROVE', 'strike-btn-approve', 'approve_nomination', entry.id));
        actions.appendChild(actionBtn('REJECT', 'strike-btn-reject', 'reject_nomination', entry.id));
        actions.appendChild(actionBtn('RETASK', 'strike-btn-retask', 'retask_nomination', entry.id));
        card.appendChild(actions);
    }

    // COA cards for APPROVED entries
    if (entry.status === 'APPROVED') {
        const coas = cachedCoas[entry.id] || [];
        if (coas.length) {
            const coaList = el('div', 'strike-coa-list');
            coas.forEach((c) => coaList.appendChild(buildCoa(entry.id, c)));
            card.appendChild(coaList);
        }
    }

    return card;
}

function buildCoa(entryId, coa) {
    const isAuthorized = coa.status === 'AUTHORIZED';
    const isRejected = coa.status === 'REJECTED';
    let cls = 'strike-coa-card';
    if (isAuthorized) cls += ' coa-authorized';
    if (isRejected) cls += ' coa-rejected';

    const card = el('div', cls);

    const header = el('div', 'strike-coa-header');
    header.appendChild(el('span', 'strike-coa-name', `${coa.effector_name} (${coa.effector_type})`));
    header.appendChild(el('span', 'strike-coa-pk', `Pk: ${(coa.pk_estimate * 100).toFixed(0)}%`));
    card.appendChild(header);

    const meta = el('div', 'strike-coa-meta');
    meta.appendChild(el('span', null, `TTE: ${coa.time_to_effect_min}m`));
    meta.appendChild(el('span', null, `Risk: ${coa.risk_score.toFixed(1)}`));
    meta.appendChild(el('span', null, `Score: ${coa.composite_score.toFixed(2)}`));
    card.appendChild(meta);

    if (!isAuthorized && !isRejected) {
        const actions = el('div', 'strike-coa-actions');
        actions.appendChild(actionBtn('AUTHORIZE', 'strike-btn-approve', 'authorize_coa', entryId, coa.id));
        actions.appendChild(actionBtn('REJECT', 'strike-btn-reject', 'reject_coa', entryId));
        card.appendChild(actions);
    }

    return card;
}

// ── Action handler ───────────────────────────────────────────────────────────

function handleAction(e) {
    const btn = e.currentTarget;
    const action = btn.dataset.strikeAction;
    const entryId = btn.dataset.entryId;
    const msg = { action, entry_id: entryId };

    const rationales = {
        approve_nomination: 'Commander approved',
        reject_nomination: 'Commander rejected',
        retask_nomination: 'Retask requested',
        authorize_coa: 'COA authorized',
        reject_coa: 'COA rejected',
    };
    msg.rationale = rationales[action] || '';

    if (action === 'authorize_coa') {
        msg.coa_id = btn.dataset.coaId;
    }

    sendMessage(msg);
}
