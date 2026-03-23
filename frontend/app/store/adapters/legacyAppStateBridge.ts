/**
 * Bidirectional bridge between legacy AppState (IIFE global) and Zustand store.
 *
 * Direction 1: AppState → Zustand — legacy code writes, React reads
 * Direction 2: Zustand → AppState — React writes, legacy code reads
 *
 * A semaphore flag prevents infinite echo loops.
 */
import { useAppStore } from '../appStore';
import type { Asset, Alert, Aimpoint, Target } from '../types';

let _bridgeUpdating = false;

/** Guard wrapper — skips the callback if the bridge is already mid-update */
function guarded(fn: () => void) {
  if (_bridgeUpdating) return;
  _bridgeUpdating = true;
  try {
    fn();
  } finally {
    _bridgeUpdating = false;
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getAppState(): any {
  return (window as any).AppState;
}

/**
 * Initialize the bridge. Called from main.tsx which is a deferred module script,
 * so all regular <script> tags (including state.js) have already executed.
 * window.AppState is guaranteed to exist at this point.
 */
export function initLegacyBridge(): () => void {
  const AppState = getAppState();
  if (!AppState) {
    console.error('[Bridge] AppState not found on window. Ensure state.js loads before main.tsx and sets window.AppState.');
    return () => {};
  }
  return _initBridge(AppState);
}

function _initBridge(AppState: any): () => void {

  const unsubs: Array<() => void> = [];
  const store = useAppStore;

  // ─── Direction 1: AppState → Zustand ───

  // Assets
  unsubs.push(AppState.subscribe('assets.updated', (asset: Asset) => {
    guarded(() => store.getState().updateAsset(asset));
  }));

  unsubs.push(AppState.subscribe('assets.telemetry', (asset: Asset) => {
    // Don't push live telemetry into the store when viewing historical state
    if (store.getState().historicalState.active) return;
    guarded(() => store.getState().updateAsset(asset));
  }));

  unsubs.push(AppState.subscribe('assets.snapshot', (assets: Asset[]) => {
    guarded(() => store.getState().setAssets(assets));
  }));

  // Selection
  unsubs.push(AppState.subscribe('selection.changed', (data: { type: string; id: string | null; ids: string[] }) => {
    guarded(() => {
      if (data.type === 'asset' || data.type === 'all') {
        store.getState().selectMultiAssets(data.ids || []);
      }
      if (data.type === 'mission') {
        store.getState().selectMission(data.id);
      }
      if (data.type === 'alert') {
        store.getState().selectAlert(data.id);
      }
    });
  }));

  // Time
  unsubs.push(AppState.subscribe('time.cursorChanged', (ms: number | null) => {
    guarded(() => store.getState().setTimeCursor(ms));
  }));

  unsubs.push(AppState.subscribe('time.modeChanged', (mode: string) => {
    guarded(() => {
      store.getState().setTimeMode(mode === 'live' ? 'live' : 'historical');
    });
  }));

  // Missions
  unsubs.push(AppState.subscribe('missions.updated', (mission: { id: string; [key: string]: unknown }) => {
    guarded(() => store.getState().updateMission(mission as any));
  }));

  // Alerts
  unsubs.push(AppState.subscribe('alerts.updated', (alert: Alert) => {
    guarded(() => store.getState().updateAlert(alert));
  }));

  // Reservations
  unsubs.push(AppState.subscribe('reservations.updated', (res: { id: string; [key: string]: unknown }) => {
    guarded(() => store.getState().updateReservation(res as any));
  }));

  // Recommendations
  unsubs.push(AppState.subscribe('recommendations.*', (rec: { id: string; [key: string]: unknown }) => {
    if (rec && rec.id) {
      guarded(() => store.getState().updateRecommendation(rec as any));
    }
  }));

  // Aimpoints
  unsubs.push(AppState.subscribe('aimpoints.snapshot', (aimpoints: Aimpoint[]) => {
    guarded(() => store.getState().setAimpoints(aimpoints));
  }));

  unsubs.push(AppState.subscribe('aimpoints.updated', (apt: Aimpoint) => {
    guarded(() => store.getState().updateAimpoint(apt));
  }));

  unsubs.push(AppState.subscribe('aimpoints.deleted', (id: string) => {
    guarded(() => store.getState().removeAimpoint(id));
  }));

  // Targets
  unsubs.push(AppState.subscribe('targets.snapshot', (targets: Target[]) => {
    guarded(() => store.getState().setTargets(targets));
  }));

  unsubs.push(AppState.subscribe('targets.updated', (tgt: Target) => {
    guarded(() => store.getState().updateTarget(tgt));
  }));

  unsubs.push(AppState.subscribe('targets.deleted', (id: string) => {
    guarded(() => store.getState().removeTarget(id));
  }));

  // Connection
  unsubs.push(AppState.subscribe('connection.changed', (val: boolean) => {
    guarded(() => {
      // Connection state is read-only in Zustand for now — could add if needed
      void val;
    });
  }));

  // ─── Direction 2: Zustand → AppState ───

  const zustandUnsub = store.subscribe((state, prevState) => {
    if (_bridgeUpdating) return;
    _bridgeUpdating = true;
    try {
      // Selection changes
      if (state.selection.assetIds !== prevState.selection.assetIds) {
        if (state.selection.assetIds.length <= 1) {
          AppState.select('asset', state.selection.primaryAssetId);
        } else {
          AppState.selectMulti(state.selection.assetIds);
        }
      }

      if (state.selection.missionId !== prevState.selection.missionId) {
        AppState.select('mission', state.selection.missionId);
      }

      if (state.selection.alertId !== prevState.selection.alertId) {
        AppState.select('alert', state.selection.alertId);
      }

      // Time cursor
      if (state.time.cursorMs !== prevState.time.cursorMs) {
        AppState.setTimeCursor(state.time.cursorMs);
      }
    } finally {
      _bridgeUpdating = false;
    }
  });

  console.log('[Bridge] Legacy AppState bridge initialized');

  // Return cleanup function
  return () => {
    unsubs.forEach((fn) => fn());
    zustandUnsub();
  };
}
