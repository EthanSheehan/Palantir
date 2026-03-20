import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../../store/SimulationStore';

function confidenceColor(c: number): Cesium.Color {
  if (c >= 0.9) return Cesium.Color.fromCssColorString('rgba(34, 197, 94, 0.3)');
  if (c >= 0.6) return Cesium.Color.fromCssColorString('rgba(234, 179, 8, 0.3)');
  if (c >= 0.3) return Cesium.Color.fromCssColorString('rgba(249, 115, 22, 0.3)');
  return Cesium.Color.fromCssColorString('rgba(239, 68, 68, 0.3)');
}

export function useFusionLayer(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const primitiveRef = useRef<Cesium.Primitive | null>(null);
  const targetCountRef = useRef<number>(0);

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      const visible = state.layerVisibility['fusion'] ?? false;

      if (!visible) {
        if (primitiveRef.current) {
          primitiveRef.current.show = false;
        }
        return;
      }

      if (primitiveRef.current) {
        primitiveRef.current.show = true;
      }

      const detectedTargets = state.targets.filter(
        (t) => t.sensor_count > 0 && t.detected
      );
      const currentCount = detectedTargets.length;

      if (primitiveRef.current && currentCount === targetCountRef.current) {
        return;
      }

      // Remove old primitive
      if (primitiveRef.current) {
        viewer.scene.primitives.remove(primitiveRef.current);
        primitiveRef.current = null;
      }

      if (detectedTargets.length === 0) {
        targetCountRef.current = 0;
        return;
      }

      const instances: Cesium.GeometryInstance[] = detectedTargets.map((target) => {
        const color = confidenceColor(target.fused_confidence);

        return new Cesium.GeometryInstance({
          geometry: new Cesium.EllipseGeometry({
            center: Cesium.Cartesian3.fromDegrees(target.lon, target.lat),
            semiMajorAxis: 2000,
            semiMinorAxis: 2000,
            height: 0,
          }),
          attributes: {
            color: Cesium.ColorGeometryInstanceAttribute.fromColor(color),
          },
        });
      });

      const prim = viewer.scene.primitives.add(
        new Cesium.GroundPrimitive({
          geometryInstances: instances,
          appearance: new Cesium.PerInstanceColorAppearance({ flat: true, translucent: true }),
          asynchronous: false,
        })
      ) as Cesium.Primitive;

      prim.show = true;
      primitiveRef.current = prim;
      targetCountRef.current = currentCount;
    });

    return () => {
      unsub();
      const viewer = viewerRef.current;
      if (viewer && !viewer.isDestroyed() && primitiveRef.current) {
        viewer.scene.primitives.remove(primitiveRef.current);
        primitiveRef.current = null;
      }
    };
  }, [viewerRef]);
}
