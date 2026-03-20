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
      const detectedEnemies = state.enemyUavs.filter(e => e.detected);

      for (const e of detectedEnemies) {
        seen.add(e.id);
        const pos = Cesium.Cartesian3.fromDegrees(e.lon, e.lat, 2500);
        const modeStyle = ENEMY_MODE_STYLES[e.mode] || ENEMY_MODE_STYLES['RECON'];
        const color = Cesium.Color.fromCssColorString(modeStyle.color);
        const labelText = `ENM-${e.id - 1000}`;

        if (!entitiesRef.current[e.id]) {
          // Create a colored triangle SVG as billboard for reliable picking
          const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
            <polygon points="12,2 22,20 2,20" fill="${modeStyle.color}" stroke="#000" stroke-width="1.5"/>
          </svg>`;
          const billboard = `data:image/svg+xml,${encodeURIComponent(svg)}`;

          entitiesRef.current[e.id] = viewer.entities.add({
            id: `enemy_uav_${e.id}`,
            position: new Cesium.ConstantPositionProperty(pos),
            billboard: {
              image: billboard,
              width: 20,
              height: 20,
              verticalOrigin: Cesium.VerticalOrigin.CENTER,
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
              pixelOffset: new Cesium.Cartesian2(0, -16),
              showBackground: true,
              backgroundColor: new Cesium.Color(0, 0, 0, 0.6),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
          });
        } else {
          const ent = entitiesRef.current[e.id];
          (ent.position as Cesium.ConstantPositionProperty).setValue(pos);
          if (ent.billboard) {
            const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
              <polygon points="12,2 22,20 2,20" fill="${modeStyle.color}" stroke="#000" stroke-width="1.5"/>
            </svg>`;
            ent.billboard.image = new Cesium.ConstantProperty(`data:image/svg+xml,${encodeURIComponent(svg)}`);
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
