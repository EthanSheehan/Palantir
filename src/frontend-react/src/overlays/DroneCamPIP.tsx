import { useRef, useState, useEffect } from 'react';
import { useSimStore } from '../store/SimulationStore';
import { useSensorCanvas } from '../hooks/useSensorCanvas';
import { SigintDisplay } from '../components/SigintDisplay';
import { SensorHUD } from '../components/SensorHUD';
import { CamLayoutSelector } from '../components/CamLayoutSelector';
import type { SensorMode } from '../store/types';

interface SlotConfig {
  droneId: number | null;
  sensorMode: SensorMode;
}

// ---------------------------------------------------------------------------
// CamSlot — single camera slot with sensor canvas + HUD + mode toggle
// ---------------------------------------------------------------------------

function CamSlot({
  droneId,
  sensorMode,
  onSensorModeChange,
  width,
  height,
}: {
  droneId: number | null;
  sensorMode: SensorMode;
  onSensorModeChange: (mode: SensorMode) => void;
  width: number;
  height: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useSensorCanvas(droneId, sensorMode, canvasRef);

  const drone = useSimStore((s) =>
    droneId != null ? s.uavs.find((u) => u.id === droneId) ?? null : null
  );
  const targets = useSimStore((s) => s.targets);

  return (
    <div style={{ position: 'relative', width, height, overflow: 'hidden', flexShrink: 0 }}>
      {sensorMode === 'SIGINT' ? (
        <SigintDisplay droneId={droneId} width={width} height={height} />
      ) : (
        <canvas
          ref={canvasRef}
          width={width}
          height={height}
          style={{ display: 'block', width, height }}
        />
      )}
      <SensorHUD drone={drone} targets={targets} sensorMode={sensorMode} />
      {/* Mini sensor mode toggle — top right of slot */}
      <div
        style={{
          position: 'absolute',
          top: 2,
          right: 2,
          display: 'flex',
          gap: 1,
          zIndex: 10,
        }}
      >
        {(['EO_IR', 'SAR', 'SIGINT', 'FUSION'] as SensorMode[]).map((m) => (
          <button
            key={m}
            onClick={() => onSensorModeChange(m)}
            style={{
              background:
                sensorMode === m ? 'rgba(45,114,210,0.6)' : 'rgba(0,0,0,0.5)',
              border: '1px solid rgba(255,255,255,0.2)',
              color: '#ccc',
              fontSize: 8,
              fontFamily: 'monospace',
              padding: '1px 3px',
              cursor: 'pointer',
              lineHeight: 1,
            }}
          >
            {m === 'EO_IR' ? 'EO' : m === 'SIGINT' ? 'SIG' : m === 'FUSION' ? 'FUS' : m}
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Slot initialisation helpers
// ---------------------------------------------------------------------------

function buildInitialSlots(
  selectedDroneId: number | null,
  uavIds: number[],
): SlotConfig[] {
  const nextActive = uavIds.find((id) => id !== selectedDroneId) ?? null;

  return [
    { droneId: selectedDroneId, sensorMode: 'EO_IR' },
    { droneId: nextActive, sensorMode: 'SAR' },
    { droneId: selectedDroneId, sensorMode: 'SAR' },
    { droneId: null, sensorMode: 'EO_IR' },
  ];
}

// ---------------------------------------------------------------------------
// DroneCamPIP — layout orchestrator
// ---------------------------------------------------------------------------

export function DroneCamPIP() {
  const selectedDroneId = useSimStore((s) => s.selectedDroneId);
  const droneCamVisible = useSimStore((s) => s.droneCamVisible);
  const setDroneCamVisible = useSimStore((s) => s.setDroneCamVisible);
  const camLayout = useSimStore((s) => s.camLayout);
  const setCamLayout = useSimStore((s) => s.setCamLayout);
  const uavs = useSimStore((s) => s.uavs);

  const uavIds = uavs.map((u) => u.id);

  // Per-slot configuration (4 slots max; only active slots are rendered)
  const [slots, setSlots] = useState<SlotConfig[]>(() =>
    buildInitialSlots(selectedDroneId, uavIds)
  );

  // Re-initialise slot 0 when the selected drone changes
  useEffect(() => {
    setSlots((prev) => {
      const next = [...prev];
      next[0] = { ...next[0], droneId: selectedDroneId };
      return next;
    });
  }, [selectedDroneId]);

  // Auto-assign QUAD slots to active (non-IDLE) drones
  useEffect(() => {
    if (camLayout !== 'QUAD') return;

    const active = uavs.filter((u) => u.mode !== 'IDLE').slice(0, 4);
    if (active.length < 4) {
      const idle = uavs.filter((u) => u.mode === 'IDLE');
      let i = 0;
      while (active.length < 4 && i < idle.length) {
        active.push(idle[i++]);
      }
    }

    const defaultModes: SensorMode[] = ['EO_IR', 'SAR', 'EO_IR', 'SAR'];
    setSlots(
      [0, 1, 2, 3].map((idx) => ({
        droneId: active[idx]?.id ?? null,
        sensorMode: defaultModes[idx],
      }))
    );
  // Re-run when layout switches to QUAD or active drone set changes length
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [camLayout]);

  // PIP secondary slot: auto-pick a drone different from primary
  useEffect(() => {
    if (camLayout !== 'PIP') return;
    const nextActive = uavs.find((u) => u.id !== selectedDroneId) ?? null;
    setSlots((prev) => {
      const next = [...prev];
      next[1] = { droneId: nextActive?.id ?? null, sensorMode: 'SAR' };
      return next;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [camLayout]);

  // SPLIT: same drone, different sensors
  useEffect(() => {
    if (camLayout !== 'SPLIT') return;
    setSlots((prev) => {
      const next = [...prev];
      next[0] = { droneId: selectedDroneId, sensorMode: 'EO_IR' };
      next[1] = { droneId: selectedDroneId, sensorMode: 'SAR' };
      return next;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [camLayout]);

  const updateSlot = (idx: number, mode: SensorMode) => {
    setSlots((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], sensorMode: mode };
      return next;
    });
  };

  const isVisible = selectedDroneId !== null && droneCamVisible;

  // Container dimensions per layout
  const containerDims = {
    SINGLE: { width: 400, height: 300 },
    PIP:    { width: 400, height: 300 },
    SPLIT:  { width: 801, height: 300 },
    QUAD:   { width: 801, height: 601 },
  }[camLayout];

  return (
    <div
      style={{
        display: isVisible ? 'block' : 'none',
        position: 'absolute',
        bottom: 16,
        right: 16,
        zIndex: 20,
        background: 'rgba(0, 0, 0, 0.85)',
        border: '1px solid rgba(0, 255, 0, 0.4)',
        borderRadius: 4,
        overflow: 'hidden',
        width: containerDims.width,
      }}
    >
      {/* Header bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '4px 8px',
          borderBottom: '1px solid rgba(0, 255, 0, 0.2)',
        }}
      >
        <span
          style={{
            fontFamily: 'monospace',
            fontSize: 11,
            color: '#00ff00',
            letterSpacing: '0.1em',
          }}
        >
          DRONE CAM
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <CamLayoutSelector layout={camLayout} onLayoutChange={setCamLayout} />
          <button
            onClick={() => setDroneCamVisible(false)}
            style={{
              background: 'none',
              border: 'none',
              color: '#666',
              cursor: 'pointer',
              fontSize: 14,
              lineHeight: 1,
              padding: '0 2px',
            }}
          >
            ×
          </button>
        </div>
      </div>

      {/* Layout body */}
      <div style={{ position: 'relative' }}>

        {/* SINGLE */}
        {camLayout === 'SINGLE' && (
          <CamSlot
            droneId={slots[0].droneId}
            sensorMode={slots[0].sensorMode}
            onSensorModeChange={(m) => updateSlot(0, m)}
            width={400}
            height={300}
          />
        )}

        {/* PIP — main canvas with small overlay top-right */}
        {camLayout === 'PIP' && (
          <div style={{ position: 'relative', width: 400, height: 300 }}>
            <CamSlot
              droneId={slots[0].droneId}
              sensorMode={slots[0].sensorMode}
              onSensorModeChange={(m) => updateSlot(0, m)}
              width={400}
              height={300}
            />
            <div
              style={{
                position: 'absolute',
                top: 4,
                right: 4,
                border: '1px solid rgba(0,255,0,0.4)',
                borderRadius: 2,
                overflow: 'hidden',
                zIndex: 5,
              }}
            >
              <CamSlot
                droneId={slots[1].droneId}
                sensorMode={slots[1].sensorMode}
                onSensorModeChange={(m) => updateSlot(1, m)}
                width={160}
                height={120}
              />
            </div>
          </div>
        )}

        {/* SPLIT — two canvases side by side */}
        {camLayout === 'SPLIT' && (
          <div style={{ display: 'flex', gap: 0 }}>
            <CamSlot
              droneId={slots[0].droneId}
              sensorMode={slots[0].sensorMode}
              onSensorModeChange={(m) => updateSlot(0, m)}
              width={400}
              height={300}
            />
            <div style={{ width: 1, background: '#334155', flexShrink: 0 }} />
            <CamSlot
              droneId={slots[1].droneId}
              sensorMode={slots[1].sensorMode}
              onSensorModeChange={(m) => updateSlot(1, m)}
              width={400}
              height={300}
            />
          </div>
        )}

        {/* QUAD — 2x2 grid */}
        {camLayout === 'QUAD' && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '400px 400px',
              gap: 1,
              background: '#334155',
            }}
          >
            {[0, 1, 2, 3].map((i) => (
              <CamSlot
                key={i}
                droneId={slots[i]?.droneId ?? null}
                sensorMode={slots[i]?.sensorMode ?? 'EO_IR'}
                onSensorModeChange={(m) => updateSlot(i, m)}
                width={400}
                height={300}
              />
            ))}
          </div>
        )}

      </div>
    </div>
  );
}
