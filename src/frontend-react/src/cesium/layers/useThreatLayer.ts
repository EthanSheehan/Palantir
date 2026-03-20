import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../../store/SimulationStore';
import { THREAT_RING_TYPES } from '../../shared/constants';

function threatColor(type: string): Cesium.Color {
  if (type === 'MANPADS') return Cesium.Color.fromCssColorString('rgba(236, 72, 153, 0.2)');
  // SAM and others
  return Cesium.Color.fromCssColorString('rgba(255, 68, 68, 0.2)');
}

export function useThreatLayer(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const primitiveRef = useRef<Cesium.Primitive | null>(null);
  const threatCountRef = useRef<number>(0);

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      const visible = state.layerVisibility['threat'] ?? false;

      if (!visible) {
        if (primitiveRef.current) {
          primitiveRef.current.show = false;
        }
        return;
      }

      if (primitiveRef.current) {
        primitiveRef.current.show = true;
      }

      const threatTargets = state.targets.filter(
        (t) => THREAT_RING_TYPES.has(t.type) && t.detected
      );
      const currentCount = threatTargets.length;

      if (primitiveRef.current && currentCount === threatCountRef.current) {
        return;
      }

      // Remove old primitive
      if (primitiveRef.current) {
        viewer.scene.primitives.remove(primitiveRef.current);
        primitiveRef.current = null;
      }

      if (threatTargets.length === 0) {
        threatCountRef.current = 0;
        return;
      }

      const instances: Cesium.GeometryInstance[] = threatTargets.map((target) => {
        const radius = (target.threat_range_km ?? 5) * 1000;
        const color = threatColor(target.type);

        return new Cesium.GeometryInstance({
          geometry: new Cesium.EllipseGeometry({
            center: Cesium.Cartesian3.fromDegrees(target.lon, target.lat),
            semiMajorAxis: radius,
            semiMinorAxis: radius,
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
      threatCountRef.current = currentCount;
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
