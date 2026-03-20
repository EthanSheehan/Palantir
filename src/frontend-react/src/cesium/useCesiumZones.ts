import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';

function getImbalanceColor(imbalance: number): Cesium.Color {
  const imb = Math.max(-20, Math.min(20, imbalance));
  if (imb < 0) {
    const intensity = Math.abs(imb) / 20.0;
    return Cesium.Color.fromCssColorString('rgba(239, 68, 68, 1.0)').withAlpha(0.2 + intensity * 0.4);
  } else if (imb > 0) {
    const intensity = imb / 20.0;
    return Cesium.Color.fromCssColorString('rgba(59, 130, 246, 1.0)').withAlpha(0.2 + intensity * 0.4);
  }
  return new Cesium.Color(0, 0, 0, 0.0);
}

export function useCesiumZones(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const primitiveRef = useRef<Cesium.GroundPrimitive | null>(null);
  const borderPrimitiveRef = useRef<Cesium.GroundPolylinePrimitive | null>(null);
  const attrsCacheRef = useRef<Record<string, any>>({});

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      const zones = state.zones;
      const gridVisState = state.gridVisState;
      if (zones.length === 0) return;

      if (!primitiveRef.current) {
        const fillInstances: Cesium.GeometryInstance[] = [];
        const borderInstances: Cesium.GeometryInstance[] = [];

        zones.forEach((z) => {
          const zoneId = `z_${z.x_idx}_${z.y_idx}`;
          const width = z.width || 0.192;
          const height = z.height || 0.094;
          const halfW = width / 2;
          const halfH = height / 2;

          const p1 = [z.lon - halfW, z.lat - halfH];
          const p2 = [z.lon + halfW, z.lat - halfH];
          const p3 = [z.lon + halfW, z.lat + halfH];
          const p4 = [z.lon - halfW, z.lat + halfH];

          const hierarchy = new Cesium.PolygonHierarchy(
            Cesium.Cartesian3.fromDegreesArray([...p1, ...p2, ...p3, ...p4])
          );

          const color = getImbalanceColor(z.imbalance);

          fillInstances.push(
            new Cesium.GeometryInstance({
              id: zoneId,
              geometry: new Cesium.PolygonGeometry({
                polygonHierarchy: hierarchy,
                height: 0,
                extrudedHeight: 0,
              }),
              attributes: {
                color: Cesium.ColorGeometryInstanceAttribute.fromColor(color),
              },
            })
          );

          const borderPositions = Cesium.Cartesian3.fromDegreesArray([
            ...p1, ...p2, ...p3, ...p4, ...p1,
          ]);

          borderInstances.push(
            new Cesium.GeometryInstance({
              geometry: new Cesium.GroundPolylineGeometry({
                positions: borderPositions,
                width: 1.0,
              }),
            })
          );
        });

        primitiveRef.current = viewer.scene.primitives.add(
          new Cesium.GroundPrimitive({
            geometryInstances: fillInstances,
            appearance: new Cesium.PerInstanceColorAppearance({ flat: true, translucent: true }),
            asynchronous: false,
          })
        ) as Cesium.GroundPrimitive;

        borderPrimitiveRef.current = viewer.scene.primitives.add(
          new Cesium.GroundPolylinePrimitive({
            geometryInstances: borderInstances,
            appearance: new Cesium.PolylineMaterialAppearance({
              material: Cesium.Material.fromType('Color', {
                color: new Cesium.Color(1.0, 1.0, 1.0, 0.15),
              }),
            }),
            asynchronous: true,
          })
        ) as Cesium.GroundPolylinePrimitive;
      } else {
        // Update existing primitive attributes via dirty-check
        zones.forEach((z) => {
          const zoneId = `z_${z.x_idx}_${z.y_idx}`;
          const color = getImbalanceColor(z.imbalance);

          let attrs = attrsCacheRef.current[zoneId];
          if (!attrs) {
            attrs = primitiveRef.current!.getGeometryInstanceAttributes(zoneId);
            attrsCacheRef.current[zoneId] = attrs;
            if (attrs) attrs._lastColor = null;
          }

          if (attrs) {
            const newColorStr = `${color.red},${color.green},${color.blue},${color.alpha}`;
            if (attrs._lastColor !== newColorStr) {
              attrs.color = [
                Math.round(color.red * 255),
                Math.round(color.green * 255),
                Math.round(color.blue * 255),
                Math.round(color.alpha * 255),
              ];
              attrs._lastColor = newColorStr;
            }
          }
        });
      }

      // Grid visibility (combined with layerVisibility gate)
      const zonesVisible = state.layerVisibility?.['zones'] ?? true;
      if (primitiveRef.current) {
        primitiveRef.current.show = gridVisState === 2 && zonesVisible;
      }
      if (borderPrimitiveRef.current) {
        borderPrimitiveRef.current.show = (gridVisState === 1 || gridVisState === 2) && zonesVisible;
      }
    });

    return () => {
      unsub();
      const viewer = viewerRef.current;
      if (viewer && !viewer.isDestroyed()) {
        if (primitiveRef.current) {
          viewer.scene.primitives.remove(primitiveRef.current);
          primitiveRef.current = null;
        }
        if (borderPrimitiveRef.current) {
          viewer.scene.primitives.remove(borderPrimitiveRef.current);
          borderPrimitiveRef.current = null;
        }
      }
      attrsCacheRef.current = {};
    };
  }, [viewerRef]);
}
