import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';

export function useCesiumRangeRings(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const ringEntitiesRef = useRef<Record<number, Cesium.Entity[]>>({});
  const waypointEntitiesRef = useRef<Record<number, Cesium.Entity>>({});

  function toggleRangeRings(droneId: number) {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    if (ringEntitiesRef.current[droneId]) {
      ringEntitiesRef.current[droneId].forEach((entity) => viewer.entities.remove(entity));
      delete ringEntitiesRef.current[droneId];
      viewer.scene.requestRender();
      return;
    }

    ringEntitiesRef.current[droneId] = [];
    const numRings = 10;
    const maxRadius = 50000;
    const maxAlt = 2000;

    for (let i = 0; i < numRings; i++) {
      const t = i / (numRings - 1);
      const radius = Math.max(1, t * maxRadius);
      const height = (1 - t) * maxAlt;

      const ring = viewer.entities.add({
        position: new Cesium.CallbackProperty(() => {
          const v = viewerRef.current;
          if (!v || v.isDestroyed()) return null;

          let targetPos: Cesium.Cartesian3 | undefined;
          const waypointEntity = waypointEntitiesRef.current[droneId];
          if (waypointEntity && waypointEntity.position) {
            targetPos = waypointEntity.position.getValue(v.clock.currentTime) ?? undefined;
          }
          if (!targetPos) {
            const droneEntity = v.entities.getById(`uav_${droneId}`);
            if (droneEntity && droneEntity.position) {
              targetPos = droneEntity.position.getValue(v.clock.currentTime) ?? undefined;
            }
          }
          if (targetPos) {
            const carto = Cesium.Cartographic.fromCartesian(targetPos);
            return Cesium.Cartesian3.fromRadians(carto.longitude, carto.latitude, height);
          }
          return undefined;
        }, false) as unknown as Cesium.PositionProperty,
        ellipse: {
          semiMajorAxis: radius,
          semiMinorAxis: radius,
          height: height,
          fill: false,
          outline: true,
          outlineColor: Cesium.Color.fromCssColorString('#38bdf8').withAlpha(0.5 - 0.2 * t),
          outlineWidth: 2,
        },
      });
      ringEntitiesRef.current[droneId].push(ring);
    }
    viewer.scene.requestRender();
  }

  function removeRangeRings(droneId: number) {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    if (ringEntitiesRef.current[droneId]) {
      ringEntitiesRef.current[droneId].forEach((entity) => viewer.entities.remove(entity));
      delete ringEntitiesRef.current[droneId];
    }
  }

  // Register waypoint entity ref (called by useCesiumWaypoints)
  function registerWaypointEntity(droneId: number, entity: Cesium.Entity | null) {
    if (entity) {
      waypointEntitiesRef.current[droneId] = entity;
    } else {
      delete waypointEntitiesRef.current[droneId];
    }
  }

  useEffect(() => {
    return () => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;
      Object.values(ringEntitiesRef.current).forEach((rings) => {
        rings.forEach((entity) => viewer.entities.remove(entity));
      });
      ringEntitiesRef.current = {};
    };
  }, [viewerRef]);

  return { toggleRangeRings, removeRangeRings, registerWaypointEntity };
}
