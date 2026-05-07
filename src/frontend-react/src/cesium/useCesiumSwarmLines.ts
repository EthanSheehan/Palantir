import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';
import type { UAV, Target, SwarmTask, SwarmExplanation } from '../store/types';

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

/** Build the InfoBox HTML for a swarm assignment from its cost-matrix
 * attribution. Beyond-Maven differentiator: Maven shows the assignment;
 * we show why this UAV won and who came second.
 */
function buildExplanationHtml(
  uavId: number,
  targetId: number,
  explanation: SwarmExplanation | null | undefined,
): string {
  if (!explanation) {
    return `<div style="font-family:ui-monospace,monospace;font-size:11px;color:#cbd5e1">
      <div style="font-weight:700;color:#22d3ee;letter-spacing:0.1em;margin-bottom:6px">SWARM ASSIGNMENT</div>
      <div>UAV ${uavId} → Target #${String(targetId).padStart(4, '0')}</div>
      <div style="opacity:0.7;margin-top:6px">No cost-matrix data available — likely a forced assignment.</div>
    </div>`;
  }
  const winnerLabel = explanation.uav_id === uavId ? 'WINNER' : 'AUXILIARY';
  const altRows = (explanation.alternatives || [])
    .map(
      a => `<tr>
        <td style="padding:2px 8px;color:#94a3b8">UAV ${a.uav_id}</td>
        <td style="padding:2px 8px;color:#cbd5e1;font-family:ui-monospace,monospace">${a.cost.toFixed(3)}</td>
      </tr>`,
    )
    .join('');
  return `<div style="font-family:ui-monospace,monospace;font-size:11px;color:#cbd5e1;line-height:1.5">
    <div style="font-weight:700;color:#22d3ee;letter-spacing:0.1em;margin-bottom:6px">SWARM ASSIGNMENT</div>
    <div><span style="color:#64748b">target:</span> #${String(targetId).padStart(4, '0')}</div>
    <div><span style="color:#64748b">winning UAV:</span> ${explanation.uav_id} (${winnerLabel})</div>
    <div><span style="color:#64748b">winning cost:</span> <span style="color:#22c55e">${explanation.winning_cost.toFixed(3)}</span></div>
    <div><span style="color:#64748b">sensor type:</span> ${explanation.sensor_type}</div>
    ${altRows ? `
      <div style="margin-top:8px;font-weight:700;color:#fbbf24;letter-spacing:0.08em">ALTERNATIVES (lost)</div>
      <table style="border-collapse:collapse;margin-top:4px">${altRows}</table>` : ''}
  </div>`;
}

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

          if (entityMapRef.current.has(key)) {
            // Refresh InfoBox content in case explanation changed this tick
            const existing = entityMapRef.current.get(key);
            if (existing) {
              existing.description = new Cesium.ConstantProperty(
                buildExplanationHtml(uavId, task.target_id, task.explanation),
              );
            }
            continue;
          }

          const posStore = positionStoreRef.current;
          const entity = viewer.entities.add({
            name: `Swarm UAV-${uavId} → TGT-${String(task.target_id).padStart(4, '0')}`,
            description: buildExplanationHtml(uavId, task.target_id, task.explanation),
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
