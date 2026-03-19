import React from 'react';
import { Card, Elevation } from '@blueprintjs/core';
import { useResizable } from '../hooks/useResizable';
import { useViewerRef } from '../cesium/CesiumContainer';
import { SidebarTabs } from './SidebarTabs';

export function Sidebar() {
  const { width, onMouseDown, setOnResize } = useResizable(300, 280, 800);
  const viewerRef = useViewerRef();

  React.useEffect(() => {
    setOnResize(() => {
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.resize();
      }
    });
  }, [viewerRef, setOnResize]);

  return (
    <div style={{ width, flexShrink: 0, display: 'flex', position: 'relative', height: '100%', overflow: 'hidden' }}>
      <Card
        elevation={Elevation.TWO}
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          borderRadius: 0,
          padding: 0,
        }}
      >
        <div style={{ padding: '12px 16px 8px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <span style={{ fontSize: 16, fontWeight: 600 }}>System Dashboard</span>
        </div>
        <SidebarTabs />
      </Card>
      <div
        onMouseDown={onMouseDown}
        style={{
          width: 8,
          cursor: 'col-resize',
          background: 'transparent',
          position: 'absolute',
          right: 0,
          top: 0,
          bottom: 0,
          zIndex: 10,
        }}
      />
    </div>
  );
}
