import { useEffect, useRef } from 'react';

/**
 * Hosts the existing Cesium viewer by reparenting #cesiumContainer.
 * Never creates or destroys the viewer — just adopts the existing DOM element.
 */
export function CesiumSurfaceHost() {
  const containerRef = useRef<HTMLDivElement>(null);
  const adoptedRef = useRef(false);

  useEffect(() => {
    if (adoptedRef.current) return;

    const cesiumEl = document.getElementById('cesiumContainer');
    if (cesiumEl && containerRef.current) {
      containerRef.current.appendChild(cesiumEl);
      adoptedRef.current = true;

      // Trigger Cesium resize after reparenting
      const viewer = (window as any).viewer;
      if (viewer) {
        requestAnimationFrame(() => viewer.resize());
      }
    }

    return () => {
      // On unmount (HMR), return element to body so it survives
      if (adoptedRef.current) {
        const cesiumEl = document.getElementById('cesiumContainer');
        if (cesiumEl) {
          document.body.appendChild(cesiumEl);
          adoptedRef.current = false;
        }
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="cesium-surface-host"
      style={{ flex: 1, position: 'relative', overflow: 'hidden' }}
    />
  );
}
