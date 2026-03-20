import { useEffect } from 'react';
import { useSimStore } from '../store/SimulationStore';
import { TARGET_STYLES, SENSOR_RANGE_KM, HFOV_DEG } from '../shared/constants';
import { haversineDist, bearing } from '../shared/geo';
import { UAV, Target, SensorMode } from '../store/types';

export type { SensorMode };

const DEFAULT_STYLE = { color: '#00c800', shape: 'square' };

// ---------------------------------------------------------------------------
// Geometry helpers
// ---------------------------------------------------------------------------

function projectTarget(
  drone: UAV,
  target: Target,
  width: number,
  height: number,
): { px: number; py: number; dist: number; brg: number } | null {
  const dist = haversineDist(drone.lat, drone.lon, target.lat, target.lon);
  if (dist > SENSOR_RANGE_KM * 1000) return null;

  const brg = bearing(drone.lat, drone.lon, target.lat, target.lon);
  const droneYaw = drone.heading_deg || 0;
  let relAngle = brg - droneYaw;
  while (relAngle > 180) relAngle -= 360;
  while (relAngle < -180) relAngle += 360;

  if (Math.abs(relAngle) > HFOV_DEG / 2) return null;

  const nx = relAngle / HFOV_DEG + 0.5;
  const distFactor = 1 - Math.min(dist / (SENSOR_RANGE_KM * 1000), 1);
  const ny = 0.3 + distFactor * 0.4;

  return {
    px: Math.round(nx * width),
    py: Math.round(ny * height),
    dist,
    brg,
  };
}

// ---------------------------------------------------------------------------
// Shared drawing primitives
// ---------------------------------------------------------------------------

function drawShape(
  ctx: CanvasRenderingContext2D,
  px: number,
  py: number,
  shape: string,
  color: string,
  size: number,
) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();

  if (shape === 'diamond') {
    ctx.moveTo(px, py - size);
    ctx.lineTo(px + size, py);
    ctx.lineTo(px, py + size);
    ctx.lineTo(px - size, py);
    ctx.closePath();
  } else if (shape === 'triangle') {
    ctx.moveTo(px, py - size);
    ctx.lineTo(px + size, py + size);
    ctx.lineTo(px - size, py + size);
    ctx.closePath();
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

function drawCorners(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  hw: number,
  hh: number,
  color: string,
) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  const cl = 8;
  const corners: [number, number, number, number][] = [
    [cx - hw, cy - hh, 1, 1],
    [cx + hw, cy - hh, -1, 1],
    [cx - hw, cy + hh, 1, -1],
    [cx + hw, cy + hh, -1, -1],
  ];
  for (const [x, y, dx, dy] of corners) {
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + cl * dx, y);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x, y + cl * dy);
    ctx.stroke();
  }
}

function drawReticle(ctx: CanvasRenderingContext2D, px: number, py: number) {
  ctx.strokeStyle = '#00ff00';
  ctx.lineWidth = 1;
  const gap = 8, arm = 20;
  ctx.beginPath(); ctx.moveTo(px - arm, py); ctx.lineTo(px - gap, py); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(px + gap, py); ctx.lineTo(px + arm, py); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(px, py - arm); ctx.lineTo(px, py - gap); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(px, py + gap); ctx.lineTo(px, py + arm); ctx.stroke();
}

let lockPulsePhase = 0;

function drawLockBox(ctx: CanvasRenderingContext2D, px: number, py: number) {
  lockPulsePhase += (1 / 60) * 4;
  const pulse = 0.5 + 0.5 * Math.sin(lockPulsePhase);
  const intensity = Math.round(128 + 127 * pulse);
  const size = Math.round(22 + 6 * pulse);
  const lw = Math.max(1, Math.round(1 + 2 * pulse));

  ctx.strokeStyle = `rgb(${intensity}, 0, 0)`;
  ctx.lineWidth = lw;
  ctx.strokeRect(px - size, py - size, size * 2, size * 2);
  drawCorners(ctx, px, py, size - 3, size - 3, ctx.strokeStyle);
}

function drawCornerBrackets(ctx: CanvasRenderingContext2D, width: number, height: number) {
  ctx.strokeStyle = '#00ff00';
  ctx.lineWidth = 1;
  const m = 12, cl = 30;

  ctx.beginPath(); ctx.moveTo(m, m); ctx.lineTo(m + cl, m); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(m, m); ctx.lineTo(m, m + cl); ctx.stroke();

  ctx.beginPath(); ctx.moveTo(width - m, m); ctx.lineTo(width - m - cl, m); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(width - m, m); ctx.lineTo(width - m, m + cl); ctx.stroke();

  ctx.beginPath(); ctx.moveTo(m, height - m); ctx.lineTo(m + cl, height - m); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(m, height - m); ctx.lineTo(m, height - m - cl); ctx.stroke();

  ctx.beginPath(); ctx.moveTo(width - m, height - m); ctx.lineTo(width - m - cl, height - m); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(width - m, height - m); ctx.lineTo(width - m, height - m - cl); ctx.stroke();
}

function drawHUD(
  ctx: CanvasRenderingContext2D,
  drone: UAV,
  targets: Target[],
  width: number,
  height: number,
) {
  const modeColors: Record<string, string> = {
    PAINT: '#ff0000', FOLLOW: '#a78bfa', INTERCEPT: '#ff6400',
    IDLE: '#00ff00', SEARCH: '#00ff00', REPOSITIONING: '#eab308', RTB: '#808080',
  };

  ctx.fillStyle = '#00ff00';
  ctx.font = '11px monospace';

  ctx.fillText(`ID: UAV-${drone.id}`, 20, 18);
  ctx.fillText(`ALT: ${((drone.altitude_m || 1000) / 1000).toFixed(1)}km`, 20, 32);
  ctx.fillText(`HDG: ${(drone.heading_deg || 0).toFixed(1)}`, 20, 46);

  ctx.fillStyle = modeColors[drone.mode] || '#00ff00';
  ctx.fillText(`MODE: ${drone.mode || 'IDLE'}`, 20, 60);

  ctx.fillStyle = '#00ff00';
  ctx.textAlign = 'right';
  ctx.fillText(`${drone.lat.toFixed(5)}N ${drone.lon.toFixed(5)}E`, width - 20, 18);

  const primaryId = drone.primary_target_id;
  if (primaryId != null) {
    const tgt = targets.find((t) => t.id === primaryId);
    if (tgt) {
      const dist = haversineDist(drone.lat, drone.lon, tgt.lat, tgt.lon);
      const brg = bearing(drone.lat, drone.lon, tgt.lat, tgt.lon);
      ctx.fillStyle = modeColors[drone.mode] || '#00c8ff';
      ctx.fillText(`TRK: ${tgt.type} #${tgt.id}`, width - 20, 32);
      ctx.fillText(`RNG: ${dist.toFixed(0)}m BRG: ${brg.toFixed(1)}`, width - 20, 46);
      if (drone.mode === 'PAINT') {
        ctx.fillStyle = '#ff0000';
        ctx.fillText('LOCK: ACTIVE', width - 20, 60);
      }
    }
  }
  ctx.textAlign = 'left';

  ctx.fillStyle = '#00ff00';
  ctx.font = '9px monospace';
  const now = new Date();
  ctx.fillText(now.toISOString().slice(11, 19) + 'Z', width / 2 - 30, height - 8);
}

// ---------------------------------------------------------------------------
// "No feed" frame
// ---------------------------------------------------------------------------

function drawNoFeed(ctx: CanvasRenderingContext2D, width: number, height: number) {
  ctx.fillStyle = '#141a14';
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = '#00ff00';
  ctx.font = '14px monospace';
  ctx.textAlign = 'center';
  ctx.fillText('NO FEED — SELECT DRONE', width / 2, height / 2);
  ctx.textAlign = 'left';
}

// ---------------------------------------------------------------------------
// EO/IR frame — dark green thermal
// ---------------------------------------------------------------------------

function drawEoIrFrame(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  drone: UAV,
  targets: Target[],
) {
  // Background
  ctx.fillStyle = '#0a1a0a';
  ctx.fillRect(0, 0, width, height);

  // Grid
  ctx.strokeStyle = '#0f2010';
  ctx.lineWidth = 1;
  for (let x = 0; x < width; x += 50) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke();
  }
  for (let y = 0; y < height; y += 50) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
  }

  // Terrain noise (sparse random-alpha rects)
  const seed = Math.floor(Date.now() / 500);
  for (let i = 0; i < 30; i++) {
    const nx = ((seed * 1234 + i * 7919) % width);
    const ny = ((seed * 3571 + i * 6113) % height);
    ctx.fillStyle = `rgba(0, 40, 0, ${0.05 + (i % 5) * 0.03})`;
    ctx.fillRect(nx, ny, 4 + (i % 8), 2 + (i % 4));
  }

  const primaryId = drone.primary_target_id;
  const trackedIds = drone.tracked_target_ids || [];

  for (const target of targets) {
    if (target.state === 'UNDETECTED') continue;
    const proj = projectTarget(drone, target, width, height);
    if (!proj) continue;

    const style = TARGET_STYLES[target.type] || DEFAULT_STYLE;
    const isPrimary = primaryId === target.id;
    const isTracked = trackedIds.includes(target.id);

    // Radial glow for thermal signature
    const grd = ctx.createRadialGradient(proj.px, proj.py, 2, proj.px, proj.py, 16);
    grd.addColorStop(0, '#00ff88');
    grd.addColorStop(1, 'rgba(0, 255, 136, 0)');
    ctx.fillStyle = grd;
    ctx.beginPath();
    ctx.arc(proj.px, proj.py, 16, 0, Math.PI * 2);
    ctx.fill();

    drawShape(ctx, proj.px, proj.py, style.shape, '#00ff88', 10);

    if (isTracked && !isPrimary) {
      // Dashed bounding box for secondary tracked targets
      ctx.strokeStyle = 'rgba(0, 255, 136, 0.5)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.strokeRect(proj.px - 16, proj.py - 16, 32, 32);
      ctx.setLineDash([]);
    }

    ctx.fillStyle = '#00ff88';
    ctx.font = '10px monospace';
    const conf = target.detection_confidence || 0.0;
    ctx.fillText(`${target.type} #${target.id} [${conf.toFixed(2)}]`, proj.px - 18, proj.py - 24);

    if (isPrimary) {
      drawReticle(ctx, proj.px, proj.py);
      if (drone.mode === 'PAINT') {
        drawLockBox(ctx, proj.px, proj.py);
      }
    }
  }

  drawHUD(ctx, drone, targets, width, height);

  if (drone.mode !== 'PAINT') {
    const cx = width / 2, cy = height / 2;
    ctx.strokeStyle = '#00ff88';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(cx - 10, cy); ctx.lineTo(cx + 10, cy); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx, cy - 10); ctx.lineTo(cx, cy + 10); ctx.stroke();
  }

  drawCornerBrackets(ctx, width, height);
}

// ---------------------------------------------------------------------------
// SAR frame — amber radar
// ---------------------------------------------------------------------------

function drawSarFrame(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  drone: UAV,
  targets: Target[],
) {
  // Background
  ctx.fillStyle = '#0d0800';
  ctx.fillRect(0, 0, width, height);

  // Scattered amber noise dots
  const seed = Math.floor(Date.now() / 200);
  for (let i = 0; i < 50; i++) {
    const nx = (seed * 1789 + i * 4567) % width;
    const ny = (seed * 2311 + i * 3299) % height;
    ctx.fillStyle = `rgba(255, 179, 0, ${0.05 + (i % 4) * 0.04})`;
    ctx.fillRect(nx, ny, 2, 1);
  }

  // Moving scan-line
  const scanY = (Date.now() / 30) % height;
  const scanGrd = ctx.createLinearGradient(0, scanY - 12, 0, scanY + 6);
  scanGrd.addColorStop(0, 'rgba(255, 179, 0, 0)');
  scanGrd.addColorStop(0.5, 'rgba(255, 179, 0, 0.25)');
  scanGrd.addColorStop(1, 'rgba(255, 179, 0, 0)');
  ctx.fillStyle = scanGrd;
  ctx.fillRect(0, scanY - 12, width, 18);

  const primaryId = drone.primary_target_id;
  const trackedIds = drone.tracked_target_ids || [];

  for (const target of targets) {
    if (target.state === 'UNDETECTED') continue;
    const proj = projectTarget(drone, target, width, height);
    if (!proj) continue;

    const isPrimary = primaryId === target.id;
    const isTracked = trackedIds.includes(target.id);

    // Bright amber dot center
    ctx.fillStyle = '#fff8e1';
    ctx.beginPath();
    ctx.arc(proj.px, proj.py, 3, 0, Math.PI * 2);
    ctx.fill();

    // Amber echo ring
    ctx.strokeStyle = '#ffb300';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(proj.px, proj.py, 8, 0, Math.PI * 2);
    ctx.stroke();

    // Velocity vector (short line in heading direction if we can infer it)
    const headingRad = (target.heading_deg * Math.PI) / 180;
    const vLen = 20;
    ctx.strokeStyle = '#ffb300';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(proj.px, proj.py);
    ctx.lineTo(
      proj.px + Math.sin(headingRad) * vLen,
      proj.py - Math.cos(headingRad) * vLen,
    );
    ctx.stroke();

    if (isTracked && !isPrimary) {
      ctx.strokeStyle = 'rgba(255, 179, 0, 0.5)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.strokeRect(proj.px - 14, proj.py - 14, 28, 28);
      ctx.setLineDash([]);
    }

    ctx.fillStyle = '#ffb300';
    ctx.font = '10px monospace';
    ctx.fillText(`${target.type} #${target.id}`, proj.px - 18, proj.py - 22);

    if (isPrimary && drone.mode === 'PAINT') {
      drawLockBox(ctx, proj.px, proj.py);
    }
  }

  // Amber-tinted HUD overlay
  ctx.save();
  // Replace green with amber in HUD by drawing on amber-tinted copy
  drawHUD(ctx, drone, targets, width, height);
  ctx.restore();

  if (drone.mode !== 'PAINT') {
    const cx = width / 2, cy = height / 2;
    ctx.strokeStyle = '#ffb300';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(cx - 10, cy); ctx.lineTo(cx + 10, cy); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx, cy - 10); ctx.lineTo(cx, cy + 10); ctx.stroke();
  }
}

// ---------------------------------------------------------------------------
// FUSION frame — split screen EO/IR (left) + SAR (right)
// ---------------------------------------------------------------------------

function drawFusionFrame(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  drone: UAV,
  targets: Target[],
) {
  const halfW = Math.floor(width / 2);

  // Left half: EO/IR
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, 0, halfW, height);
  ctx.clip();
  drawEoIrFrame(ctx, halfW, height, drone, targets);
  ctx.restore();

  // Right half: SAR (translated)
  ctx.save();
  ctx.translate(halfW, 0);
  ctx.beginPath();
  ctx.rect(0, 0, halfW, height);
  ctx.clip();
  drawSarFrame(ctx, halfW, height, drone, targets);
  ctx.restore();

  // Center divider line
  ctx.strokeStyle = '#334155';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(halfW, 0);
  ctx.lineTo(halfW, height);
  ctx.stroke();

  // Labels
  ctx.fillStyle = 'rgba(0,0,0,0.5)';
  ctx.fillRect(4, 4, 44, 16);
  ctx.fillRect(halfW + 4, 4, 36, 16);
  ctx.fillStyle = '#00ff88';
  ctx.font = '9px monospace';
  ctx.fillText('EO/IR', 8, 16);
  ctx.fillStyle = '#ffb300';
  ctx.fillText('SAR', halfW + 8, 16);
}

// ---------------------------------------------------------------------------
// SIGINT placeholder
// ---------------------------------------------------------------------------

function drawSigintPlaceholder(ctx: CanvasRenderingContext2D, width: number, height: number) {
  ctx.fillStyle = '#000814';
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = '#F5A623';
  ctx.font = '12px monospace';
  ctx.textAlign = 'center';
  ctx.fillText('SIGINT — SEE WATERFALL DISPLAY', width / 2, height / 2);
  ctx.textAlign = 'left';
}

// ---------------------------------------------------------------------------
// Dispatcher
// ---------------------------------------------------------------------------

function drawSensorFrame(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  drone: UAV,
  targets: Target[],
  sensorMode: SensorMode,
) {
  switch (sensorMode) {
    case 'EO_IR':
      drawEoIrFrame(ctx, width, height, drone, targets);
      break;
    case 'SAR':
      drawSarFrame(ctx, width, height, drone, targets);
      break;
    case 'FUSION':
      drawFusionFrame(ctx, width, height, drone, targets);
      break;
    case 'SIGINT':
      drawSigintPlaceholder(ctx, width, height);
      break;
  }
}

// ---------------------------------------------------------------------------
// Public hook
// ---------------------------------------------------------------------------

export function useSensorCanvas(
  droneId: number | null,
  sensorMode: SensorMode,
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
) {
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctxRaw = canvas.getContext('2d');
    if (!ctxRaw) return;
    const ctx: CanvasRenderingContext2D = ctxRaw;

    const w = canvas.clientWidth > 0 ? canvas.clientWidth : 400;
    const h = canvas.clientHeight > 0 ? canvas.clientHeight : 300;
    canvas.width = w;
    canvas.height = h;

    let animId: number;

    function renderLoop() {
      animId = requestAnimationFrame(renderLoop);

      const { uavs, targets } = useSimStore.getState();
      const drone = droneId != null ? uavs.find((u) => u.id === droneId) ?? null : null;

      if (!drone) {
        drawNoFeed(ctx, w, h);
        return;
      }

      drawSensorFrame(ctx, w, h, drone, targets, sensorMode);
    }

    animId = requestAnimationFrame(renderLoop);

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [droneId, sensorMode]); // canvasRef is stable — no dep needed
}
