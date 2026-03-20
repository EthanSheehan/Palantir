import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';
import type { ThreatCluster } from '../store/types';

function clusterColor(clusterType: ThreatCluster['cluster_type']): Cesium.Color {
  switch (clusterType) {
    case 'SAM_BATTERY': return Cesium.Color.RED;
    case 'AD_NETWORK':  return Cesium.Color.ORANGE;
    case 'CONVOY':      return Cesium.Color.BLUE;
    case 'CP_COMPLEX':  return Cesium.Color.PURPLE;
    default:            return Cesium.Color.GRAY;
  }
}

export function useCesiumAssessment(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const entitiesRef = useRef<Cesium.Entity[]>([]);

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;
      const assessment = state.assessment;
      if (!assessment) return;

      // Remove all previous assessment entities
      entitiesRef.current.forEach(e => viewer.entities.remove(e));
      entitiesRef.current = [];

      // 1. Cluster hull polygons + centroid labels
      for (const cluster of assessment.clusters) {
        const color = clusterColor(cluster.cluster_type);

        if (cluster.hull_points.length >= 3) {
          const positions = Cesium.Cartesian3.fromDegreesArray(
            cluster.hull_points.flatMap(([lon, lat]) => [lon, lat])
          );
          const poly = viewer.entities.add({
            polygon: {
              hierarchy: new Cesium.PolygonHierarchy(positions),
              material: color.withAlpha(0.2),
              outline: true,
              outlineColor: color.withAlpha(0.8),
              height: 0,
            },
          });
          entitiesRef.current.push(poly);
        }

        const label = viewer.entities.add({
          position: Cesium.Cartesian3.fromDegrees(cluster.centroid_lon, cluster.centroid_lat),
          label: {
            text: `${cluster.cluster_type}\n${cluster.member_target_ids.length} targets`,
            font: '12px sans-serif',
            fillColor: Cesium.Color.WHITE,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 2,
            style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            verticalOrigin: Cesium.VerticalOrigin.CENTER,
            pixelOffset: new Cesium.Cartesian2(0, -20),
            scale: 0.8,
            showBackground: true,
            backgroundColor: Cesium.Color.BLACK.withAlpha(0.6),
          },
        });
        entitiesRef.current.push(label);
      }

      // 2. SAM engagement envelopes
      const samTargets = state.targets.filter(
        t => ['SAM', 'RADAR', 'MANPADS'].includes(t.type)
          && t.state !== 'UNDETECTED'
          && t.threat_range_km != null
      );
      for (const t of samTargets) {
        const radius = (t.threat_range_km ?? 0) * 1000;
        if (radius <= 0) continue;
        const ring = viewer.entities.add({
          position: Cesium.Cartesian3.fromDegrees(t.lon, t.lat),
          ellipse: {
            semiMajorAxis: radius,
            semiMinorAxis: radius,
            material: Cesium.Color.RED.withAlpha(0.1),
            outline: true,
            outlineColor: Cesium.Color.RED.withAlpha(0.6),
            outlineWidth: 1.5,
            height: 0,
          },
        });
        entitiesRef.current.push(ring);
      }

      // 3. Movement corridor polylines
      for (const corridor of assessment.movement_corridors) {
        if (corridor.waypoints.length < 2) continue;
        const positions = Cesium.Cartesian3.fromDegreesArrayHeights(
          corridor.waypoints.flatMap(([lon, lat]) => [lon, lat, 500])
        );
        const line = viewer.entities.add({
          polyline: {
            positions,
            width: 2,
            material: new Cesium.PolylineDashMaterialProperty({
              color: Cesium.Color.YELLOW.withAlpha(0.7),
              dashLength: 16,
            }),
            arcType: Cesium.ArcType.GEODESIC,
          },
        });
        entitiesRef.current.push(line);
      }

      viewer.scene.requestRender();
    });

    return () => {
      unsub();
      const viewer = viewerRef.current;
      if (viewer && !viewer.isDestroyed()) {
        entitiesRef.current.forEach(e => viewer.entities.remove(e));
      }
      entitiesRef.current = [];
    };
  }, [viewerRef]);
}
