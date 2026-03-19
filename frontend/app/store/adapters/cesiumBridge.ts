/**
 * Narrow imperative bridge between React/Zustand and the Cesium viewer.
 * All communication from React to Cesium goes through these methods.
 */

function getViewer(): any {
  return (window as any).viewer;
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

  /** Trigger viewer resize (after layout changes) */
  resize() {
    const viewer = getViewer();
    if (viewer) {
      viewer.resize();
    }
  },
};
