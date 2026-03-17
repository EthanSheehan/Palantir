import { state } from './state.js';
import { TARGET_MAP } from './targets.js';

const STATE_COLORS = {
    DETECTED:     { color: '#eab308', bg: 'rgba(234, 179, 8, 0.15)' },
    IDENTIFIED:   { color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)' },
    TRACKED:      { color: '#f97316', bg: 'rgba(249, 115, 22, 0.15)' },
    NOMINATED:    { color: '#ef4444', bg: 'rgba(239, 68, 68, 0.15)' },
    ENGAGED:      { color: '#dc2626', bg: 'rgba(220, 38, 38, 0.25)' },
    NEUTRALIZED:  { color: '#64748b', bg: 'rgba(100, 116, 139, 0.15)' },
};

export function updateEnemyList(targets) {
    const container = document.getElementById('enemyListContainer');
    if (!container) return;

    const visibleTargets = targets.filter(t => {
        const targetState = t.state || (t.detected ? 'DETECTED' : 'UNDETECTED');
        return targetState !== 'UNDETECTED';
    });

    // Render threat summary
    renderThreatSummary(container, visibleTargets);

    if (visibleTargets.length === 0) {
        if (!container.querySelector('.empty-state')) {
            // Keep summary, clear cards
            clearCards(container);
            const emptyDiv = document.createElement('div');
            emptyDiv.className = 'empty-state';
            emptyDiv.textContent = 'No hostile entities detected.';
            container.appendChild(emptyDiv);
        }
        return;
    }

    const empty = container.querySelector('.empty-state');
    if (empty) container.removeChild(empty);

    const activeIds = new Set(visibleTargets.map(t => t.id));

    Array.from(container.querySelectorAll('.enemy-card')).forEach(card => {
        if (!activeIds.has(parseInt(card.dataset.id))) {
            container.removeChild(card);
        }
    });

    visibleTargets.forEach(t => {
        let card = container.querySelector(`.enemy-card[data-id="${t.id}"]`);
        if (!card) {
            card = document.createElement('div');
            card.className = 'enemy-card';
            card.dataset.id = t.id;

            card.addEventListener('click', () => {
                state.selectedTargetId = t.id;
                container.querySelectorAll('.enemy-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');

                const viewer = state.viewer;
                const entity = viewer.entities.getById(`target_${t.id}`);
                if (entity) {
                    viewer.flyTo(entity, {
                        offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-45), 1000)
                    });
                }
                document.dispatchEvent(new CustomEvent('target:selected', { detail: { id: t.id } }));

                // Show drone action bar if a drone is also selected
                if (state.selectedDroneId != null) {
                    const actionBar = document.getElementById('droneActionBar');
                    if (actionBar) {
                        actionBar.style.display = 'block';
                        const droneLabel = document.getElementById('actionBarDrone');
                        const targetLabel = document.getElementById('actionBarTarget');
                        if (droneLabel) droneLabel.textContent = `UAV-${state.selectedDroneId}`;
                        if (targetLabel) targetLabel.textContent = `TGT-${t.id}`;
                    }
                }
            });

            container.appendChild(card);
        }

        const targetState = t.state || (t.detected ? 'DETECTED' : 'UNDETECTED');
        const confidence = t.detection_confidence ? Math.round(t.detection_confidence * 100) : (t.detected ? 100 : 0);
        const config = TARGET_MAP[t.type] || { color: '#ffcc00', label: 'TGT' };
        const stateStyle = STATE_COLORS[targetState] || { color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.1)' };

        const isSelected = (t.id === state.selectedTargetId);
        if (isSelected && !card.classList.contains('selected')) {
            card.classList.add('selected');
        } else if (!isSelected && card.classList.contains('selected')) {
            card.classList.remove('selected');
        }

        // Apply state-based border color
        if (targetState === 'ENGAGED') {
            card.classList.add('enemy-card-engaged');
        } else {
            card.classList.remove('enemy-card-engaged');
        }
        if (targetState === 'NEUTRALIZED') {
            card.classList.add('enemy-card-neutralized');
        } else {
            card.classList.remove('enemy-card-neutralized');
        }

        card.textContent = '';

        const infoDiv = document.createElement('div');
        infoDiv.className = 'enemy-card-info';

        // ID with type icon/label
        const idRow = document.createElement('div');
        idRow.style.display = 'flex';
        idRow.style.alignItems = 'center';
        idRow.style.gap = '6px';

        const typeBadge = document.createElement('span');
        typeBadge.className = 'enemy-type-badge';
        typeBadge.style.background = config.color;
        typeBadge.style.color = '#000';
        typeBadge.style.padding = '1px 5px';
        typeBadge.style.borderRadius = '3px';
        typeBadge.style.fontSize = '0.6rem';
        typeBadge.style.fontWeight = '800';
        typeBadge.style.letterSpacing = '0.03em';
        typeBadge.textContent = config.label;
        idRow.appendChild(typeBadge);

        const idSpan = document.createElement('span');
        idSpan.className = 'enemy-card-id';
        idSpan.style.color = config.color;
        idSpan.textContent = `TARGET-${t.id}`;
        idRow.appendChild(idSpan);

        // Concealment indicator
        if (t.concealed) {
            const concealIcon = document.createElement('span');
            concealIcon.className = 'enemy-concealed-badge';
            concealIcon.title = 'Target is concealed';
            concealIcon.textContent = 'CONCEALED';
            idRow.appendChild(concealIcon);
        }

        infoDiv.appendChild(idRow);

        const typeDiv = document.createElement('div');
        typeDiv.className = 'enemy-card-type';
        typeDiv.textContent = t.type;
        infoDiv.appendChild(typeDiv);

        const stateSpan = document.createElement('span');
        stateSpan.className = 'enemy-card-state';
        stateSpan.style.color = stateStyle.color;
        stateSpan.style.background = stateStyle.bg;
        stateSpan.textContent = targetState;
        infoDiv.appendChild(stateSpan);

        card.appendChild(infoDiv);

        const metaDiv = document.createElement('div');
        metaDiv.className = 'enemy-card-meta';

        const coordsDiv = document.createElement('div');
        coordsDiv.className = 'enemy-card-coords';
        coordsDiv.textContent = `${t.lat.toFixed(4)}, ${t.lon.toFixed(4)}`;
        metaDiv.appendChild(coordsDiv);

        const confDiv = document.createElement('div');
        confDiv.className = 'enemy-card-confidence';
        confDiv.textContent = `${confidence}% CONF`;
        metaDiv.appendChild(confDiv);

        card.appendChild(metaDiv);
    });
}

function renderThreatSummary(container, visibleTargets) {
    let summary = container.querySelector('.threat-summary');
    if (!summary) {
        summary = document.createElement('div');
        summary.className = 'threat-summary';
        container.insertBefore(summary, container.firstChild);
    }

    const neutralized = visibleTargets.filter(t => (t.state || '') === 'NEUTRALIZED').length;
    const active = visibleTargets.length - neutralized;

    summary.textContent = '';

    const activeSpan = document.createElement('span');
    activeSpan.className = 'threat-count-active';
    activeSpan.textContent = `${active} Active`;
    summary.appendChild(activeSpan);

    const sep = document.createTextNode(' / ');
    summary.appendChild(sep);

    const neutSpan = document.createElement('span');
    neutSpan.className = 'threat-count-neutralized';
    neutSpan.textContent = `${neutralized} Neutralized`;
    summary.appendChild(neutSpan);
}

function clearCards(container) {
    Array.from(container.querySelectorAll('.enemy-card')).forEach(c => container.removeChild(c));
}
