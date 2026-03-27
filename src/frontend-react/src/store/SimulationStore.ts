import { create } from 'zustand';
import { UAV, Target, Zone, FlowLine, StrikeEntry, COA, TheaterInfo, AssistantMessage, HitlUpdate, EnemyUAV, SwarmTask, IntelEvent, CommandEvent, AssessmentPayload, ISRRequirement, MapMode, MAP_MODE_DEFAULTS, CamLayout, WorkspaceMode } from './types';
import { MAX_ASSISTANT_MESSAGES, MAX_INTEL_EVENTS, MAX_COMMAND_EVENTS } from '../shared/constants';

interface SimState {
  // Simulation data (from WS)
  uavs: UAV[];
  targets: Target[];
  zones: Zone[];
  flows: FlowLine[];
  strikeBoard: StrikeEntry[];
  theater: TheaterInfo | null;
  demoMode: boolean;
  connected: boolean;

  // Assistant messages
  assistantMessages: AssistantMessage[];

  // Feed slices
  intelEvents: IntelEvent[];
  commandEvents: CommandEvent[];

  // Cached COAs per entry_id
  cachedCoas: Record<string, COA[]>;

  // Enemy UAVs
  enemyUavs: EnemyUAV[];

  // Swarm tasks
  swarmTasks: SwarmTask[];

  // Autonomy state
  autonomyLevel: 'MANUAL' | 'SUPERVISED' | 'AUTONOMOUS';
  pendingTransitions: Record<number, { mode: string; reason: string; expires_at: number }>;

  // Assessment data
  assessment: AssessmentPayload | null;

  // Ops alerts
  opsAlerts: any[];

  // Planned targets
  plannedTargets: any[];

  // ISR state
  isrQueue: ISRRequirement[];
  coverageMode: 'balanced' | 'threat_adaptive';

  // Map mode state
  mapMode: MapMode;
  layerVisibility: Record<string, boolean>;

  // Drone cam layout
  camLayout: CamLayout;

  // UI state
  selectedDroneId: number | null;
  selectedDroneIds: number[];
  selectedTargetId: number | null;
  selectedEnemyUavId: number | null;
  trackedDroneId: number | null;
  activeTab: string;
  gridVisState: 0 | 1 | 2;
  showAllWaypoints: boolean;
  droneCamVisible: boolean;
  isSettingWaypoint: boolean;
  rangeRingDroneIds: number[];
  workspaceMode: WorkspaceMode;

  // Actions
  setSimData: (data: {
    uavs: UAV[];
    targets: Target[];
    zones: Zone[];
    flows: FlowLine[];
    strike_board: StrikeEntry[];
    theater: TheaterInfo | null;
    demo_mode: boolean;
    autonomy_level?: 'MANUAL' | 'SUPERVISED' | 'AUTONOMOUS';
    sitrep_response?: string;
    hitl_update?: HitlUpdate | string;
    enemy_uavs?: EnemyUAV[];
    swarm_tasks?: SwarmTask[];
    assessment?: AssessmentPayload;
    isr_queue?: ISRRequirement[];
    coverage_mode?: 'balanced' | 'threat_adaptive';
    ops_alerts?: any[];
    planned_targets?: any[];
  }) => void;
  setConnected: (connected: boolean) => void;
  addAssistantMessage: (msg: AssistantMessage) => void;
  addIntelEvent: (e: IntelEvent) => void;
  addCommandEvent: (e: CommandEvent) => void;
  setIntelEvents: (events: IntelEvent[]) => void;
  setCommandEvents: (events: CommandEvent[]) => void;
  setCachedCoas: (entryId: string, coas: COA[]) => void;
  selectDrone: (id: number | null) => void;
  selectDroneAdditive: (id: number) => void;
  selectTarget: (id: number | null) => void;
  selectEnemyUav: (id: number | null) => void;
  setActiveTab: (tab: string) => void;
  setTrackedDrone: (id: number | null) => void;
  cycleGridVis: () => void;
  toggleAllWaypoints: () => void;
  setDroneCamVisible: (visible: boolean) => void;
  setIsSettingWaypoint: (setting: boolean) => void;
  setAutonomyLevel: (level: 'MANUAL' | 'SUPERVISED' | 'AUTONOMOUS') => void;
  setMapMode: (mode: MapMode) => void;
  toggleLayer: (layer: string) => void;
  setCamLayout: (layout: CamLayout) => void;
  setCoverageMode: (mode: string) => void;
  toggleRangeRing: (droneId: number) => void;
  setWorkspaceMode: (mode: WorkspaceMode) => void;
}

export const useSimStore = create<SimState>((set, get) => ({
  uavs: [],
  targets: [],
  zones: [],
  flows: [],
  strikeBoard: [],
  theater: null,
  demoMode: false,
  connected: false,
  assistantMessages: [],
  intelEvents: [],
  commandEvents: [],
  cachedCoas: {},
  selectedDroneId: null,
  selectedDroneIds: [],
  selectedTargetId: null,
  selectedEnemyUavId: null,
  trackedDroneId: null,
  activeTab: 'mission',
  gridVisState: 2,
  showAllWaypoints: false,
  droneCamVisible: false,
  isSettingWaypoint: false,
  rangeRingDroneIds: [],
  workspaceMode: 'isr' as WorkspaceMode,
  enemyUavs: [],
  swarmTasks: [],
  autonomyLevel: 'MANUAL',
  pendingTransitions: {},
  assessment: null,
  opsAlerts: [],
  plannedTargets: [],
  isrQueue: [],
  coverageMode: 'balanced',
  mapMode: 'OPERATIONAL' as MapMode,
  layerVisibility: { ...MAP_MODE_DEFAULTS['OPERATIONAL'] },
  camLayout: 'SINGLE' as CamLayout,

  setSimData: (data) => {
    const newMessages: AssistantMessage[] = [...get().assistantMessages];

    if (data.sitrep_response) {
      newMessages.push({
        timestamp: new Date().toISOString(),
        text: data.sitrep_response,
        severity: 'INFO',
      });
    }

    if (data.hitl_update) {
      const update = data.hitl_update;
      if (typeof update === 'string') {
        newMessages.push({
          timestamp: new Date().toISOString(),
          text: update,
          severity: 'INFO',
        });
      } else {
        newMessages.push({
          timestamp: new Date().toISOString(),
          text: update.text,
          severity: (update.severity as AssistantMessage['severity']) || 'INFO',
        });
        if (update.coas && update.entry_id) {
          get().setCachedCoas(update.entry_id, update.coas);
        }
      }
    }

    const trimmed = newMessages.slice(-MAX_ASSISTANT_MESSAGES);

    set({
      uavs: data.uavs,
      targets: data.targets,
      zones: data.zones,
      flows: data.flows,
      strikeBoard: data.strike_board,
      theater: data.theater,
      demoMode: data.demo_mode,
      assistantMessages: trimmed,
      enemyUavs: data.enemy_uavs || [],
      swarmTasks: data.swarm_tasks || [],
      opsAlerts: data.ops_alerts || [],
      plannedTargets: data.planned_targets || [],
    });

    if (data.autonomy_level) {
      set({ autonomyLevel: data.autonomy_level });
    }

    if (data.assessment) {
      set({ assessment: data.assessment });
    }

    if (data.isr_queue) {
      set({ isrQueue: data.isr_queue });
    }

    if (data.coverage_mode) {
      set({ coverageMode: data.coverage_mode as 'balanced' | 'threat_adaptive' });
    }

    const pending: Record<number, { mode: string; reason: string; expires_at: number }> = {};
    for (const uav of data.uavs) {
      if (uav.pending_transition) {
        pending[uav.id] = uav.pending_transition;
      }
    }
    set({ pendingTransitions: pending });
  },

  setConnected: (connected) => set({ connected }),

  addAssistantMessage: (msg) => set((state) => ({
    assistantMessages: [...state.assistantMessages, msg].slice(-MAX_ASSISTANT_MESSAGES),
  })),

  addIntelEvent: (e) => set((state) => ({
    intelEvents: [...state.intelEvents, e].slice(-MAX_INTEL_EVENTS),
  })),

  addCommandEvent: (e) => set((state) => ({
    commandEvents: [...state.commandEvents, e].slice(-MAX_COMMAND_EVENTS),
  })),

  setIntelEvents: (events) => set({ intelEvents: events.slice(-MAX_INTEL_EVENTS) }),

  setCommandEvents: (events) => set({ commandEvents: events.slice(-MAX_COMMAND_EVENTS) }),

  setCachedCoas: (entryId, coas) => set((state) => ({
    cachedCoas: { ...state.cachedCoas, [entryId]: coas },
  })),

  selectDrone: (id) => set({ selectedDroneId: id, selectedDroneIds: id !== null ? [id] : [] }),
  selectDroneAdditive: (id) => set((state) => ({
    selectedDroneIds: state.selectedDroneIds.includes(id)
      ? state.selectedDroneIds.filter(d => d !== id)
      : [...state.selectedDroneIds, id],
    selectedDroneId: id,
  })),
  setActiveTab: (tab) => set({ activeTab: tab }),

  selectTarget: (id) => set({ selectedTargetId: id }),

  selectEnemyUav: (id) => set({ selectedEnemyUavId: id }),

  setTrackedDrone: (id) => set({ trackedDroneId: id }),

  cycleGridVis: () => set((state) => ({
    gridVisState: ((state.gridVisState + 1) % 3) as 0 | 1 | 2,
  })),

  toggleAllWaypoints: () => set((state) => ({
    showAllWaypoints: !state.showAllWaypoints,
  })),

  setDroneCamVisible: (visible) => set({ droneCamVisible: visible }),

  setIsSettingWaypoint: (setting) => set({ isSettingWaypoint: setting }),

  setAutonomyLevel: (level) => set({ autonomyLevel: level }),

  setMapMode: (mode) => set({ mapMode: mode, layerVisibility: { ...MAP_MODE_DEFAULTS[mode] } }),

  toggleLayer: (layer) => set((state) => ({
    layerVisibility: { ...state.layerVisibility, [layer]: !state.layerVisibility[layer] },
  })),

  setCamLayout: (layout) => set({ camLayout: layout }),

  setCoverageMode: (mode) => set({ coverageMode: mode as 'balanced' | 'threat_adaptive' }),

  toggleRangeRing: (droneId) => set((state) => ({
    rangeRingDroneIds: state.rangeRingDroneIds.includes(droneId)
      ? state.rangeRingDroneIds.filter(id => id !== droneId)
      : [...state.rangeRingDroneIds, droneId],
  })),

  setWorkspaceMode: (mode) => set({ workspaceMode: mode }),
}));

// Layout persistence — save UI state to localStorage
const LAYOUT_KEY = 'palantir_layout';

function loadPersistedLayout(): Partial<SimState> {
  try {
    const raw = localStorage.getItem(LAYOUT_KEY);
    if (!raw) return {};
    const data = JSON.parse(raw);
    return {
      mapMode: data.mapMode || 'OPERATIONAL',
      camLayout: data.camLayout || 'SINGLE',
      workspaceMode: data.workspaceMode || 'isr',
      gridVisState: data.gridVisState ?? 2,
    };
  } catch {
    return {};
  }
}

const persisted = loadPersistedLayout();
if (Object.keys(persisted).length > 0) {
  useSimStore.setState(persisted);
}

useSimStore.subscribe((state) => {
  try {
    localStorage.setItem(LAYOUT_KEY, JSON.stringify({
      mapMode: state.mapMode,
      camLayout: state.camLayout,
      workspaceMode: state.workspaceMode,
      gridVisState: state.gridVisState,
    }));
  } catch { /* ignore quota errors */ }
});
