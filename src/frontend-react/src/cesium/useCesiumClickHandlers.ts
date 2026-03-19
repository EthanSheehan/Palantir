import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';

interface DroneEntity extends Cesium.Entity {
  _lastHeading?: number;
}

interface TargetEntity extends Cesium.Entity {
  _lockRing?: Cesium.Entity;
}

export function useCesiumClickHandlers(
  viewerRef: React.RefObject<Cesium.Viewer | null>,
  droneEntitiesRef: React.RefObject<Record<number, DroneEntity>>,
  targetEntitiesRef: React.RefObject<Record<number, TargetEntity>>
) {
  // Lazy-import sendMessage from context — we'll read it from a window-level store accessor instead
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    let mapClickTimer: ReturnType<typeof setTimeout> | null = null;

    function pickId(pickedObject: unknown): string | null {
      if (!Cesium.defined(pickedObject)) return null;
      const id = (pickedObject as any).id;
      if (!id) return null;
      if (typeof id === 'string') return id;
      if (id.id && typeof id.id === 'string') return id.id;
      return null;
    }

    function selectDrone(entity: Cesium.Entity, viewMode: 'macro' | 'thirdPerson') {
      const v = viewerRef.current;
      if (!v || v.isDestroyed()) return;

      const droneId = parseInt(entity.id.replace('uav_', ''));
      useSimStore.getState().setTrackedDrone(droneId);
      useSimStore.getState().selectDrone(droneId);
      useSimStore.getState().setDroneCamVisible(true);

      v.trackedEntity = undefined;
      if (v.camera.transform && !v.camera.transform.equals(Cesium.Matrix4.IDENTITY)) {
        v.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
      }

      if (viewMode === 'thirdPerson') {
        entity.viewFrom = undefined;
        v.flyTo(entity, {
          duration: 1.5,
          offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-15), 150),
        }).then((result) => {
          if (result && useSimStore.getState().trackedDroneId === droneId) {
            (entity as any).viewFrom = new Cesium.Cartesian3(0, -100, 30);
            v.trackedEntity = entity;
          }
        });
      } else {
        entity.viewFrom = undefined;
        const currentHeading = v.camera.heading;
        const currentPitch = Math.min(v.camera.pitch, Cesium.Math.toRadians(-20));

        v.flyTo(entity, {
          duration: 1.5,
          offset: new Cesium.HeadingPitchRange(currentHeading, currentPitch, 10000),
        });
        // Note: macro tracking is handled by useCesiumMacroTrack via store subscription
      }
    }

    // Single click handler
    viewer.screenSpaceEventHandler.setInputAction(
      (movement: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
        const v = viewerRef.current;
        if (!v || v.isDestroyed()) return;

        const store = useSimStore.getState();

        // Waypoint setting mode
        if (store.isSettingWaypoint && store.trackedDroneId != null) {
          let cartesian: Cesium.Cartesian3 | undefined = v.scene.pickPosition(movement.position);
          if (!cartesian) {
            cartesian = v.camera.pickEllipsoid(movement.position, v.scene.globe.ellipsoid) ?? undefined;
          }
          if (cartesian) {
            const carto = Cesium.Cartographic.fromCartesian(cartesian);
            const lon = Cesium.Math.toDegrees(carto.longitude);
            const lat = Cesium.Math.toDegrees(carto.latitude);
            const droneId = store.trackedDroneId;

            // Send via WebSocket context — dispatch custom event
            window.dispatchEvent(new CustomEvent('palantir:send', {
              detail: { action: 'move_drone', drone_id: droneId, target_lon: lon, target_lat: lat },
            }));

            // Place waypoint via event
            window.dispatchEvent(new CustomEvent('palantir:placeWaypoint', {
              detail: { droneId, cartesian },
            }));

            store.setIsSettingWaypoint(false);
          }
          return;
        }

        const pickedObjects = v.scene.drillPick(movement.position);
        for (let i = 0; i < pickedObjects.length; i++) {
          const id = pickId(pickedObjects[i]);
          if (!id) continue;

          if (id.startsWith('uav_')) {
            if (mapClickTimer) clearTimeout(mapClickTimer);
            mapClickTimer = setTimeout(() => {
              const entity = v.entities.getById(id);
              if (entity) selectDrone(entity, 'macro');
            }, 250);
            return;
          }

          if (id.startsWith('target_')) {
            const tId = parseInt(id.replace('target_', ''));
            useSimStore.getState().selectTarget(tId);
            return;
          }
        }
      },
      Cesium.ScreenSpaceEventType.LEFT_CLICK
    );

    // Double click handler
    viewer.screenSpaceEventHandler.setInputAction(
      (movement: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
        const v = viewerRef.current;
        if (!v || v.isDestroyed()) return;

        if (mapClickTimer) clearTimeout(mapClickTimer);

        const pickedObjects = v.scene.drillPick(movement.position);
        for (let i = 0; i < pickedObjects.length; i++) {
          const id = pickId(pickedObjects[i]);
          if (id && id.startsWith('uav_')) {
            const entity = v.entities.getById(id);
            if (entity) selectDrone(entity, 'thirdPerson');
            return;
          }
        }

        // No drone — spike if no tracked drone
        if (useSimStore.getState().trackedDroneId != null) return;

        let cartesian: Cesium.Cartesian3 | undefined = v.scene.pickPosition(movement.position);
        if (!cartesian) {
          cartesian = v.camera.pickEllipsoid(movement.position, v.scene.globe.ellipsoid) ?? undefined;
        }

        if (cartesian) {
          const carto = Cesium.Cartographic.fromCartesian(cartesian);
          const lon = Cesium.Math.toDegrees(carto.longitude);
          const lat = Cesium.Math.toDegrees(carto.latitude);

          window.dispatchEvent(new CustomEvent('palantir:send', {
            detail: { action: 'spike', lon, lat, radius: 0.5, magnitude: 20 },
          }));

          const entity = v.entities.add({
            position: cartesian,
            cylinder: {
              length: 10000.0,
              topRadius: 3000.0,
              bottomRadius: 3000.0,
              material: Cesium.Color.RED.withAlpha(0.3),
              outline: true,
              outlineColor: Cesium.Color.RED.withAlpha(0.6),
            },
          });
          v.scene.requestRender();
          setTimeout(() => {
            const vv = viewerRef.current;
            if (vv && !vv.isDestroyed()) {
              vv.entities.remove(entity);
              vv.scene.requestRender();
            }
          }, 500);
        }
      },
      Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK
    );

    return () => {
      if (mapClickTimer) clearTimeout(mapClickTimer);
    };
  }, [viewerRef, droneEntitiesRef, targetEntitiesRef]);
}
