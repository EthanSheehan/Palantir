import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';

export function useCesiumMacroTrack(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const macroReadyRef = useRef(false);
  const lastDronePositionRef = useRef<Cesium.Cartesian3 | null>(null);
  const macroTrackedIdRef = useRef<number | null>(null);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    // Subscribe to store to track macroTrackedId changes
    const unsub = useSimStore.subscribe((state) => {
      const newId = state.trackedDroneId;
      if (newId !== macroTrackedIdRef.current) {
        macroTrackedIdRef.current = newId;
        macroReadyRef.current = false;
        lastDronePositionRef.current = null;
      }
    });

    function preUpdateListener(_scene: Cesium.Scene, time: Cesium.JulianDate) {
      const v = viewerRef.current;
      if (!v || v.isDestroyed()) return;

      const trackedId = macroTrackedIdRef.current;
      if (trackedId == null || v.trackedEntity) {
        lastDronePositionRef.current = null;
        return;
      }

      const entity = v.entities.getById(`uav_${trackedId}`);
      if (!entity || !entity.position) {
        lastDronePositionRef.current = null;
        return;
      }

      const pos = entity.position.getValue(time);
      if (!pos) {
        lastDronePositionRef.current = null;
        return;
      }

      if (!macroReadyRef.current) {
        // First frame after tracking starts — just record position, do not jump
        lastDronePositionRef.current = pos.clone();
        macroReadyRef.current = true;
        return;
      }

      if (lastDronePositionRef.current) {
        v.camera.position.x += pos.x - lastDronePositionRef.current.x;
        v.camera.position.y += pos.y - lastDronePositionRef.current.y;
        v.camera.position.z += pos.z - lastDronePositionRef.current.z;
      }
      lastDronePositionRef.current = pos.clone();
    }

    viewer.scene.preUpdate.addEventListener(preUpdateListener);

    return () => {
      unsub();
      const v = viewerRef.current;
      if (!v || v.isDestroyed()) return;
      v.scene.preUpdate.removeEventListener(preUpdateListener);
    };
  }, [viewerRef]);

  // Expose a way to signal macro tracking is ready after flyTo completes
  return { macroReadyRef };
}
