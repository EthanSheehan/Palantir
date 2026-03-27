import React, { useRef, useState, useEffect, createContext, useContext, RefObject, useCallback } from 'react';
import * as Cesium from 'cesium';
import { useCesiumViewer } from '../hooks/useCesiumViewer';
import { useCesiumDrones } from './useCesiumDrones';
import { useCesiumTargets } from './useCesiumTargets';
import { useCesiumZones } from './useCesiumZones';
import { useCesiumFlowLines } from './useCesiumFlowLines';
import { useCesiumSwarmLines } from './useCesiumSwarmLines';
import { useCesiumCompass } from './useCesiumCompass';
import { useCesiumMacroTrack } from './useCesiumMacroTrack';
import { useCesiumClickHandlers } from './useCesiumClickHandlers';
import { useCesiumRangeRings } from './useCesiumRangeRings';
import { useCesiumWaypoints } from './useCesiumWaypoints';
import { useCesiumLockIndicators } from './useCesiumLockIndicators';
import { useCesiumEnemyUAVs } from './useCesiumEnemyUAVs';
import { useCesiumAssessment } from './useCesiumAssessment';
import { useSatelliteLens } from './useSatelliteLens';
import { useCesiumLaunchers } from './useCesiumLaunchers';
import { useCoverageLayer } from './layers/useCoverageLayer';
import { useThreatLayer } from './layers/useThreatLayer';
import { useFusionLayer } from './layers/useFusionLayer';
import { useSwarmLayer } from './layers/useSwarmLayer';
import { useTerrainLayer } from './layers/useTerrainLayer';
import { CameraControls } from './CameraControls';
import { DroneCamPIP } from '../overlays/DroneCamPIP';
import { MapModeBar } from '../overlays/MapModeBar';
import { LayerPanel } from '../overlays/LayerPanel';
import { CameraPresets } from '../overlays/CameraPresets';
import { CesiumContextMenu } from './CesiumContextMenu';

export const ViewerContext = createContext<RefObject<Cesium.Viewer | null>>({ current: null });

export function useViewerRef() {
  return useContext(ViewerContext);
}

export function CesiumContainer({ children }: { children?: React.ReactNode }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useCesiumViewer(containerRef);

  // Entity hooks — all take viewerRef, guard internally
  const { entitiesRef: droneEntitiesRef } = useCesiumDrones(viewerRef);
  const { entitiesRef: targetEntitiesRef } = useCesiumTargets(viewerRef);
  useCesiumZones(viewerRef);
  useCesiumFlowLines(viewerRef);
  useCesiumSwarmLines(viewerRef);
  useCesiumEnemyUAVs(viewerRef);
  useCesiumAssessment(viewerRef);

  // Map mode layer hooks
  useCoverageLayer(viewerRef);
  useThreatLayer(viewerRef);
  useFusionLayer(viewerRef);
  useSwarmLayer(viewerRef);
  useTerrainLayer(viewerRef);

  // Interaction and overlay hooks
  useCesiumCompass(viewerRef, droneEntitiesRef);
  useCesiumMacroTrack(viewerRef);
  useCesiumClickHandlers(viewerRef, droneEntitiesRef, targetEntitiesRef);
  useCesiumRangeRings(viewerRef);
  useCesiumWaypoints(viewerRef);
  useCesiumLockIndicators(viewerRef, targetEntitiesRef);
  useSatelliteLens(viewerRef);
  useCesiumLaunchers(viewerRef);

  // Bridge palantir:flyTo events from SearchBar to Cesium camera
  useEffect(() => {
    function onFlyTo(e: Event) {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;
      const { lon, lat, altitude } = (e as CustomEvent<{ lon: number; lat: number; altitude: number }>).detail;
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(lon, lat, altitude || 15000),
        duration: 1.5,
      });
    }
    window.addEventListener('palantir:flyTo', onFlyTo);
    return () => window.removeEventListener('palantir:flyTo', onFlyTo);
  }, [viewerRef]);

  return (
    <ViewerContext.Provider value={viewerRef}>
      <div
        ref={containerRef}
        style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }}
      />
      <CameraControls />
      <DroneCamPIP />
      <MapModeBar />
      <LayerPanel />
      <CameraPresets />
      {children}
    </ViewerContext.Provider>
  );
}
