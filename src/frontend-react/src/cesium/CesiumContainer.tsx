import React, { useRef, createContext, useContext, RefObject } from 'react';
import * as Cesium from 'cesium';
import { useCesiumViewer } from '../hooks/useCesiumViewer';

export const ViewerContext = createContext<RefObject<Cesium.Viewer | null>>({ current: null });

export function useViewerRef() {
  return useContext(ViewerContext);
}

export function CesiumContainer({ children }: { children?: React.ReactNode }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useCesiumViewer(containerRef);

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
