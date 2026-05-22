/**
 * PyrenderFeed — polls /api/drone-camera/{droneId} and renders the resulting
 * PNG frame, replacing the 2D video-simulator canvas when the operator picks
 * the PYRENDER_3D sensor mode.
 *
 * Falls back gracefully when:
 *   - USE_PYRENDER is off on the backend (503)              → shows banner
 *   - The drone-camera endpoint errors out                  → shows banner
 *   - droneId is null                                       → shows placeholder
 *
 * Polling cadence (250 ms = 4 Hz) is intentionally slower than the 2D path
 * (which streams at sim tick rate) — the pyrender backend re-builds the scene
 * graph each call so we don't want to hammer it.
 */
import { useEffect, useRef, useState } from 'react';

interface Props {
  droneId: number | null;
  width: number;
  height: number;
  pitchDeg?: number;
  pollMs?: number;
}

interface BackendStatus {
  use_pyrender: boolean;
  bridge_initialized: boolean;
  fallback: string;
}

export function PyrenderFeed({ droneId, width, height, pitchDeg = 25.0, pollMs = 250 }: Props) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<BackendStatus | null>(null);
  const lastBlobRef = useRef<string | null>(null);

  // Status probe — one-shot
  useEffect(() => {
    fetch('/api/drone-camera/_status')
      .then((r) => r.json())
      .then((data: BackendStatus) => setStatus(data))
      .catch(() => setStatus({ use_pyrender: false, bridge_initialized: false, fallback: 'unknown' }));
  }, []);

  // Frame poll
  useEffect(() => {
    if (droneId == null) {
      setSrc(null);
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      try {
        const resp = await fetch(`/api/drone-camera/${droneId}?pitch_deg=${pitchDeg}`);
        if (cancelled) return;
        if (resp.status === 503) {
          setError('pyrender backend off (set USE_PYRENDER=true on backend)');
          return;
        }
        if (!resp.ok) {
          setError(`backend error ${resp.status}`);
          return;
        }
        const blob = await resp.blob();
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        if (lastBlobRef.current) URL.revokeObjectURL(lastBlobRef.current);
        lastBlobRef.current = url;
        setSrc(url);
        setError(null);
      } catch (e) {
        if (!cancelled) setError(`fetch failed: ${e}`);
      } finally {
        if (!cancelled) timer = setTimeout(tick, pollMs);
      }
    };

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      if (lastBlobRef.current) URL.revokeObjectURL(lastBlobRef.current);
      lastBlobRef.current = null;
    };
  }, [droneId, pitchDeg, pollMs]);

  if (droneId == null) {
    return (
      <div
        style={{
          width,
          height,
          background: '#0d1117',
          color: '#8b949e',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'monospace',
          fontSize: 11,
        }}
      >
        No drone selected
      </div>
    );
  }

  return (
    <div
      style={{
        position: 'relative',
        width,
        height,
        background: '#0d1117',
        overflow: 'hidden',
      }}
    >
      {src ? (
        <img
          src={src}
          alt={`Pyrender 3D feed — drone ${droneId}`}
          style={{ width, height, display: 'block', objectFit: 'cover' }}
        />
      ) : (
        <div
          style={{
            width,
            height,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#58a6ff',
            fontFamily: 'monospace',
            fontSize: 11,
          }}
        >
          {error ?? 'connecting 3D feed…'}
        </div>
      )}
      <div
        style={{
          position: 'absolute',
          bottom: 4,
          left: 4,
          background: 'rgba(0, 0, 0, 0.6)',
          border: '1px solid rgba(88, 166, 255, 0.5)',
          color: '#58a6ff',
          fontFamily: 'monospace',
          fontSize: 9,
          padding: '2px 6px',
          letterSpacing: 0.4,
        }}
      >
        {status?.use_pyrender ? '3D · PYRENDER · LIVE' : '3D · PYRENDER · OFF'}
      </div>
      {error && (
        <div
          style={{
            position: 'absolute',
            top: 4,
            left: 4,
            right: 4,
            background: 'rgba(248, 81, 73, 0.85)',
            color: '#fff',
            fontFamily: 'monospace',
            fontSize: 9,
            padding: '2px 6px',
            borderRadius: 2,
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
}
