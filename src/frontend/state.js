// Shared application state passed between modules
export const state = {
    viewer: null,
    ws: null,
    selectedDroneId: null,
    selectedTargetId: null,
    trackedDroneEntity: null,
    macroTrackedId: null,
    isMacroTrackingReady: false,
    lastDronePosition: null,
    isSettingWaypoint: false,
    showAllWaypoints: false,
    gridVisState: 2,
    zonesPrimitive: null,
    zoneBordersPrimitive: null,
    droneWaypoints: {},
    droneCamVisible: false,
    theaterBounds: null,
};
