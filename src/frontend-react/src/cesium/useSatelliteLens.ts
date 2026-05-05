import { useEffect, useRef, RefObject } from 'react';
import * as Cesium from 'cesium';

export function useSatelliteLens(viewerRef: RefObject<Cesium.Viewer | null>) {
  const lensViewerRef = useRef<Cesium.Viewer | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const enabledRef = useRef(false);

  function destroyLens() {
    if (lensViewerRef.current && !lensViewerRef.current.isDestroyed()) {
      lensViewerRef.current.destroy();
    }
    lensViewerRef.current = null;
    if (containerRef.current && containerRef.current.parentNode) {
      containerRef.current.parentNode.removeChild(containerRef.current);
    }
    containerRef.current = null;
    enabledRef.current = false;
  }

  function createLens() {
    const mainViewer = viewerRef.current;
    if (!mainViewer || mainViewer.isDestroyed()) return;

    const mapContainer = mainViewer.container as HTMLElement;

    const container = document.createElement('div');
    Object.assign(container.style, {
      position: 'absolute',
      bottom: '80px',
      left: '16px',
      width: '300px',
      height: '200px',
      border: '2px solid rgba(100, 180, 255, 0.6)',
      borderRadius: '8px',
      overflow: 'hidden',
      zIndex: '5',
      boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
    });

    const label = document.createElement('div');
    label.textContent = 'SAT';
    Object.assign(label.style, {
      position: 'absolute',
      top: '4px',
      left: '8px',
      color: 'rgba(100, 180, 255, 0.9)',
      fontSize: '10px',
      fontWeight: 'bold',
      letterSpacing: '1px',
      zIndex: '6',
      pointerEvents: 'none',
    });
    container.appendChild(label);

    mapContainer.appendChild(container);
    containerRef.current = container;

    const lensViewer = new Cesium.Viewer(container, {
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      selectionIndicator: false,
      navigationHelpButton: false,
      infoBox: false,
      fullscreenButton: false,
      timeline: false,
      animation: false,
      creditContainer: document.createElement('div'),
    });

    lensViewer.scene.mode = Cesium.SceneMode.SCENE3D;

    lensViewerRef.current = lensViewer;
    enabledRef.current = true;

    mainViewer.scene.postRender.addEventListener(() => {
      const lv = lensViewerRef.current;
      const mv = viewerRef.current;
      if (!lv || lv.isDestroyed() || !mv || mv.isDestroyed()) return;
      lv.camera.position = mv.camera.position.clone();
      lv.camera.direction = mv.camera.direction.clone();
      lv.camera.up = mv.camera.up.clone();
    });
  }

  function toggle() {
    if (enabledRef.current) {
      destroyLens();
    } else {
      createLens();
    }
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === 's' || e.key === 'S') toggle();
    }

    function onToggleEvent() {
      toggle();
    }

    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('grid-sentinel:toggleSatLens', onToggleEvent);

    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('grid-sentinel:toggleSatLens', onToggleEvent);
      destroyLens();
    };
  }, [viewerRef]);
}
