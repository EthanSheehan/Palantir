import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';

interface DroneEntity extends Cesium.Entity {
  _lastHeading?: number;
}

export function useCesiumCompass(
  viewerRef: React.RefObject<Cesium.Viewer | null>,
  droneEntitiesRef: React.RefObject<Record<number, DroneEntity>>
) {
  const mousePositionRef = useRef<Cesium.Cartesian3 | null>(null);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    function getCompassCenter(): Cesium.Cartesian3 | null {
      const v = viewerRef.current;
      if (!v || v.isDestroyed()) return null;
      const trackedId = useSimStore.getState().trackedDroneId;
      if (trackedId != null) {
        const entity = v.entities.getById(`uav_${trackedId}`);
        if (entity && entity.position) {
          const pos = entity.position.getValue(v.clock.currentTime);
          if (pos) {
            const carto = Cesium.Cartographic.fromCartesian(pos);
            carto.height = 0;
            return Cesium.Cartographic.toCartesian(carto);
          }
        }
      }
      return mousePositionRef.current;
    }

    // Compass needle entity
    viewer.entities.add({
      id: 'compass_needle',
      polyline: {
        positions: new Cesium.CallbackProperty(() => {
          const center = getCompassCenter();
          if (!center) return [];

          const transform = Cesium.Transforms.eastNorthUpToFixedFrame(center);
          let fwd = new Cesium.Cartesian3(0.0, 2000.0, 0.0);

          const trackedId = useSimStore.getState().trackedDroneId;
          if (trackedId != null && droneEntitiesRef.current != null && droneEntitiesRef.current[trackedId]) {
            const droneEntity = droneEntitiesRef.current[trackedId];
            if (droneEntity._lastHeading !== undefined) {
              let heading = droneEntity._lastHeading;
              heading -= Math.PI;
              const rotMatrix = Cesium.Matrix3.fromRotationZ(-heading);
              Cesium.Matrix3.multiplyByVector(rotMatrix, fwd, fwd);
            }
          }

          const worldFwd = new Cesium.Cartesian3();
          Cesium.Matrix4.multiplyByPoint(transform, fwd, worldFwd);
          return [center, worldFwd];
        }, false),
        width: 3,
        material: Cesium.Color.fromCssColorString('#facc15'),
        clampToGround: true,
      },
    });

    // Compass ring entity
    viewer.entities.add({
      id: 'compass_ring',
      polyline: {
        positions: new Cesium.CallbackProperty(() => {
          const center = getCompassCenter();
          if (!center) return [];

          const radius = 1500.0;
          const segments = 64;
          const transform = Cesium.Transforms.eastNorthUpToFixedFrame(center);
          const pts: Cesium.Cartesian3[] = [];
          const local = new Cesium.Cartesian3();
          for (let i = 0; i <= segments; i++) {
            const angle = (i / segments) * Math.PI * 2;
            local.x = Math.cos(angle) * radius;
            local.y = Math.sin(angle) * radius;
            local.z = 0;
            pts.push(Cesium.Matrix4.multiplyByPoint(transform, local, new Cesium.Cartesian3()));
          }
          return pts;
        }, false),
        width: 3,
        material: Cesium.Color.fromCssColorString('#facc15').withAlpha(0.6),
        clampToGround: true,
      },
    });

    // Mouse tracking for compass center when no drone tracked
    viewer.screenSpaceEventHandler.setInputAction(
      (movement: Cesium.ScreenSpaceEventHandler.MotionEvent) => {
        const trackedId = useSimStore.getState().trackedDroneId;
        if (trackedId != null) return;
        let cartesian: Cesium.Cartesian3 | undefined = viewer.scene.pickPosition(movement.endPosition);
        if (!cartesian) {
          cartesian = viewer.camera.pickEllipsoid(
            movement.endPosition,
            viewer.scene.globe.ellipsoid
          ) ?? undefined;
        }
        if (cartesian) {
          mousePositionRef.current = cartesian;
          viewer.scene.requestRender();
        }
      },
      Cesium.ScreenSpaceEventType.MOUSE_MOVE
    );

    return () => {
      const v = viewerRef.current;
      if (!v || v.isDestroyed()) return;
      const needle = v.entities.getById('compass_needle');
      const ring = v.entities.getById('compass_ring');
      if (needle) v.entities.remove(needle);
      if (ring) v.entities.remove(ring);
      // Note: screenSpaceEventHandler.setInputAction returns void, handler removed on viewer destroy
    };
  }, [viewerRef, droneEntitiesRef]);
}
