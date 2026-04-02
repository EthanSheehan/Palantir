import React, { useRef, useEffect, useCallback } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';

const DARK_TILE_URL = 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png';
const CONSTRAINT_RADIUS_METERS = 150000.0;

function getDronePin(statusColor: string): string {
  const svg = `<svg fill="none" height="78" width="70" viewBox="-15 -15 70 78" xmlns="http://www.w3.org/2000/svg"><rect x="-15" y="-15" width="70" height="78" fill="rgba(255,255,255,0.01)"/><rect x="6" y="6" width="28" height="28" stroke="#3b82f6" stroke-width="2"/><circle cx="20" cy="20" r="4" fill="#3b82f6"/><rect x="6" y="40" width="28" height="6" fill="${statusColor}"/></svg>`;
  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
}

export function DetailMapDialog() {
  const containerRef = useRef<HTMLDivElement>(null);
  const detailViewerRef = useRef<Cesium.Viewer | null>(null);
  const rangeConstraintRef = useRef<Cesium.Entity | null>(null);
  const droneMarkerRef = useRef<Cesium.Entity | null>(null);
  const activedroneIdRef = useRef<number | null>(null);
  const isOpenRef = useRef(false);

  const [open, setOpen] = React.useState(false);

  const selectedDroneId = useSimStore((s) => s.selectedDroneId);
  const uavs = useSimStore((s) => s.uavs);

  const initViewer = useCallback(() => {
    const container = containerRef.current;
    if (!container || detailViewerRef.current) return;

    const viewer = new Cesium.Viewer(container, {
      terrain: Cesium.Terrain.fromWorldTerrain(),
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      infoBox: false,
      navigationHelpButton: false,
      sceneModePicker: false,
      timeline: false,
      animation: false,
      fullscreenButton: false,
      selectionIndicator: false,
    });

    viewer.imageryLayers.removeAll();
    viewer.imageryLayers.addImageryProvider(
      new Cesium.UrlTemplateImageryProvider({ url: DARK_TILE_URL })
    );

    viewer.scene.globe.baseColor = Cesium.Color.BLACK;
    viewer.scene.backgroundColor = Cesium.Color.BLACK;
    viewer.scene.globe.enableLighting = true;
    if (viewer.scene.skyAtmosphere) {
      viewer.scene.skyAtmosphere.hueShift = -0.5;
      viewer.scene.skyAtmosphere.brightnessShift = -0.8;
    }
    viewer.scene.fog.enabled = true;
    viewer.scene.fog.density = 0.0001;

    // Lock camera controls
    viewer.scene.screenSpaceCameraController.enableRotate = false;
    viewer.scene.screenSpaceCameraController.enableTranslate = false;
    viewer.scene.screenSpaceCameraController.enableZoom = false;
    viewer.scene.screenSpaceCameraController.enableTilt = false;
    viewer.scene.screenSpaceCameraController.enableLook = false;

    viewer.clock.currentTime = Cesium.JulianDate.fromIso8601('2023-06-21T10:00:00Z');
    viewer.clock.shouldAnimate = false;

    const rangeConstraint = viewer.entities.add({
      name: 'Range Constraint',
      position: Cesium.Cartesian3.fromDegrees(0, 0),
      ellipse: {
        semiMajorAxis: CONSTRAINT_RADIUS_METERS,
        semiMinorAxis: CONSTRAINT_RADIUS_METERS,
        material: Cesium.Color.RED.withAlpha(0.15),
        outline: true,
        outlineColor: Cesium.Color.RED.withAlpha(0.6),
        outlineWidth: 2,
        height: 0,
      },
    });

    const droneMarker = viewer.entities.add({
      name: 'Detail Drone Marker',
      position: Cesium.Cartesian3.fromDegrees(0, 0),
      billboard: {
        image: getDronePin('#facc15'),
        scale: 0.8,
        verticalOrigin: Cesium.VerticalOrigin.CENTER,
      },
    });

    // Click handler for waypoint placement
    viewer.screenSpaceEventHandler.setInputAction(
      (movement: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
        if (activedroneIdRef.current == null) return;

        let cartesian: Cesium.Cartesian3 | undefined = viewer.scene.pickPosition(movement.position);
        if (!cartesian) {
          cartesian = viewer.camera.pickEllipsoid(movement.position, viewer.scene.globe.ellipsoid) ?? undefined;
        }
        if (!cartesian) return;

        const centerPos = rangeConstraintRef.current?.position?.getValue(Cesium.JulianDate.now());
        if (!centerPos) return;

        const distanceMeters = Cesium.Cartesian3.distance(centerPos, cartesian);

        if (distanceMeters <= CONSTRAINT_RADIUS_METERS) {
          const carto = Cesium.Cartographic.fromCartesian(cartesian);
          const lon = Cesium.Math.toDegrees(carto.longitude);
          const lat = Cesium.Math.toDegrees(carto.latitude);
          const droneId = activedroneIdRef.current;

          window.dispatchEvent(new CustomEvent('amc-grid:send', {
            detail: { action: 'move_drone', drone_id: droneId, target_lon: lon, target_lat: lat },
          }));
          window.dispatchEvent(new CustomEvent('amc-grid:placeWaypoint', {
            detail: { droneId, cartesian },
          }));

          activedroneIdRef.current = null;
          setOpen(false);
        } else {
          // Flash amber for out-of-range click
          const origMat = rangeConstraint.ellipse!.material;
          rangeConstraint.ellipse!.material = new Cesium.ColorMaterialProperty(
            Cesium.Color.fromCssColorString('#fbbf24').withAlpha(0.6)
          );
          setTimeout(() => {
            if (rangeConstraint.ellipse) rangeConstraint.ellipse.material = origMat;
          }, 150);
        }
      },
      Cesium.ScreenSpaceEventType.LEFT_CLICK
    );

    rangeConstraintRef.current = rangeConstraint;
    droneMarkerRef.current = droneMarker;
    detailViewerRef.current = viewer;
  }, []);

  // Listen for open events
  useEffect(() => {
    function onOpenDetailMap(e: Event) {
      const droneData = (e as CustomEvent).detail;
      if (!droneData) return;

      setOpen(true);
      activedroneIdRef.current = droneData.id;

      // We need to init the viewer after the dialog opens (after container is in DOM)
      requestAnimationFrame(() => {
        initViewer();

        const viewer = detailViewerRef.current;
        if (!viewer || viewer.isDestroyed()) return;
        const { lon, lat } = droneData;
        const dronePos = Cesium.Cartesian3.fromDegrees(lon, lat);
        if (rangeConstraintRef.current) rangeConstraintRef.current.position = new Cesium.ConstantPositionProperty(dronePos);
        if (droneMarkerRef.current) droneMarkerRef.current.position = new Cesium.ConstantPositionProperty(dronePos);
        viewer.resize();
        viewer.camera.setView({
          destination: Cesium.Cartesian3.fromDegrees(lon, lat, 400000.0),
          orientation: { heading: 0.0, pitch: Cesium.Math.toRadians(-90.0), roll: 0.0 },
        });
      });
    }

    window.addEventListener('amc-grid:openDetailMap', onOpenDetailMap);
    return () => window.removeEventListener('amc-grid:openDetailMap', onOpenDetailMap);
  }, [initViewer]);

  if (!open) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
      }}
    >
      <div
        style={{
          width: 600,
          height: 480,
          background: '#1c2127',
          border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: 6,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 12px',
            borderBottom: '1px solid rgba(255,255,255,0.1)',
          }}
        >
          <span style={{ fontFamily: 'monospace', fontSize: 12, color: '#e2e8f0' }}>
            DETAIL MAP — SET WAYPOINT
          </span>
          <button
            onClick={() => { setOpen(false); activedroneIdRef.current = null; }}
            style={{
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              fontSize: 16,
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
        <div ref={containerRef} style={{ flex: 1, position: 'relative' }} />
      </div>
    </div>
  );
}
