import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../../store/SimulationStore';
import { SENSOR_RANGE_KM } from '../../shared/constants';

function sensorColor(sensor: string): Cesium.Color {
  if (sensor === 'SAR') return Cesium.Color.fromCssColorString('rgba(234, 179, 8, 0.15)');
  if (sensor === 'SIGINT') return Cesium.Color.fromCssColorString('rgba(168, 85, 247, 0.15)');
  // EO_IR and default
  return Cesium.Color.fromCssColorString('rgba(6, 182, 212, 0.15)');
}

export function useCoverageLayer(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const primitiveRef = useRef<Cesium.Primitive | null>(null);
  const countRef = useRef<number>(0);

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      const visible = state.layerVisibility['coverage'] ?? false;

      if (!visible) {
        if (primitiveRef.current) {
          primitiveRef.current.show = false;
        }
        return;
      }

      if (primitiveRef.current) {
        primitiveRef.current.show = true;
      }

      const uavs = state.uavs;
      const currentCount = uavs.length;

      if (primitiveRef.current && currentCount === countRef.current) {
        // No rebuild needed — just ensure show is true
        return;
      }

      // Remove old primitive
      if (primitiveRef.current) {
        viewer.scene.primitives.remove(primitiveRef.current);
        primitiveRef.current = null;
      }

      if (uavs.length === 0) {
        countRef.current = 0;
        return;
      }

      const instances: Cesium.GeometryInstance[] = uavs.map((uav) => {
        const firstSensor = uav.sensors?.[0] ?? uav.sensor_type ?? '';
        const color = sensorColor(firstSensor);

        return new Cesium.GeometryInstance({
          geometry: new Cesium.EllipseGeometry({
            center: Cesium.Cartesian3.fromDegrees(uav.lon, uav.lat),
            semiMajorAxis: SENSOR_RANGE_KM * 1000,
            semiMinorAxis: SENSOR_RANGE_KM * 1000,
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
      countRef.current = currentCount;
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
