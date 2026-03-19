import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';
import { TARGET_MAP, THREAT_RING_RADIUS, THREAT_RING_TYPES } from '../shared/constants';
import { Target } from '../store/types';

const targetSvgCache: Record<string, string> = {};

function getTargetIcon(target: Target): string {
  const config = TARGET_MAP[target.type] || { color: '#ffcc00', label: 'TGT' };
  const confidence = target.detection_confidence || (target.detected ? 1.0 : 0.3);
  const targetState = target.state || (target.detected ? 'DETECTED' : 'UNDETECTED');
  const isVisible = targetState !== 'UNDETECTED';
  const isNeutralized = targetState === 'NEUTRALIZED';
  const isConcealed = target.concealed === true;

  const color = isNeutralized ? '#4a5568' : isVisible ? config.color : 'rgba(255, 204, 0, 0.5)';
  const size = isVisible ? 32 : 20;
  const opacity = isConcealed ? 0.4 : confidence;

  const cacheKey = `${target.type}_${targetState}_${Math.round(confidence * 10)}_${isConcealed ? 'c' : 'v'}`;
  if (targetSvgCache[cacheKey]) return targetSvgCache[cacheKey];

  const crossLine = isNeutralized
    ? `<line x1="4" y1="4" x2="${size - 4}" y2="${size - 4}" stroke="#ef4444" stroke-width="2" opacity="0.7"/>
       <line x1="${size - 4}" y1="4" x2="4" y2="${size - 4}" stroke="#ef4444" stroke-width="2" opacity="0.7"/>`
    : '';

  const svg = `<svg width="${size}" height="${size + 14}" viewBox="0 0 ${size} ${size + 14}" xmlns="http://www.w3.org/2000/svg">
    <circle cx="${size / 2}" cy="${size / 2}" r="${size / 2 - 2}" stroke="${color}" stroke-width="2" fill="none" opacity="${opacity}" />
    <circle cx="${size / 2}" cy="${size / 2}" r="${size / 4}" fill="${color}" opacity="${opacity}" />
    ${crossLine}
    ${isVisible ? `<text x="${size / 2}" y="${size + 12}" fill="${color}" font-size="10" font-family="Inter" font-weight="bold" text-anchor="middle" opacity="${opacity}">${config.label}</text>` : ''}
  </svg>`;
  const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  targetSvgCache[cacheKey] = url;
  return url;
}

interface TargetEntity extends Cesium.Entity {
  _lastTargetTime?: Cesium.JulianDate;
}

export function useCesiumTargets(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const entitiesRef = useRef<Record<number, TargetEntity>>({});
  const threatRingRef = useRef<Record<number, Cesium.Entity>>({});
  const fusionRingRef = useRef<Record<number, Cesium.Entity>>({});

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      const targets = state.targets;
      const currentIds = new Set<number>();

      targets.forEach((t) => {
        currentIds.add(t.id);
        const position = Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 0);
        const confidence = t.detection_confidence || (t.detected ? 1.0 : 0.3);
        const targetState = t.state || (t.detected ? 'DETECTED' : 'UNDETECTED');
        const isConcealed = t.concealed === true;
        const billboardAlpha = isConcealed ? 0.35 : Math.max(0.3, confidence);

        if (!entitiesRef.current[t.id]) {
          const positionProperty = new Cesium.SampledPositionProperty();
          positionProperty.forwardExtrapolationType = Cesium.ExtrapolationType.HOLD;
          positionProperty.setInterpolationOptions({
            interpolationDegree: 2,
            interpolationAlgorithm: Cesium.HermitePolynomialApproximation,
          });
          positionProperty.addSample(viewer.clock.currentTime, position);

          const config = TARGET_MAP[t.type] || { color: '#ffcc00', label: 'TGT' };
          const labelColor = Cesium.Color.fromCssColorString(
            targetState === 'NEUTRALIZED' ? '#4a5568' : config.color
          );
          const marker = viewer.entities.add({
            id: `target_${t.id}`,
            name: `Target-${t.id}`,
            position: positionProperty,
            billboard: {
              image: getTargetIcon(t),
              verticalOrigin: Cesium.VerticalOrigin.CENTER,
              heightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
              color: Cesium.Color.WHITE.withAlpha(billboardAlpha),
            },
            label: {
              text: `${config.label} #${t.id}`,
              font: 'bold 12px monospace',
              fillColor: labelColor,
              outlineColor: Cesium.Color.BLACK,
              outlineWidth: 3,
              style: Cesium.LabelStyle.FILL_AND_OUTLINE,
              verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
              pixelOffset: new Cesium.Cartesian2(0, -36),
              showBackground: true,
              backgroundColor: Cesium.Color.BLACK.withAlpha(0.55),
              backgroundPadding: new Cesium.Cartesian2(5, 3),
              distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0.0, 1200000.0),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
          }) as TargetEntity;
          entitiesRef.current[t.id] = marker;
        } else {
          const marker = entitiesRef.current[t.id];
          let targetTime: Cesium.JulianDate;
          if (!marker._lastTargetTime) {
            targetTime = Cesium.JulianDate.addSeconds(viewer.clock.currentTime, 0.3, new Cesium.JulianDate());
          } else {
            targetTime = Cesium.JulianDate.addSeconds(marker._lastTargetTime, 0.1, new Cesium.JulianDate());
          }
          marker._lastTargetTime = targetTime;
          (marker.position as Cesium.SampledPositionProperty).addSample(targetTime, position);
          marker.billboard!.image = new Cesium.ConstantProperty(getTargetIcon(t));
          marker.billboard!.color = new Cesium.ConstantProperty(Cesium.Color.WHITE.withAlpha(billboardAlpha));
          const updConfig = TARGET_MAP[t.type] || { color: '#ffcc00', label: 'TGT' };
          const updLabelColor = Cesium.Color.fromCssColorString(
            targetState === 'NEUTRALIZED' ? '#4a5568' : updConfig.color
          );
          marker.label!.fillColor = new Cesium.ConstantProperty(updLabelColor);
        }

        // Threat rings for SAM/MANPADS
        if (THREAT_RING_TYPES.has(t.type) && targetState !== 'UNDETECTED' && targetState !== 'NEUTRALIZED') {
          if (!threatRingRef.current[t.id]) {
            const config = TARGET_MAP[t.type] || { color: '#ff4444' };
            const cesiumColor = Cesium.Color.fromCssColorString(config.color).withAlpha(0.3);
            const ring = viewer.entities.add({
              id: `threat_ring_${t.id}`,
              position: Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 0),
              ellipse: {
                semiMajorAxis: THREAT_RING_RADIUS,
                semiMinorAxis: THREAT_RING_RADIUS,
                fill: true,
                material: cesiumColor,
                outline: true,
                outlineColor: Cesium.Color.fromCssColorString(config.color).withAlpha(0.6),
                outlineWidth: 2,
                heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
              },
            });
            threatRingRef.current[t.id] = ring;
          } else {
            threatRingRef.current[t.id].position = Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 0) as any;
          }
        } else if (threatRingRef.current[t.id]) {
          viewer.entities.remove(threatRingRef.current[t.id]);
          delete threatRingRef.current[t.id];
        }

        // Fusion ring (cyan) — scales with sensor_count
        const sensorCount = t.sensor_count ?? 0;
        if (sensorCount > 0) {
          const fusionRadius = 1000 + sensorCount * 500;
          const fusionAlpha = Math.min(0.6, 0.2 * sensorCount);
          if (!fusionRingRef.current[t.id]) {
            const ring = viewer.entities.add({
              id: `fusion_ring_${t.id}`,
              position: Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 0),
              ellipse: {
                semiMajorAxis: fusionRadius,
                semiMinorAxis: fusionRadius,
                fill: true,
                material: Cesium.Color.CYAN.withAlpha(fusionAlpha),
                outline: true,
                outlineColor: Cesium.Color.CYAN.withAlpha(0.8),
                outlineWidth: 1,
                heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
              },
            });
            fusionRingRef.current[t.id] = ring;
          } else {
            fusionRingRef.current[t.id].position = Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 0) as any;
            fusionRingRef.current[t.id].ellipse!.semiMajorAxis = new Cesium.ConstantProperty(fusionRadius);
            fusionRingRef.current[t.id].ellipse!.semiMinorAxis = new Cesium.ConstantProperty(fusionRadius);
            fusionRingRef.current[t.id].ellipse!.material = new Cesium.ColorMaterialProperty(
              Cesium.Color.CYAN.withAlpha(fusionAlpha)
            );
          }
        } else if (fusionRingRef.current[t.id]) {
          viewer.entities.remove(fusionRingRef.current[t.id]);
          delete fusionRingRef.current[t.id];
        }
      });

      // Cleanup removed targets
      Object.keys(entitiesRef.current).forEach((idStr) => {
        const id = parseInt(idStr);
        if (!currentIds.has(id)) {
          viewer.entities.remove(entitiesRef.current[id]);
          delete entitiesRef.current[id];
          if (threatRingRef.current[id]) {
            viewer.entities.remove(threatRingRef.current[id]);
            delete threatRingRef.current[id];
          }
          if (fusionRingRef.current[id]) {
            viewer.entities.remove(fusionRingRef.current[id]);
            delete fusionRingRef.current[id];
          }
        }
      });
    });

    return unsub;
  }, [viewerRef]);

  return { entitiesRef };
}
