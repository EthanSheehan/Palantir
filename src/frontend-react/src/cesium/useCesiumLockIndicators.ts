import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';

interface TargetEntity extends Cesium.Entity {
  _lockRing?: Cesium.Entity;
}

export function useCesiumLockIndicators(
  viewerRef: React.RefObject<Cesium.Viewer | null>,
  targetEntitiesRef: React.RefObject<Record<number, TargetEntity>>
) {
  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      const { uavs } = state;

      const targetEntities = targetEntitiesRef.current;
      if (!targetEntities) return;

      uavs.forEach((uav) => {
        if (uav.mode === 'PAINT' && uav.tracked_target_id != null) {
          const targetEntity = targetEntities[uav.tracked_target_id] as TargetEntity | undefined;
          if (targetEntity && !targetEntity._lockRing) {
            targetEntity._lockRing = viewer.entities.add({
              position: targetEntity.position as Cesium.PositionProperty,
              ellipse: {
                semiMajorAxis: 500,
                semiMinorAxis: 500,
                height: 50,
                fill: false,
                outline: true,
                outlineColor: Cesium.Color.RED.withAlpha(0.8),
                outlineWidth: 3,
              },
            });
          }
        } else if (uav.mode !== 'PAINT' && uav.tracked_target_id != null) {
          const targetEntity = targetEntities[uav.tracked_target_id] as TargetEntity | undefined;
          if (targetEntity && targetEntity._lockRing) {
            viewer.entities.remove(targetEntity._lockRing);
            targetEntity._lockRing = undefined;
          }
        }
      });
    });

    return unsub;
  }, [viewerRef, targetEntitiesRef]);
}
