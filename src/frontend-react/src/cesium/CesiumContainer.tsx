import React, { useRef, createContext, useContext, RefObject } from 'react';
import * as Cesium from 'cesium';
import { useCesiumViewer } from '../hooks/useCesiumViewer';
import { useCesiumDrones } from './useCesiumDrones';
import { useCesiumTargets } from './useCesiumTargets';
import { useCesiumZones } from './useCesiumZones';
import { useCesiumFlowLines } from './useCesiumFlowLines';

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

  return (
    <ViewerContext.Provider value={viewerRef}>
      <div
        ref={containerRef}
        style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }}
      />
      {children}
    </ViewerContext.Provider>
  );
}
