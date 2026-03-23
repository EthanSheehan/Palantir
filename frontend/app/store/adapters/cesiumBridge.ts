/**
 * Narrow imperative bridge between React/Zustand and the Cesium viewer.
 * All communication from React to Cesium goes through these methods.
 */
import { useAppStore } from '../appStore';

function getViewer(): any {
  return (window as any).viewer;
}

// Subscribe to historical state changes and update Cesium entity positions
let _historicalSubscribed = false;
function _ensureHistoricalSubscription() {
  if (_historicalSubscribed) return;
  _historicalSubscribed = true;

  useAppStore.subscribe(
    (s) => s.historicalState,
    (historicalState) => {
      const viewer = getViewer();
      if (!viewer) return;
      const Cesium = (window as any).Cesium;
      if (!Cesium) return;

      if (!historicalState.active) {
        // Exiting historical mode — restore live position properties
        const entities = viewer.entities.values;
        for (let i = 0; i < entities.length; i++) {
          const entity = entities[i];
          if (entity._livePositionProperty) {
            entity.position = entity._livePositionProperty;
            entity._livePositionProperty = undefined;
          }
        }
        viewer.scene.requestRender();
      }
    },
  );
}

function getMapToolController(): any {
  return (window as any).MapToolController;
}

export const cesiumBridge = {
  /** Highlight selected assets on the globe */
  setSelectedAssets(ids: string[]) {
    const AppState = (window as any).AppState;
    if (AppState) {
      if (ids.length <= 1) {
        AppState.select('asset', ids[0] ?? null);
      } else {
        AppState.selectMulti(ids);
      }
    }
  },

  /** Focus camera on a mission area */
  setMissionFocus(_id: string) {
    // Future: fly to mission's area of operations
  },

  /** Update the time cursor (for scrub rendering) */
  setTimeCursor(ms: number | null) {
    const AppState = (window as any).AppState;
    if (AppState) {
      AppState.setTimeCursor(ms);
    }
  },

  /** Switch the map interaction tool */
  setToolMode(mode: string) {
    const controller = getMapToolController();
    if (controller?.setTool) {
      controller.setTool(mode);
    }
  },

  /** Briefly flash/highlight an entity (e.g. from alert click) */
  flashAlertEntity(_id: string) {
    // Future: temporary highlight effect on the globe entity
  },

  /** Fly camera to an entity */
  flyToEntity(id: string) {
    const viewer = getViewer();
    if (!viewer) return;
    const entity = viewer.entities.getById('uav_' + id.replace('ast_', ''));
    if (entity) {
      viewer.flyTo(entity, { duration: 1.0 });
    }
  },

  /** Request a render frame (needed with requestRenderMode) */
  requestRender() {
    const viewer = getViewer();
    if (viewer?.scene) {
      viewer.scene.requestRender();
    }
  },

  /** Initialize historical mode subscription for Cesium */
  initHistoricalMode() {
    _ensureHistoricalSubscription();
  },

  /** Trigger viewer resize (after layout changes) */
  resize() {
    const viewer = getViewer();
    if (viewer) {
      viewer.resize();
    }
  },
};
