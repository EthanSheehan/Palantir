import { create } from 'zustand';
import { UAV, Target, Zone, FlowLine, StrikeEntry, COA, TheaterInfo, AssistantMessage, HitlUpdate, EnemyUAV, SwarmTask } from './types';
import { MAX_ASSISTANT_MESSAGES } from '../shared/constants';

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

  // Cached COAs per entry_id
  cachedCoas: Record<string, COA[]>;

  // Enemy UAVs
  enemyUavs: EnemyUAV[];

  // Swarm tasks
  swarmTasks: SwarmTask[];

  // Autonomy state
  autonomyLevel: 'MANUAL' | 'SUPERVISED' | 'AUTONOMOUS';
  pendingTransitions: Record<number, { mode: string; reason: string; expires_at: number }>;

  // UI state
  selectedDroneId: number | null;
  selectedTargetId: number | null;
  selectedEnemyUavId: number | null;
  trackedDroneId: number | null;
  activeTab: string;
  gridVisState: 0 | 1 | 2;
  showAllWaypoints: boolean;
  droneCamVisible: boolean;
  isSettingWaypoint: boolean;

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
  }) => void;
  setConnected: (connected: boolean) => void;
  addAssistantMessage: (msg: AssistantMessage) => void;
  setCachedCoas: (entryId: string, coas: COA[]) => void;
  selectDrone: (id: number | null) => void;
  selectTarget: (id: number | null) => void;
  selectEnemyUav: (id: number | null) => void;
  setActiveTab: (tab: string) => void;
  setTrackedDrone: (id: number | null) => void;
  cycleGridVis: () => void;
  toggleAllWaypoints: () => void;
  setDroneCamVisible: (visible: boolean) => void;
  setIsSettingWaypoint: (setting: boolean) => void;
  setAutonomyLevel: (level: 'MANUAL' | 'SUPERVISED' | 'AUTONOMOUS') => void;
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
  cachedCoas: {},
  selectedDroneId: null,
  selectedTargetId: null,
  selectedEnemyUavId: null,
  trackedDroneId: null,
  activeTab: 'mission',
  gridVisState: 2,
  showAllWaypoints: false,
  droneCamVisible: false,
  isSettingWaypoint: false,
  enemyUavs: [],
  swarmTasks: [],
  autonomyLevel: 'MANUAL',
  pendingTransitions: {},

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
    });

    if (data.autonomy_level) {
      set({ autonomyLevel: data.autonomy_level });
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

  setCachedCoas: (entryId, coas) => set((state) => ({
    cachedCoas: { ...state.cachedCoas, [entryId]: coas },
  })),

  selectDrone: (id) => set({ selectedDroneId: id }),
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
}));
