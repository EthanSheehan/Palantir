import { useEffect, useRef } from 'react';
import * as Cesium from 'cesium';
import { useSimStore } from '../store/SimulationStore';
import { Launcher } from '../store/types';

const launcherSvgCache: Record<string, string> = {};

function getLauncherPin(available: number, capacity: number): string {
  const ratio = capacity > 0 ? available / capacity : 0;
  const color = ratio > 0.5 ? '#22c55e' : ratio > 0 ? '#eab308' : '#6b7280';
  const cacheKey = `${available}_${capacity}`;
  if (launcherSvgCache[cacheKey]) return launcherSvgCache[cacheKey];
  const svg = `<svg width="36" height="44" viewBox="0 0 36 44" xmlns="http://www.w3.org/2000/svg">
    <polygon points="18,2 34,34 18,28 2,34" fill="${color}" stroke="#fff" stroke-width="1.5"/>
    <rect x="14" y="36" width="8" height="6" fill="${color}" stroke="#fff" stroke-width="1"/>
  </svg>`;
  const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  launcherSvgCache[cacheKey] = url;
  return url;
}

function dispatchLaunch(launcherName: string): void {
  window.dispatchEvent(
    new CustomEvent('amc-grid:send', {
      detail: { action: 'launch_drone', launcher_name: launcherName },
    })
  );
}

export function useCesiumLaunchers(viewerRef: React.RefObject<Cesium.Viewer | null>) {
  const entitiesRef = useRef<Record<string, Cesium.Entity>>({});
  const handlerRef = useRef<Cesium.ScreenSpaceEventHandler | null>(null);

  useEffect(() => {
    const unsub = useSimStore.subscribe((state) => {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;

      // Lazily create the click handler once the viewer is available
      if (!handlerRef.current) {
        const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
        handler.setInputAction((click: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
          const v = viewerRef.current;
          if (!v || v.isDestroyed()) return;
          const picked = v.scene.pick(click.position);
          if (picked && picked.id) {
            const entityId: string =
              typeof picked.id === 'string' ? picked.id : picked.id?.id ?? '';
            if (entityId.startsWith('launcher_')) {
              const launcherName = entityId.replace('launcher_', '');
              dispatchLaunch(launcherName);
            }
          }
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
        handlerRef.current = handler;
      }

      const launchers: Launcher[] = state.launchers;
      const currentNames = new Set<string>();

      launchers.forEach((launcher) => {
        currentNames.add(launcher.name);
        const position = Cesium.Cartesian3.fromDegrees(launcher.lon, launcher.lat, 0);
        const billboardImage = getLauncherPin(launcher.available, launcher.capacity);
        const labelText = `${launcher.name}\n${launcher.available}/${launcher.capacity}`;

        if (!entitiesRef.current[launcher.name]) {
          const entity = viewer.entities.add({
            id: `launcher_${launcher.name}`,
            name: launcher.name,
            position,
            billboard: {
              image: billboardImage,
              width: 36,
              height: 44,
              verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
              heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
            },
            label: {
              text: labelText,
              font: '11px Inter, monospace',
              fillColor: Cesium.Color.WHITE,
              outlineColor: Cesium.Color.BLACK,
              outlineWidth: 2,
              style: Cesium.LabelStyle.FILL_AND_OUTLINE,
              verticalOrigin: Cesium.VerticalOrigin.TOP,
              pixelOffset: new Cesium.Cartesian2(0, 4),
              heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
          });
          entitiesRef.current[launcher.name] = entity;
        } else {
          const entity = entitiesRef.current[launcher.name];
          (entity.position as Cesium.ConstantPositionProperty).setValue(position);
          if (entity.billboard) {
            entity.billboard.image = billboardImage;
          }
          if (entity.label) {
            entity.label.text = labelText;
          }
        }
      });

      // Remove stale launcher entities
      for (const name of Object.keys(entitiesRef.current)) {
        if (!currentNames.has(name)) {
          viewer.entities.remove(entitiesRef.current[name]);
          delete entitiesRef.current[name];
        }
      }
    });

    return () => {
      unsub();
      if (handlerRef.current) {
        handlerRef.current.destroy();
        handlerRef.current = null;
      }
      const viewer = viewerRef.current;
      if (viewer && !viewer.isDestroyed()) {
        for (const entity of Object.values(entitiesRef.current)) {
          viewer.entities.remove(entity);
        }
      }
      for (const key of Object.keys(entitiesRef.current)) {
        delete entitiesRef.current[key];
      }
    };
  }, [viewerRef]);
}
