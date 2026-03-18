/**
 * Drone Camera PIP — Canvas-based synthetic drone feed.
 * Shows a tactical camera view from the selected drone's perspective,
 * rendering nearby targets with HUD overlays, crosshair, and mode indicators.
 */
import { state } from './state.js';

const WIDTH = 400;
const HEIGHT = 300;
const SENSOR_RANGE_KM = 15;
const HFOV_DEG = 60;
const EARTH_R = 6378137;

let canvas = null;
let ctx = null;
let panel = null;
let lastTargets = [];
let lastUavs = [];
let animFrame = null;
let lockPulsePhase = 0;

const TARGET_STYLES = {
    SAM:       { color: '#ff0000', shape: 'diamond' },
    TEL:       { color: '#ff8c00', shape: 'triangle' },
    TRUCK:     { color: '#ffffff', shape: 'rect' },
    CP:        { color: '#ff6400', shape: 'square' },
    MANPADS:   { color: '#c800c8', shape: 'circle' },
    RADAR:     { color: '#00ffff', shape: 'hexagon' },
    C2_NODE:   { color: '#ffff00', shape: 'diamond' },
    LOGISTICS: { color: '#b4b4b4', shape: 'rect' },
    ARTILLERY: { color: '#ff4444', shape: 'triangle' },
    APC:       { color: '#88cc88', shape: 'square' },
};

const DEFAULT_STYLE = { color: '#00c800', shape: 'square' };

export function initDroneCam() {
    panel = document.getElementById('droneCamPanel');
    canvas = document.getElementById('droneCamCanvas');
    if (!panel || !canvas) return;
    ctx = canvas.getContext('2d');
    canvas.width = WIDTH;
    canvas.height = HEIGHT;

    // Close button
    const closeBtn = panel.querySelector('.drone-cam-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            panel.style.display = 'none';
            state.droneCamVisible = false;
        });
    }

    // Show when drone is selected
    document.addEventListener('drone:selected', () => {
        if (state.selectedDroneId != null) {
            panel.style.display = 'block';
            state.droneCamVisible = true;
            if (!animFrame) _renderLoop();
        }
    });
}

export function updateDroneCamState(uavs, targets) {
    lastUavs = uavs;
    lastTargets = targets || [];
}

function _getSelectedDrone() {
    const id = parseInt(state.selectedDroneId);
    return lastUavs.find(u => u.id === id) || null;
}

function _haversineDist(lat1, lon1, lat2, lon2) {
    const toRad = Math.PI / 180;
    const dLat = (lat2 - lat1) * toRad;
    const dLon = (lon2 - lon1) * toRad;
    const a = Math.sin(dLat / 2) ** 2 +
        Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) * Math.sin(dLon / 2) ** 2;
    return EARTH_R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function _bearing(lat1, lon1, lat2, lon2) {
    const toRad = Math.PI / 180;
    const dLon = (lon2 - lon1) * toRad;
    const y = Math.sin(dLon) * Math.cos(lat2 * toRad);
    const x = Math.cos(lat1 * toRad) * Math.sin(lat2 * toRad) -
        Math.sin(lat1 * toRad) * Math.cos(lat2 * toRad) * Math.cos(dLon);
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

function _projectTarget(drone, target) {
    const dist = _haversineDist(drone.lat, drone.lon, target.lat, target.lon);
    if (dist > SENSOR_RANGE_KM * 1000) return null;

    const brg = _bearing(drone.lat, drone.lon, target.lat, target.lon);
    const droneYaw = drone.heading_deg || 0;
    let relAngle = brg - droneYaw;
    while (relAngle > 180) relAngle -= 360;
    while (relAngle < -180) relAngle += 360;

    if (Math.abs(relAngle) > HFOV_DEG / 2) return null;

    const nx = (relAngle / HFOV_DEG) + 0.5;
    const distFactor = 1 - Math.min(dist / (SENSOR_RANGE_KM * 1000), 1);
    const ny = 0.3 + distFactor * 0.4;

    return {
        px: Math.round(nx * WIDTH),
        py: Math.round(ny * HEIGHT),
        dist,
        brg,
    };
}

function _renderLoop() {
    animFrame = requestAnimationFrame(_renderLoop);

    if (!state.droneCamVisible || panel.style.display === 'none') return;

    const drone = _getSelectedDrone();
    if (!drone) {
        _drawNoFeed();
        return;
    }

    _drawFrame(drone);
}

function _drawNoFeed() {
    ctx.fillStyle = '#141a14';
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
    ctx.fillStyle = '#00ff00';
    ctx.font = '14px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('NO FEED — SELECT DRONE', WIDTH / 2, HEIGHT / 2);
    ctx.textAlign = 'left';
}

function _drawFrame(drone) {
    const dt = 1 / 60;

    // Background
    ctx.fillStyle = '#141a14';
    ctx.fillRect(0, 0, WIDTH, HEIGHT);

    // Grid
    ctx.strokeStyle = '#1e231e';
    ctx.lineWidth = 1;
    for (let x = 0; x < WIDTH; x += 50) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, HEIGHT); ctx.stroke();
    }
    for (let y = 0; y < HEIGHT; y += 50) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(WIDTH, y); ctx.stroke();
    }

    // Render targets
    const isTracking = ['FOLLOW', 'PAINT', 'INTERCEPT'].includes(drone.mode);
    const trackedId = drone.tracked_target_id;

    for (const target of lastTargets) {
        if (target.state === 'UNDETECTED') continue;
        const proj = _projectTarget(drone, target);
        if (!proj) continue;

        const style = TARGET_STYLES[target.type] || DEFAULT_STYLE;
        const isThisTracked = trackedId === target.id;

        // Target shape
        _drawShape(proj.px, proj.py, style.shape, style.color, 12);

        // Bounding box corners
        _drawCorners(proj.px, proj.py, 18, 18, style.color);

        // Label
        ctx.fillStyle = style.color;
        ctx.font = '10px monospace';
        const conf = target.detection_confidence || 0.92;
        ctx.fillText(`${target.type} #${target.id} [${conf.toFixed(2)}]`, proj.px - 18, proj.py - 24);

        // Tracking overlays
        if (isThisTracked && isTracking) {
            _drawReticle(proj.px, proj.py);
            _drawTargetInfo(target, proj.dist, proj.brg);

            if (drone.mode === 'PAINT') {
                _drawLockBox(proj.px, proj.py, dt);
            }
        }
    }

    // HUD
    _drawHUD(drone, isTracking, trackedId);

    // Crosshair (center)
    if (drone.mode !== 'PAINT') {
        const cx = WIDTH / 2, cy = HEIGHT / 2;
        ctx.strokeStyle = '#00ff00';
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(cx - 10, cy); ctx.lineTo(cx + 10, cy); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(cx, cy - 10); ctx.lineTo(cx, cy + 10); ctx.stroke();
    }

    // Corner brackets
    _drawCornerBrackets();
}

function _drawShape(px, py, shape, color, size) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();

    if (shape === 'diamond') {
        ctx.moveTo(px, py - size); ctx.lineTo(px + size, py);
        ctx.lineTo(px, py + size); ctx.lineTo(px - size, py); ctx.closePath();
    } else if (shape === 'triangle') {
        ctx.moveTo(px, py - size); ctx.lineTo(px + size, py + size);
        ctx.lineTo(px - size, py + size); ctx.closePath();
    } else if (shape === 'rect') {
        ctx.rect(px - size, py - size / 2, size * 2, size);
    } else if (shape === 'square') {
        ctx.rect(px - size, py - size, size * 2, size * 2);
    } else if (shape === 'circle') {
        ctx.arc(px, py, size / 2, 0, Math.PI * 2);
    } else if (shape === 'hexagon') {
        for (let i = 0; i < 6; i++) {
            const a = (i / 6) * Math.PI * 2;
            const hx = px + Math.cos(a) * size;
            const hy = py + Math.sin(a) * size;
            i === 0 ? ctx.moveTo(hx, hy) : ctx.lineTo(hx, hy);
        }
        ctx.closePath();
    }
    ctx.stroke();
}

function _drawCorners(cx, cy, hw, hh, color) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    const cl = 8;
    const corners = [
        [cx - hw, cy - hh, 1, 1],
        [cx + hw, cy - hh, -1, 1],
        [cx - hw, cy + hh, 1, -1],
        [cx + hw, cy + hh, -1, -1],
    ];
    for (const [x, y, dx, dy] of corners) {
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + cl * dx, y); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y + cl * dy); ctx.stroke();
    }
}

function _drawReticle(px, py) {
    ctx.strokeStyle = '#00ff00';
    ctx.lineWidth = 1;
    const gap = 8, arm = 20;
    ctx.beginPath(); ctx.moveTo(px - arm, py); ctx.lineTo(px - gap, py); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(px + gap, py); ctx.lineTo(px + arm, py); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(px, py - arm); ctx.lineTo(px, py - gap); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(px, py + arm); ctx.lineTo(px, py + gap); ctx.stroke();
}

function _drawLockBox(px, py, dt) {
    lockPulsePhase += dt * 4;
    const pulse = 0.5 + 0.5 * Math.sin(lockPulsePhase);
    const intensity = Math.round(128 + 127 * pulse);
    const size = Math.round(22 + 6 * pulse);
    const lw = Math.max(1, Math.round(1 + 2 * pulse));

    ctx.strokeStyle = `rgb(${intensity}, 0, 0)`;
    ctx.lineWidth = lw;
    ctx.strokeRect(px - size, py - size, size * 2, size * 2);
    _drawCorners(px, py, size - 3, size - 3, ctx.strokeStyle);
}

function _drawTargetInfo(target, dist, brg) {
    const x = 20, y = HEIGHT - 80;
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.fillRect(x - 4, y - 12, 180, 68);

    ctx.fillStyle = '#00ff00';
    ctx.font = '10px monospace';
    const lines = [
        `TGT: ${target.type} #${target.id}`,
        `STATE: ${target.state || '?'}`,
        `RNG: ${dist.toFixed(0)}m  BRG: ${brg.toFixed(1)}`,
        `CONF: ${(target.detection_confidence || 0.92).toFixed(2)}`,
    ];
    lines.forEach((line, i) => ctx.fillText(line, x, y + i * 14));
}

function _drawHUD(drone, isTracking, trackedId) {
    ctx.fillStyle = '#00ff00';
    ctx.font = '11px monospace';

    // Top-left: telemetry
    ctx.fillText(`ID: UAV-${drone.id}`, 20, 18);
    ctx.fillText(`ALT: ${((drone.altitude_m || 1000) / 1000).toFixed(1)}km`, 20, 32);
    ctx.fillText(`HDG: ${(drone.heading_deg || 0).toFixed(1)}`, 20, 46);

    // Mode indicator
    const modeColors = { PAINT: '#ff0000', FOLLOW: '#a78bfa', INTERCEPT: '#ff6400', IDLE: '#00ff00', SEARCH: '#00ff00', REPOSITIONING: '#eab308', RTB: '#808080' };
    ctx.fillStyle = modeColors[drone.mode] || '#00ff00';
    ctx.fillText(`MODE: ${drone.mode || 'IDLE'}`, 20, 60);

    // Top-right: position
    ctx.fillStyle = '#00ff00';
    ctx.textAlign = 'right';
    ctx.fillText(`${drone.lat.toFixed(5)}N ${drone.lon.toFixed(5)}E`, WIDTH - 20, 18);

    // Tracking info
    if (isTracking && trackedId != null) {
        const tgt = lastTargets.find(t => t.id === trackedId);
        if (tgt) {
            const dist = _haversineDist(drone.lat, drone.lon, tgt.lat, tgt.lon);
            const brg = _bearing(drone.lat, drone.lon, tgt.lat, tgt.lon);
            ctx.fillStyle = modeColors[drone.mode] || '#00c8ff';
            ctx.fillText(`TRK: ${tgt.type} #${tgt.id}`, WIDTH - 20, 32);
            ctx.fillText(`RNG: ${dist.toFixed(0)}m BRG: ${brg.toFixed(1)}`, WIDTH - 20, 46);
            if (drone.mode === 'PAINT') {
                ctx.fillStyle = '#ff0000';
                ctx.fillText('LOCK: ACTIVE', WIDTH - 20, 60);
            }
        }
    }
    ctx.textAlign = 'left';

    // Timestamp
    ctx.fillStyle = '#00ff00';
    ctx.font = '9px monospace';
    const now = new Date();
    ctx.fillText(now.toISOString().slice(11, 19) + 'Z', WIDTH / 2 - 30, HEIGHT - 8);
}

function _drawCornerBrackets() {
    ctx.strokeStyle = '#00ff00';
    ctx.lineWidth = 1;
    const m = 12, cl = 30;

    ctx.beginPath(); ctx.moveTo(m, m); ctx.lineTo(m + cl, m); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(m, m); ctx.lineTo(m, m + cl); ctx.stroke();

    ctx.beginPath(); ctx.moveTo(WIDTH - m, m); ctx.lineTo(WIDTH - m - cl, m); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(WIDTH - m, m); ctx.lineTo(WIDTH - m, m + cl); ctx.stroke();

    ctx.beginPath(); ctx.moveTo(m, HEIGHT - m); ctx.lineTo(m + cl, HEIGHT - m); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(m, HEIGHT - m); ctx.lineTo(m, HEIGHT - m - cl); ctx.stroke();

    ctx.beginPath(); ctx.moveTo(WIDTH - m, HEIGHT - m); ctx.lineTo(WIDTH - m - cl, HEIGHT - m); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(WIDTH - m, HEIGHT - m); ctx.lineTo(WIDTH - m, HEIGHT - m - cl); ctx.stroke();
}
