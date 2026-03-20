import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';
import { ENEMY_MODE_STYLES } from '../shared/constants';

export function useCesiumEnemyUAVs(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const entitiesRef = useRef<Record<number, Cesium.Entity>>({});

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      const seen = new Set<number>();

      for (const e of state.enemyUavs) {
        seen.add(e.id);
        const pos = Cesium.Cartesian3.fromDegrees(e.lon, e.lat, 2500);
        const modeStyle = ENEMY_MODE_STYLES[e.mode] || ENEMY_MODE_STYLES['RECON'];
        const color = Cesium.Color.fromCssColorString(modeStyle.color);
        const labelText = `ENM-${e.id - 1000}`;

        if (!entitiesRef.current[e.id]) {
          entitiesRef.current[e.id] = viewer.entities.add({
            position: new Cesium.ConstantPositionProperty(pos),
            point: {
              pixelSize: 10,
              color: color,
              outlineColor: Cesium.Color.BLACK,
              outlineWidth: 1,
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
            label: {
              text: labelText,
              font: '11px monospace',
              fillColor: color,
              style: Cesium.LabelStyle.FILL_AND_OUTLINE,
              outlineWidth: 2,
              outlineColor: Cesium.Color.BLACK,
              verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
              pixelOffset: new Cesium.Cartesian2(0, -14),
              showBackground: true,
              backgroundColor: new Cesium.Color(0, 0, 0, 0.6),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
          });
        } else {
          const ent = entitiesRef.current[e.id];
          (ent.position as Cesium.ConstantPositionProperty).setValue(pos);
          if (ent.point) {
            ent.point.color = new Cesium.ConstantProperty(color);
          }
          if (ent.label) {
            ent.label.fillColor = new Cesium.ConstantProperty(color);
            ent.label.text = new Cesium.ConstantProperty(labelText);
          }
        }
      }

      // Remove stale entities
      for (const idStr of Object.keys(entitiesRef.current)) {
        const id = Number(idStr);
        if (!seen.has(id)) {
          viewer.entities.remove(entitiesRef.current[id]);
          delete entitiesRef.current[id];
        }
      }
    });

    return unsub;
  }, [viewerRef]);

  return { entitiesRef };
}
