/// <reference types="vite/client" />

// Legacy globals from IIFE modules loaded via <script> tags
interface Window {
  Cesium: typeof import('cesium');
  AppState: any;
  ApiClient: any;
  WsClient: any;
  WorkspaceShell: any;
  MapToolController: any;
  TimelinePanel: any;
  InspectorPanel: any;
  MissionPanel: any;
  AlertsPanel: any;
  MacrogridPanel: any;
  Toolbar: any;
  LayoutPersistence: any;
  PaneRegistry: any;
  viewer: any;
}
