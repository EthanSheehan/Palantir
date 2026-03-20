import React from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';
import { useViewerRef } from '../cesium/CesiumContainer';
import type { TheaterInfo } from '../store/types';

const PRESETS = [
  { key: 'THEATER', label: 'OVERVIEW', pitch: -45, altitude: 500000 },
  { key: 'TOP_DOWN', label: 'TOP DOWN', pitch: -90, altitude: 300000 },
  { key: 'OBLIQUE', label: 'OBLIQUE', pitch: -25, altitude: 200000 },
] as const;

function flyToPreset(
  viewer: Cesium.Viewer,
  theater: TheaterInfo | null,
  preset: (typeof PRESETS)[number]
) {
  const b = theater?.bounds;
  const lon = b ? (b.min_lon + b.max_lon) / 2 : 24.9668;
  const lat = b ? (b.min_lat + b.max_lat) / 2 : 41.2;
  viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(lon, lat, preset.altitude),
    orientation: {
      heading: Cesium.Math.toRadians(0),
      pitch: Cesium.Math.toRadians(preset.pitch),
      roll: 0.0,
    },
    duration: 1.5,
  });
}

export function CameraPresets() {
  const theater = useSimStore((s) => s.theater);
  const viewerRef = useViewerRef();

  function handlePreset(preset: (typeof PRESETS)[number]) {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    flyToPreset(viewer, theater, preset);
  }

  function handleFree() {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    viewer.trackedEntity = undefined;
    viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
  }

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 16,
        right: 16,
        zIndex: 10,
        display: 'flex',
        flexDirection: 'row',
        gap: 4,
        background: 'rgba(0,0,0,0.7)',
        borderRadius: 4,
        padding: 4,
        border: '1px solid rgba(255,255,255,0.15)',
      }}
    >
      {PRESETS.map((preset) => (
        <button
          key={preset.key}
          onClick={() => handlePreset(preset)}
          style={{
            background: 'transparent',
            border: '1px solid rgba(255,255,255,0.2)',
            color: '#e2e8f0',
            padding: '4px 8px',
            borderRadius: 3,
            cursor: 'pointer',
            fontFamily: 'monospace',
            fontSize: 11,
          }}
        >
          {preset.label}
        </button>
      ))}
      <button
        onClick={handleFree}
        style={{
          background: 'transparent',
          border: '1px solid rgba(255,255,255,0.2)',
          color: '#94a3b8',
          padding: '4px 8px',
          borderRadius: 3,
          cursor: 'pointer',
          fontFamily: 'monospace',
          fontSize: 11,
        }}
      >
        FREE
      </button>
    </div>
  );
}
