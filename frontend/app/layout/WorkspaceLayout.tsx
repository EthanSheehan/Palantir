import { useEffect, useRef, useState } from 'react';
import { TopCommandBar } from './TopCommandBar';
import { LeftRail } from './LeftRail';
import { BottomTimelineDock } from './BottomTimelineDock';
import { CesiumSurfaceHost } from '../surfaces/CesiumSurfaceHost';
import { useAppStore } from '../store/appStore';
import { cesiumBridge } from '../store/adapters/cesiumBridge';
import './WorkspaceLayout.css';

/**
 * Top-level React layout shell. Replaces legacy WorkspaceShell.
 *
 * Structure:
 *   TopCommandBar (48px)
 *   Body:
 *     LeftRail (floating overlay)
 *     CesiumSurfaceHost (fills center)
 *   BottomTimelineDock (floating pill + expandable drawer)
 */
export function WorkspaceLayout() {
  const [viewerReady, setViewerReady] = useState(false);
  const shellRef = useRef<HTMLDivElement>(null);
  const layout = useAppStore((s) => s.ui.layout);

  // Wait for the Cesium viewer to exist before mounting surfaces
  useEffect(() => {
    function check() {
      if ((window as any).viewer) {
        setViewerReady(true);
        return;
      }
      requestAnimationFrame(check);
    }
    check();
  }, []);

  // Hide legacy #appContainer — React shell takes over
  useEffect(() => {
    if (!viewerReady) return;
    const appContainer = document.getElementById('appContainer');
    if (appContainer) {
      appContainer.style.display = 'none';
    }
  }, [viewerReady]);

  // Apply CSS custom properties for layout dimensions
  useEffect(() => {
    if (shellRef.current) {
      shellRef.current.style.setProperty('--ws-left-width', layout.leftWidth + 'px');
    }
  }, [layout.leftWidth]);

  // Resize Cesium when layout changes
  useEffect(() => {
    cesiumBridge.resize();
  }, [layout.leftWidth, layout.leftCollapsed]);

  // Move camera controls and context menu into correct positions
  useEffect(() => {
    if (!shellRef.current || !viewerReady) return;
    const camControls = document.getElementById('cameraControls');
    if (camControls) shellRef.current.appendChild(camControls);
    const ctxMenu = document.getElementById('drone-context-menu');
    if (ctxMenu) document.body.appendChild(ctxMenu);
    const modal = document.getElementById('detailMapModal');
    if (modal) document.body.appendChild(modal);
  }, [viewerReady]);

  return (
    <div ref={shellRef} id="workspace-shell" className="workspace-shell">
      <TopCommandBar />
      <div className="ws-body">
        {viewerReady && <CesiumSurfaceHost />}
        <LeftRail />
      </div>
      {viewerReady && <BottomTimelineDock />}
    </div>
  );
}
