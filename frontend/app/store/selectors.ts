import { useAppStore } from './appStore';
import type { AppStore } from './appStore';

/** Selected primary asset object */
export const useSelectedAsset = () =>
  useAppStore((s: AppStore) => {
    const id = s.selection.primaryAssetId;
    return id ? s.assets[id] ?? null : null;
  });

/** All selected asset objects (ordered) */
export const useSelectedAssets = () =>
  useAppStore((s: AppStore) =>
    s.selection.assetIds
      .map((id) => s.assets[id])
      .filter((a): a is NonNullable<typeof a> => a != null)
  );

/** Selected mission object */
export const useSelectedMission = () =>
  useAppStore((s: AppStore) => {
    const id = s.selection.missionId;
    return id ? s.missions[id] ?? null : null;
  });

/** Selected alert object */
export const useSelectedAlert = () =>
  useAppStore((s: AppStore) => {
    const id = s.selection.alertId;
    return id ? s.alerts[id] ?? null : null;
  });

/** Assets as sorted array */
export const useAssetList = () =>
  useAppStore((s: AppStore) => Object.values(s.assets));

/** Missions as sorted array */
export const useMissionList = () =>
  useAppStore((s: AppStore) => Object.values(s.missions));

/** Alerts as array, sorted by severity */
export const useAlertList = () =>
  useAppStore((s: AppStore) => Object.values(s.alerts));

/** Whether we're in live mode */
export const useIsLive = () =>
  useAppStore((s: AppStore) => s.time.mode === 'live');

/** Current time cursor */
export const useTimeCursor = () =>
  useAppStore((s: AppStore) => s.time.cursorMs);

/** Aimpoints as array */
export const useAimpointList = () =>
  useAppStore((s: AppStore) => Object.values(s.aimpoints));

/** Targets as array */
export const useTargetList = () =>
  useAppStore((s: AppStore) => Object.values(s.targets));

/** Selected targets as objects */
export const useSelectedTargets = () =>
  useAppStore((s: AppStore) =>
    s.selection.selectedTargetIds
      .map((id) => s.targets[id])
      .filter((t): t is NonNullable<typeof t> => t != null)
  );
