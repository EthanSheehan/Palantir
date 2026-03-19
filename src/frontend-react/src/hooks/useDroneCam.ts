import { useEffect, useRef } from 'react';
import { useSimStore } from '../store/SimulationStore';
import { TARGET_STYLES, SENSOR_RANGE_KM, HFOV_DEG } from '../shared/constants';
import { haversineDist, bearing } from '../shared/geo';
import { UAV, Target } from '../store/types';

const WIDTH = 400;
const HEIGHT = 300;
const DEFAULT_STYLE = { color: '#00c800', shape: 'square' };

export function useDroneCam(canvasRef: React.RefObject<HTMLCanvasElement | null>) {
  const animFrameRef = useRef<number | null>(null);
  const lockPulsePhaseRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctxRaw = canvas.getContext('2d');
    if (!ctxRaw) return;
    const ctx: CanvasRenderingContext2D = ctxRaw;

    canvas.width = WIDTH;
    canvas.height = HEIGHT;

    function getSelectedDrone(uavs: UAV[], selectedId: number | null): UAV | null {
      if (selectedId == null) return null;
      return uavs.find((u) => u.id === selectedId) ?? null;
    }

    function projectTarget(drone: UAV, target: Target): { px: number; py: number; dist: number; brg: number } | null {
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
        px: Math.round(nx * WIDTH),
        py: Math.round(ny * HEIGHT),
        dist,
        brg,
      };
    }

    function drawShape(px: number, py: number, shape: string, color: string, size: number) {
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

    function drawCorners(cx: number, cy: number, hw: number, hh: number, color: string) {
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

    function drawReticle(px: number, py: number) {
      ctx.strokeStyle = '#00ff00';
      ctx.lineWidth = 1;
      const gap = 8, arm = 20;
      ctx.beginPath(); ctx.moveTo(px - arm, py); ctx.lineTo(px - gap, py); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(px + gap, py); ctx.lineTo(px + arm, py); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(px, py - arm); ctx.lineTo(px, py - gap); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(px, py + arm); ctx.lineTo(px, py + gap); ctx.stroke();
    }

    function drawLockBox(px: number, py: number, dt: number) {
      lockPulsePhaseRef.current += dt * 4;
      const pulse = 0.5 + 0.5 * Math.sin(lockPulsePhaseRef.current);
      const intensity = Math.round(128 + 127 * pulse);
      const size = Math.round(22 + 6 * pulse);
      const lw = Math.max(1, Math.round(1 + 2 * pulse));

      ctx.strokeStyle = `rgb(${intensity}, 0, 0)`;
      ctx.lineWidth = lw;
      ctx.strokeRect(px - size, py - size, size * 2, size * 2);
      drawCorners(px, py, size - 3, size - 3, ctx.strokeStyle);
    }

    function drawTargetInfo(target: Target, dist: number, brg: number) {
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

    function drawHUD(drone: UAV, targets: Target[], isTracking: boolean, trackedId: number | null) {
      const modeColors: Record<string, string> = {
        PAINT: '#ff0000', FOLLOW: '#a78bfa', INTERCEPT: '#ff6400',
        IDLE: '#00ff00', SEARCH: '#00ff00', REPOSITIONING: '#eab308', RTB: '#808080',
      };

      ctx.fillStyle = '#00ff00';
      ctx.font = '11px monospace';

      // Top-left: telemetry
      ctx.fillText(`ID: UAV-${drone.id}`, 20, 18);
      ctx.fillText(`ALT: ${((drone.altitude_m || 1000) / 1000).toFixed(1)}km`, 20, 32);
      ctx.fillText(`HDG: ${(drone.heading_deg || 0).toFixed(1)}`, 20, 46);

      // Mode indicator
      ctx.fillStyle = modeColors[drone.mode] || '#00ff00';
      ctx.fillText(`MODE: ${drone.mode || 'IDLE'}`, 20, 60);

      // Top-right: position
      ctx.fillStyle = '#00ff00';
      ctx.textAlign = 'right';
      ctx.fillText(`${drone.lat.toFixed(5)}N ${drone.lon.toFixed(5)}E`, WIDTH - 20, 18);

      // Tracking info
      if (isTracking && trackedId != null) {
        const tgt = targets.find((t) => t.id === trackedId);
        if (tgt) {
          const dist = haversineDist(drone.lat, drone.lon, tgt.lat, tgt.lon);
          const brg = bearing(drone.lat, drone.lon, tgt.lat, tgt.lon);
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

    function drawCornerBrackets() {
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

    function drawNoFeed() {
      ctx.fillStyle = '#141a14';
      ctx.fillRect(0, 0, WIDTH, HEIGHT);
      ctx.fillStyle = '#00ff00';
      ctx.font = '14px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('NO FEED — SELECT DRONE', WIDTH / 2, HEIGHT / 2);
      ctx.textAlign = 'left';
    }

    function drawFrame(drone: UAV, targets: Target[]) {
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

      const isTracking = ['FOLLOW', 'PAINT', 'INTERCEPT'].includes(drone.mode);
      const trackedId = drone.tracked_target_id;

      for (const target of targets) {
        if (target.state === 'UNDETECTED') continue;
        const proj = projectTarget(drone, target);
        if (!proj) continue;

        const style = TARGET_STYLES[target.type] || DEFAULT_STYLE;
        const isThisTracked = trackedId === target.id;

        drawShape(proj.px, proj.py, style.shape, style.color, 12);
        drawCorners(proj.px, proj.py, 18, 18, style.color);

        ctx.fillStyle = style.color;
        ctx.font = '10px monospace';
        const conf = target.detection_confidence || 0.92;
        ctx.fillText(`${target.type} #${target.id} [${conf.toFixed(2)}]`, proj.px - 18, proj.py - 24);

        if (isThisTracked && isTracking) {
          drawReticle(proj.px, proj.py);
          drawTargetInfo(target, proj.dist, proj.brg);
          if (drone.mode === 'PAINT') {
            drawLockBox(proj.px, proj.py, dt);
          }
        }
      }

      drawHUD(drone, targets, isTracking, trackedId);

      // Crosshair (hidden in PAINT mode)
      if (drone.mode !== 'PAINT') {
        const cx = WIDTH / 2, cy = HEIGHT / 2;
        ctx.strokeStyle = '#00ff00';
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(cx - 10, cy); ctx.lineTo(cx + 10, cy); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(cx, cy - 10); ctx.lineTo(cx, cy + 10); ctx.stroke();
      }

      drawCornerBrackets();
    }

    function renderLoop() {
      animFrameRef.current = requestAnimationFrame(renderLoop);

      const { selectedDroneId, droneCamVisible, uavs, targets } = useSimStore.getState();

      if (!droneCamVisible) return;

      const drone = selectedDroneId != null ? uavs.find((u) => u.id === selectedDroneId) ?? null : null;
      if (!drone) {
        drawNoFeed();
        return;
      }

      drawFrame(drone, targets);
    }

    animFrameRef.current = requestAnimationFrame(renderLoop);

    return () => {
      if (animFrameRef.current != null) {
        cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = null;
      }
    };
  }, [canvasRef]);
}
