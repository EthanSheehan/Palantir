import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import type {
  Asset, Mission, Alert, TimelineReservation, Command,
  Recommendation, LayoutState,
} from './types';

// ── Layout Persistence ──
const LAYOUT_STORAGE_KEY = 'ams.workspace.layout';
const LAYOUT_SAVE_DEBOUNCE = 500;
let _layoutSaveTimer: ReturnType<typeof setTimeout> | null = null;

function loadPersistedLayout(): Partial<LayoutState> {
  try {
    const raw = localStorage.getItem(LAYOUT_STORAGE_KEY);
    if (!raw) return {};
    const saved = JSON.parse(raw);
    if (saved.version !== 1 || !saved.regions) return {};
    const r = saved.regions;
    return {
      leftWidth: Math.max(240, Math.min(800, r.left?.width ?? 380)),
      leftCollapsed: r.left?.collapsed ?? false,
      rightWidth: Math.max(240, Math.min(600, r.right?.width ?? 340)),
      rightVisible: r.right?.visible ?? false,
      timelineExpanded: r.bottom?.timelineExpanded ?? false,
      timelineHeight: r.bottom?.timelineHeight ?? 25,
    };
  } catch {
    return {};
  }
}

function saveLayout(layout: LayoutState, activeTab: string) {
  if (_layoutSaveTimer) clearTimeout(_layoutSaveTimer);
  _layoutSaveTimer = setTimeout(() => {
    try {
      localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify({
        version: 1,
        regions: {
          left: { width: layout.leftWidth, collapsed: layout.leftCollapsed, activeTab },
          right: { width: layout.rightWidth, visible: layout.rightVisible },
          bottom: { timelineExpanded: layout.timelineExpanded, timelineHeight: layout.timelineHeight },
        },
      }));
    } catch { /* quota exceeded etc */ }
  }, LAYOUT_SAVE_DEBOUNCE);
}

const persistedLayout = loadPersistedLayout();

export type LeftPanelTab = 'missions' | 'targets' | 'assets' | 'inspector' | 'alerts' | 'macrogrid' | 'commands';
// Note: 'targets' tab exists in the HTML but isn't in the original blueprint spec.
// Preserved for backwards compatibility with existing tab content.

export interface AppStore {
  // ── UI ──
  ui: {
    leftPanelTab: LeftPanelTab;
    inspectorOpen: boolean;
    timelineOpen: boolean;
    layout: LayoutState;
    theme: 'dark';
  };

  // ── Selection ──
  selection: {
    primaryAssetId: string | null;
    assetIds: string[];
    missionId: string | null;
    alertId: string | null;
    hoveredEntityId: string | null;
    selectedTargetIds: (number | string)[];
  };

  // ── Time ──
  time: {
    mode: 'live' | 'historical';
    cursorMs: number | null;
    viewStartMs: number | null;
    viewEndMs: number | null;
  };

  // ── Domain Data ──
  assets: Record<string, Asset>;
  missions: Record<string, Mission>;
  alerts: Record<string, Alert>;
  reservations: Record<string, TimelineReservation>;
  recommendations: Record<string, Recommendation>;
  commands: Record<string, Command>;

  // ── Pinned Target (for cross-panel sort anchor) ──
  pinnedTarget: { id: number | string; name: string; description?: string; lon: number; lat: number; aimpoints?: Array<{ id: number; lon: number; lat: number; type: string; description: string }> } | null;

  // ── Tool Mode ──
  toolMode: {
    mode: string | null;
    armed: boolean;
  };

  // ── Filters ──
  filters: {
    assetTypes: string[];
    severities: string[];
    missionStates: string[];
  };

  // ── Actions ──
  selectAsset: (id: string | null) => void;
  selectMultiAssets: (ids: string[]) => void;
  selectMission: (id: string | null) => void;
  selectAlert: (id: string | null) => void;
  setHoveredEntity: (id: string | null) => void;
  selectTarget: (id: number | string | null, additive?: boolean) => void;
  setTimeCursor: (ms: number | null) => void;
  setTimeMode: (mode: 'live' | 'historical') => void;
  setLeftPanelTab: (tab: LeftPanelTab) => void;
  setInspectorOpen: (open: boolean) => void;
  setTimelineOpen: (open: boolean) => void;
  setToolMode: (mode: string | null, armed?: boolean) => void;
  updateAsset: (asset: Asset) => void;
  updateMission: (mission: Mission) => void;
  updateAlert: (alert: Alert) => void;
  updateReservation: (res: TimelineReservation) => void;
  updateRecommendation: (rec: Recommendation) => void;
  updateCommand: (cmd: Command) => void;
  setAssets: (assets: Asset[]) => void;
  setLayout: (layout: Partial<LayoutState>) => void;
  setFilters: (filters: Partial<AppStore['filters']>) => void;
  setPinnedTarget: (target: AppStore['pinnedTarget']) => void;
}

export const useAppStore = create<AppStore>()(subscribeWithSelector((set) => ({
  // ── Initial State (with persisted layout) ──
  ui: {
    leftPanelTab: 'missions' as LeftPanelTab,
    inspectorOpen: false,
    timelineOpen: false,
    layout: {
      leftWidth: persistedLayout.leftWidth ?? 380,
      leftCollapsed: persistedLayout.leftCollapsed ?? false,
      rightWidth: persistedLayout.rightWidth ?? 340,
      rightVisible: persistedLayout.rightVisible ?? false,
      timelineExpanded: persistedLayout.timelineExpanded ?? false,
      timelineHeight: persistedLayout.timelineHeight ?? 25,
    },
    theme: 'dark' as const,
  },

  selection: {
    primaryAssetId: null,
    assetIds: [],
    missionId: null,
    alertId: null,
    hoveredEntityId: null,
    selectedTargetIds: [],
  },

  time: {
    mode: 'live',
    cursorMs: null,
    viewStartMs: null,
    viewEndMs: null,
  },

  assets: {},
  missions: {},
  alerts: {},
  reservations: {},
  recommendations: {},
  commands: {},

  toolMode: {
    mode: null,
    armed: false,
  },

  filters: {
    assetTypes: [],
    severities: [],
    missionStates: [],
  },

  // ── Actions ──
  selectAsset: (id) => set((state) => ({
    selection: {
      ...state.selection,
      primaryAssetId: id,
      assetIds: id ? [id] : [],
    },
  })),

  selectMultiAssets: (ids) => set((state) => ({
    selection: {
      ...state.selection,
      primaryAssetId: ids.length > 0 ? ids[0]! : null,
      assetIds: ids,
    },
  })),

  selectMission: (id) => set((state) => ({
    selection: { ...state.selection, missionId: id },
  })),

  selectAlert: (id) => set((state) => ({
    selection: { ...state.selection, alertId: id },
  })),

  setHoveredEntity: (id) => set((state) => ({
    selection: { ...state.selection, hoveredEntityId: id },
  })),

  selectTarget: (id, additive = false) => set((state) => {
    if (id === null) return { selection: { ...state.selection, selectedTargetIds: [] } };
    const current = state.selection.selectedTargetIds;
    if (additive) {
      const idx = current.indexOf(id);
      const next = idx >= 0 ? current.filter((t) => t !== id) : [...current, id];
      return { selection: { ...state.selection, selectedTargetIds: next } };
    }
    // Single select: toggle if already sole selection
    const next = current.length === 1 && current[0] === id ? [] : [id];
    return { selection: { ...state.selection, selectedTargetIds: next } };
  }),

  setTimeCursor: (ms) => set((state) => ({
    time: {
      ...state.time,
      cursorMs: ms,
      mode: ms === null ? 'live' : 'historical',
    },
  })),

  setTimeMode: (mode) => set((state) => ({
    time: { ...state.time, mode },
  })),

  setLeftPanelTab: (tab) => set((state) => ({
    ui: { ...state.ui, leftPanelTab: tab },
  })),

  setInspectorOpen: (open) => set((state) => ({
    ui: { ...state.ui, inspectorOpen: open },
  })),

  setTimelineOpen: (open) => set((state) => ({
    ui: { ...state.ui, timelineOpen: open },
  })),

  setToolMode: (mode, armed = false) => set(() => ({
    toolMode: { mode, armed },
  })),

  updateAsset: (asset) => set((state) => ({
    assets: { ...state.assets, [asset.id]: asset },
  })),

  updateMission: (mission) => set((state) => ({
    missions: { ...state.missions, [mission.id]: mission },
  })),

  updateAlert: (alert) => set((state) => ({
    alerts: { ...state.alerts, [alert.id]: alert },
  })),

  updateReservation: (res) => set((state) => ({
    reservations: { ...state.reservations, [res.id]: res },
  })),

  updateRecommendation: (rec) => set((state) => ({
    recommendations: { ...state.recommendations, [rec.id]: rec },
  })),

  updateCommand: (cmd) => set((state) => ({
    commands: { ...state.commands, [cmd.id]: cmd },
  })),

  setAssets: (assets) => set(() => {
    const map: Record<string, Asset> = {};
    for (const a of assets) {
      map[a.id] = a;
    }
    return { assets: map };
  }),

  setLayout: (layout) => set((state) => ({
    ui: {
      ...state.ui,
      layout: { ...state.ui.layout, ...layout },
    },
  })),

  setFilters: (filters) => set((state) => ({
    filters: { ...state.filters, ...filters },
  })),

  pinnedTarget: null,

  setPinnedTarget: (target) => set({ pinnedTarget: target }),
})));

// ── Auto-save layout to localStorage on change ──
useAppStore.subscribe(
  (s) => ({ layout: s.ui.layout, tab: s.ui.leftPanelTab }),
  ({ layout, tab }) => saveLayout(layout, tab),
  { equalityFn: (a, b) => a.layout === b.layout && a.tab === b.tab },
);
