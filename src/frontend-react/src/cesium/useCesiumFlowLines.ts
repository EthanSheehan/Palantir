import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';

export function useCesiumFlowLines(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const entitiesRef = useRef<Cesium.Entity[]>([]);

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      const flows = state.flows;

      // Remove all existing flow entities
      entitiesRef.current.forEach((e) => viewer.entities.remove(e));
      entitiesRef.current = [];

      // Add new flow lines
      flows.forEach((flow) => {
        const line = viewer.entities.add({
          polyline: {
            positions: Cesium.Cartesian3.fromDegreesArrayHeights([
              flow.source[0], flow.source[1], 2000,
              flow.target[0], flow.target[1], 2000,
            ]),
            width: 3,
            material: new Cesium.PolylineGlowMaterialProperty({
              glowPower: 0.2,
              color: Cesium.Color.CYAN,
            }),
            arcType: Cesium.ArcType.GEODESIC,
          },
        });
        entitiesRef.current.push(line);
      });

      viewer.scene.requestRender();
    });

    return () => {
      unsub();
      const viewer = viewerRef.current;
      if (viewer && !viewer.isDestroyed()) {
        entitiesRef.current.forEach((e) => viewer.entities.remove(e));
      }
      entitiesRef.current = [];
    };
  }, [viewerRef]);
}
