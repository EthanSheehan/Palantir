import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';
import type { UAV, Target, SwarmTask } from '../store/types';

/** Stable key for a swarm assignment line: uavId->targetId */
function lineKey(uavId: number, targetId: number): string {
  return `${uavId}->${targetId}`;
}

/** Collect all active swarm line keys from current tasks. */
function activeLineKeys(tasks: SwarmTask[]): Set<string> {
  const keys = new Set<string>();
  for (const task of tasks) {
    for (const uavId of task.assigned_uav_ids) {
      keys.add(lineKey(uavId, task.target_id));
    }
  }
  return keys;
}

const DASH_MATERIAL = new Cesium.PolylineDashMaterialProperty({
  color: Cesium.Color.CYAN.withAlpha(0.7),
  gapColor: Cesium.Color.TRANSPARENT,
  dashLength: 16.0,
  dashPattern: 255,
});

export function useCesiumSwarmLines(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const entityMapRef = useRef<Map<string, Cesium.Entity>>(new Map());
  // Mutable position store read by CallbackProperty — avoids entity teardown
  const positionStoreRef = useRef<Map<string, { uavId: number; targetId: number }>>(new Map());

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      const { swarmTasks, uavs, targets } = state;
      const uavMap = new Map<number, UAV>(uavs.map(u => [u.id, u]));
      const targetMap = new Map<number, Target>(targets.map(t => [t.id, t]));

      const nextKeys = activeLineKeys(swarmTasks);

      // Remove stale lines
      for (const [key, entity] of entityMapRef.current) {
        if (!nextKeys.has(key)) {
          viewer.entities.remove(entity);
          entityMapRef.current.delete(key);
          positionStoreRef.current.delete(key);
        }
      }

      // Add or update lines
      for (const task of swarmTasks) {
        const target = targetMap.get(task.target_id);
        if (!target) continue;

        for (const uavId of task.assigned_uav_ids) {
          const uav = uavMap.get(uavId);
          if (!uav) continue;

          const key = lineKey(uavId, task.target_id);
          positionStoreRef.current.set(key, { uavId, targetId: task.target_id });

          if (entityMapRef.current.has(key)) continue; // entity exists, CallbackProperty handles updates

          const posStore = positionStoreRef.current;
          const entity = viewer.entities.add({
            polyline: {
              positions: new Cesium.CallbackProperty(() => {
                const info = posStore.get(key);
                if (!info) return [];
                const store = useSimStore.getState();
                const u = store.uavs.find(d => d.id === info.uavId);
                const t = store.targets.find(d => d.id === info.targetId);
                if (!u || !t) return [];
                return Cesium.Cartesian3.fromDegreesArrayHeights([
                  u.lon, u.lat, 2000,
                  t.lon, t.lat, 500,
                ]);
              }, false) as unknown as Cesium.PositionProperty,
              width: 2,
              material: DASH_MATERIAL,
              arcType: Cesium.ArcType.GEODESIC,
            },
          });
          entityMapRef.current.set(key, entity);
        }
      }

      viewer.scene.requestRender();
    });

    return () => {
      unsub();
      const viewer = viewerRef.current;
      if (viewer && !viewer.isDestroyed()) {
        entityMapRef.current.forEach((e) => viewer.entities.remove(e));
      }
      entityMapRef.current.clear();
      positionStoreRef.current.clear();
    };
  }, [viewerRef]);
}
