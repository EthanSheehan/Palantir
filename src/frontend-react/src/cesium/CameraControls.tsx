import React from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';
import { useViewerRef } from './CesiumContainer';

export function CameraControls() {
  const trackedDroneId = useSimStore((s) => s.trackedDroneId);
  const theater = useSimStore((s) => s.theater);
  const setTrackedDrone = useSimStore((s) => s.setTrackedDrone);
  const selectDrone = useSimStore((s) => s.selectDrone);
  const setIsSettingWaypoint = useSimStore((s) => s.setIsSettingWaypoint);
  const viewerRef = useViewerRef();

  if (trackedDroneId === null) return null;

  function decoupleCamera() {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    const entity = viewer.entities.getById(`uav_${trackedDroneId}`);
    if (entity) (entity as any).viewFrom = undefined;

    viewer.trackedEntity = undefined;
    viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);

    setTrackedDrone(null);
    selectDrone(null);
    setIsSettingWaypoint(false);
  }

  function returnToGlobe() {
    decoupleCamera();

    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    const b = theater?.bounds;
    const lon = b ? (b.min_lon + b.max_lon) / 2 : 24.9668;
    const lat = b ? (b.min_lat + b.max_lat) / 2 : 41.2;
    const alt = b
      ? Math.max(b.max_lon - b.min_lon, b.max_lat - b.min_lat) * 80000
      : 500000;

    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(lon, lat, alt),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-45.0),
        roll: 0.0,
      },
      duration: 1.5,
    });
  }

  return (
    <div
      style={{
        position: 'absolute',
        top: 16,
        left: 16,
        display: 'flex',
        flexDirection: 'row',
        gap: 4,
        zIndex: 10,
      }}
    >
      <button
        onClick={returnToGlobe}
        title="Return to globe view"
        style={{
          background: 'rgba(0,0,0,0.7)',
          border: '1px solid rgba(255,255,255,0.25)',
          color: '#e2e8f0',
          padding: '6px 10px',
          borderRadius: 4,
          cursor: 'pointer',
          fontFamily: 'monospace',
          fontSize: 12,
        }}
      >
        GLOBE
      </button>
      <button
        onClick={decoupleCamera}
        title="Decouple camera"
        style={{
          background: 'rgba(0,0,0,0.7)',
          border: '1px solid rgba(255,255,255,0.25)',
          color: '#e2e8f0',
          padding: '6px 10px',
          borderRadius: 4,
          cursor: 'pointer',
          fontFamily: 'monospace',
          fontSize: 12,
        }}
      >
        X
      </button>
    </div>
  );
}
