import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';
import { MODE_STYLES } from '../shared/constants';
import { UAV } from '../store/types';

const svgCache: Record<string, string> = {};

function getDronePin(statusColor: string): string {
  if (svgCache[statusColor]) return svgCache[statusColor];
  const svg = `<svg fill="none" height="78" width="70" viewBox="-15 -15 70 78" xmlns="http://www.w3.org/2000/svg"><rect x="-15" y="-15" width="70" height="78" fill="rgba(255,255,255,0.01)"/><rect x="6" y="6" width="28" height="28" stroke="#3b82f6" stroke-width="2"/><circle cx="20" cy="20" r="4" fill="#3b82f6"/><rect x="6" y="40" width="28" height="6" fill="${statusColor}"/></svg>`;
  const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  svgCache[statusColor] = url;
  return url;
}

interface DroneEntity extends Cesium.Entity {
  _lastLon?: number;
  _lastLat?: number;
  _lastMode?: string;
  _lastHeading?: number;
  _lastTargetTime?: Cesium.JulianDate;
  _tether?: Cesium.Entity;
}

function updateDrones(uavs: UAV[], viewer: Cesium.Viewer, entities: Record<number, DroneEntity>) {
  const currentIds = new Set<number>();

  uavs.forEach((uav) => {
    currentIds.add(uav.id);
    const modeStyle = MODE_STYLES[uav.mode] || MODE_STYLES.IDLE;
    const colorStr = modeStyle.color;
    const color = Cesium.Color.fromCssColorString(colorStr);
    const billboardImage = getDronePin(colorStr);
    const altitude = uav.altitude_m || 1000;
    const position = Cesium.Cartesian3.fromDegrees(uav.lon, uav.lat, altitude);

    if (!entities[uav.id]) {
      const positionProperty = new Cesium.SampledPositionProperty();
      positionProperty.forwardExtrapolationType = Cesium.ExtrapolationType.HOLD;
      positionProperty.backwardExtrapolationType = Cesium.ExtrapolationType.HOLD;
      positionProperty.setInterpolationOptions({
        interpolationDegree: 2,
        interpolationAlgorithm: Cesium.HermitePolynomialApproximation,
      });
      positionProperty.addSample(viewer.clock.currentTime, position);

      const orientationProperty = new Cesium.SampledProperty(Cesium.Quaternion);
      orientationProperty.forwardExtrapolationType = Cesium.ExtrapolationType.HOLD;
      orientationProperty.backwardExtrapolationType = Cesium.ExtrapolationType.HOLD;
      orientationProperty.setInterpolationOptions({
        interpolationDegree: 2,
        interpolationAlgorithm: Cesium.HermitePolynomialApproximation,
      });
      const hpr = new Cesium.HeadingPitchRoll(0, 0, 0);
      orientationProperty.addSample(
        viewer.clock.currentTime,
        Cesium.Transforms.headingPitchRollQuaternion(position, hpr)
      );

      const modelColor = Cesium.Color.fromCssColorString('#888888');
      const marker = viewer.entities.add({
        id: `uav_${uav.id}`,
        name: `UAV-${uav.id}`,
        position: positionProperty,
        orientation: orientationProperty as any,
        point: {
          pixelSize: 6,
          color,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 1,
          heightReference: Cesium.HeightReference.NONE,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(800000.0, 50000000.0),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        billboard: {
          image: billboardImage,
          scale: 0.8,
          verticalOrigin: Cesium.VerticalOrigin.CENTER,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(2000.0, 800000.0),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        label: {
          text: `UAV-${uav.id}`,
          font: 'bold 13px monospace',
          fillColor: color,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 3,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          verticalOrigin: Cesium.VerticalOrigin.TOP,
          pixelOffset: new Cesium.Cartesian2(0, 14),
          showBackground: true,
          backgroundColor: Cesium.Color.BLACK.withAlpha(0.55),
          backgroundPadding: new Cesium.Cartesian2(5, 3),
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0.0, 1200000.0),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        model: {
          uri: 'Fixed V2.glb',
          minimumPixelSize: 100,
          maximumScale: 50.0,
          color: modelColor,
          colorBlendMode: Cesium.ColorBlendMode.MIX,
          colorBlendAmount: 0.5,
          shadows: Cesium.ShadowMode.DISABLED,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0.0, 20000.0),
        },
      }) as DroneEntity;

      const tether = viewer.entities.add({
        polyline: {
          positions: new Cesium.CallbackProperty((time) => {
            try {
              const currentPos = positionProperty.getValue(time);
              if (!currentPos) return [];
              const carto = Cesium.Cartographic.fromCartesian(currentPos);
              if (!carto) return [];
              const groundPos = Cesium.Cartesian3.fromRadians(carto.longitude, carto.latitude, 0);
              return [groundPos, currentPos];
            } catch {
              return [];
            }
          }, false),
          width: 1,
          material: color.withAlpha(0.3),
        },
      });
      marker._tether = tether;
      marker._lastLon = uav.lon;
      marker._lastLat = uav.lat;
      marker._lastMode = colorStr;
      entities[uav.id] = marker;
    } else {
      const marker = entities[uav.id];
      const now = viewer.clock.currentTime;
      const targetTime = Cesium.JulianDate.addSeconds(now, 0.15, new Cesium.JulianDate());
      marker._lastTargetTime = targetTime;
      (marker.position as Cesium.SampledPositionProperty).addSample(targetTime, position);

      const dx = uav.lon - (marker._lastLon || 0);
      const dy = uav.lat - (marker._lastLat || 0);
      const movementDist = Math.abs(dx) + Math.abs(dy);

      if (movementDist > 0.0005) {
        const latRad = Cesium.Math.toRadians(uav.lat);
        const dxScaled = dx * Math.cos(latRad);
        const mathAngle = Math.atan2(dy, dxScaled);
        let heading = Math.PI / 2 - mathAngle + Math.PI;

        if (marker._lastHeading === undefined) marker._lastHeading = heading;
        let hdiff = heading - marker._lastHeading;
        while (hdiff > Math.PI) hdiff -= Math.PI * 2;
        while (hdiff < -Math.PI) hdiff += Math.PI * 2;
        heading = marker._lastHeading + hdiff * 0.6;
        marker._lastHeading = heading;

        const hpr = new Cesium.HeadingPitchRoll(heading, 0.0, 0.0);
        const quat = Cesium.Transforms.headingPitchRollQuaternion(position, hpr);
        (marker.orientation as Cesium.SampledProperty).addSample(targetTime, quat);

        marker._lastLon = uav.lon;
        marker._lastLat = uav.lat;
      }

      if (uav.heading_deg !== undefined && movementDist <= 0.002) {
        const heading = Cesium.Math.toRadians(uav.heading_deg) + Math.PI;
        marker._lastHeading = heading;
        const hpr = new Cesium.HeadingPitchRoll(heading, 0.0, 0.0);
        const quat = Cesium.Transforms.headingPitchRollQuaternion(position, hpr);
        (marker.orientation as Cesium.SampledProperty).addSample(targetTime, quat);
      }

      if (marker._lastMode !== colorStr) {
        marker.billboard!.image = new Cesium.ConstantProperty(billboardImage);
        marker.point!.color = new Cesium.ConstantProperty(color);
        marker.label!.fillColor = new Cesium.ConstantProperty(color);
        if (marker._tether) {
          marker._tether.polyline!.material = new Cesium.ColorMaterialProperty(color.withAlpha(0.3));
        }
        marker._lastMode = colorStr;
      }
    }
  });

  // Remove stale entities
  Object.keys(entities).forEach((idStr) => {
    const id = parseInt(idStr);
    if (!currentIds.has(id)) {
      const marker = entities[id];
      if (marker._tether) viewer.entities.remove(marker._tether);
      viewer.entities.remove(marker);
      delete entities[id];
    }
  });
}

export function useCesiumDrones(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const entitiesRef = useRef<Record<number, DroneEntity>>({});

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;
      updateDrones(state.uavs, viewer, entitiesRef.current);
    });

    return unsub;
  }, [viewerRef]);

  return { entitiesRef };
}
