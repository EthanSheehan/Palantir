import { useEffect, useRef, useState, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
import { Icon } from '@blueprintjs/core';
import { VerticalTaskbar } from './VerticalTaskbar';
import type { WorkspaceTab } from './VerticalTaskbar';
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
 *   VerticalTaskbar (left edge, ~44px)
 *   Body:
 *     Planner: LeftRail + CesiumSurfaceHost + BottomTimelineDock
 *     ISR: Blank grey screen (placeholder)
 */
export function WorkspaceLayout() {
  const [viewerReady, setViewerReady] = useState(false);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('plan');
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

  // Hide legacy #appContainer and tool palette — React shell takes over
  useEffect(() => {
    if (!viewerReady) return;
    const appContainer = document.getElementById('appContainer');
    if (appContainer) {
      appContainer.style.display = 'none';
    }
    const toolPalette = document.getElementById('ws-tool-palette');
    if (toolPalette) {
      toolPalette.style.display = 'none';
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
    // Render Blueprint icons into camera control buttons
    function mountIcon(btn: HTMLElement, icon: string) {
      let container = btn.querySelector('.bp5-icon-mount') as HTMLElement;
      if (container) return null; // already mounted
      container = document.createElement('span');
      container.className = 'bp5-icon-mount';
      btn.textContent = '';
      btn.appendChild(container);
      const root = createRoot(container);
      root.render(<Icon icon={icon} size={16} />);
      return root;
    }
    const globeBtn = document.getElementById('returnGlobalBtn');
    if (globeBtn) mountIcon(globeBtn, 'globe');
    const lockBtn = document.getElementById('lockZoomBtn');
    if (lockBtn) {
      const root = mountIcon(lockBtn, 'flow-end');
      if (root) {
        lockBtn.addEventListener('zoomToggle', (e: Event) => {
          const zoomOn = (e as CustomEvent).detail.zoomOn;
          root.render(<Icon icon={zoomOn ? 'flow-end' : 'layout-sorted-clusters'} size={16} />);
        });
      }
    }
    const haloBtn = document.getElementById('haloModeBtn');
    if (haloBtn) {
      const root = mountIcon(haloBtn, 'circle');
      if (root) {
        haloBtn.addEventListener('haloToggle', (e: Event) => {
          const isCanvas = (e as CustomEvent).detail.isCanvas;
          root.render(<Icon icon={isCanvas ? 'intersection' : 'circle'} size={16} />);
        });
      }
    }
  }, [viewerReady]);

  // Hide/show Cesium viewer and camera controls when switching tabs
  useEffect(() => {
    const viewer = (window as any).viewer;
    const camControls = document.getElementById('cameraControls');
    if (activeTab === 'plan') {
      if (viewer) {
        (viewer.container as HTMLElement).style.display = '';
        // Delay resize to allow browser reflow after display change,
        // otherwise canvas dimensions are still 0 and WebGL renders black
        requestAnimationFrame(() => {
          viewer.resize();
          viewer.scene.requestRender();
          cesiumBridge.resize();
        });
      }
      if (camControls) camControls.style.display = '';
    } else {
      if (viewer) (viewer.container as HTMLElement).style.display = 'none';
      if (camControls) camControls.style.display = 'none';
    }
  }, [activeTab, viewerReady]);

  const handleTabChange = useCallback((tab: WorkspaceTab) => {
    setActiveTab(tab);
  }, []);

  return (
    <div ref={shellRef} id="workspace-shell" className="workspace-shell">
      <VerticalTaskbar activeTab={activeTab} onTabChange={handleTabChange} />
      <div className="ws-body">
        {/* Plan workspace — always mounted, hidden via CSS when not active */}
        <div className="ws-plan-workspace" style={{ display: activeTab === 'plan' ? 'contents' : 'none' }}>
          {viewerReady && <CesiumSurfaceHost />}
          <LeftRail />
        </div>
        {/* ISR workspace */}
        {activeTab === 'isr' && (
          <div className="ws-isr-placeholder">
            ISR
          </div>
        )}
      </div>
      {activeTab === 'plan' && viewerReady && <BottomTimelineDock />}
    </div>
  );
}
