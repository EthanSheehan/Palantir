import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';

interface WaypointRecord {
  waypoint: Cesium.Entity;
  trajectory: Cesium.Entity;
}

export function useCesiumWaypoints(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const waypointEntitiesRef = useRef<Record<number, WaypointRecord>>({});

  function placeWaypoint(droneId: number, cartesian: Cesium.Cartesian3) {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    const existing = waypointEntitiesRef.current[droneId];
    if (existing) {
      existing.waypoint.position = new Cesium.ConstantPositionProperty(cartesian);
      return;
    }

    const waypointEntity = viewer.entities.add({
      position: cartesian,
      cylinder: {
        length: 2000.0,
        topRadius: 20.0,
        bottomRadius: 20.0,
        material: Cesium.Color.fromCssColorString('#22c55e').withAlpha(0.6),
        outline: true,
        outlineColor: Cesium.Color.fromCssColorString('#22c55e'),
      },
    });

    const trajectoryEntity = viewer.entities.add({
      polyline: {
        positions: new Cesium.CallbackProperty(() => {
          const v = viewerRef.current;
          if (!v || v.isDestroyed()) return [];
          const droneEntity = v.entities.getById(`uav_${droneId}`);
          if (!droneEntity || !droneEntity.position) return [];
          const start = droneEntity.position.getValue(v.clock.currentTime);
          const end = waypointEntity.position?.getValue(v.clock.currentTime);
          if (start && end) return [start, end];
          return [];
        }, false),
        width: 2,
        material: new Cesium.PolylineDashMaterialProperty({
          color: Cesium.Color.fromCssColorString('#22c55e'),
          dashLength: 20.0,
        }),
        clampToGround: true,
      },
    });

    waypointEntitiesRef.current[droneId] = { waypoint: waypointEntity, trajectory: trajectoryEntity };
    _updateWaypointVisibility();
  }

  function removeWaypoint(droneId: number) {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    const rec = waypointEntitiesRef.current[droneId];
    if (rec) {
      viewer.entities.remove(rec.waypoint);
      viewer.entities.remove(rec.trajectory);
      delete waypointEntitiesRef.current[droneId];
    }
  }

  function _updateWaypointVisibility() {
    const { trackedDroneId, showAllWaypoints } = useSimStore.getState();
    Object.entries(waypointEntitiesRef.current).forEach(([idStr, rec]) => {
      const id = parseInt(idStr);
      const visible = showAllWaypoints || id === trackedDroneId;
      rec.waypoint.show = visible;
      rec.trajectory.show = visible;
    });
  }

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const { trackedDroneId, showAllWaypoints, uavs } = state;

      // Remove waypoints for drones that have left repositioning mode
      uavs.forEach((u) => {
        if (u.mode !== 'REPOSITIONING' && waypointEntitiesRef.current[u.id]) {
          removeWaypoint(u.id);
        }
      });

      // Update visibility
      Object.entries(waypointEntitiesRef.current).forEach(([idStr, rec]) => {
        const id = parseInt(idStr);
        const visible = showAllWaypoints || id === trackedDroneId;
        rec.waypoint.show = visible;
        rec.trajectory.show = visible;
      });
    });

    // Listen for place-waypoint events from click handler
    function onPlaceWaypoint(e: Event) {
      const { droneId, cartesian } = (e as CustomEvent).detail;
      if (droneId != null && cartesian) {
        placeWaypoint(droneId, cartesian);
      }
    }
    window.addEventListener('grid-sentinel:placeWaypoint', onPlaceWaypoint);

    return () => {
      unsub();
      window.removeEventListener('grid-sentinel:placeWaypoint', onPlaceWaypoint);
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;
      Object.values(waypointEntitiesRef.current).forEach(({ waypoint, trajectory }) => {
        viewer.entities.remove(waypoint);
        viewer.entities.remove(trajectory);
      });
      waypointEntitiesRef.current = {};
    };
  }, [viewerRef]);

  return { placeWaypoint, removeWaypoint, waypointEntitiesRef };
}
