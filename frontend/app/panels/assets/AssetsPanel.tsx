import { useCallback, useState } from 'react';
import { Tag, Intent, SegmentedControl } from '@blueprintjs/core';
import { useAppStore } from '../../store/appStore';
import { useAssetList } from '../../store/selectors';
import type { Asset } from '../../store/types';
import './AssetsPanel.css';

const FILTERS = [
  { label: 'All', value: 'all' },
  { label: 'Idle', value: 'idle' },
  { label: 'Serving', value: 'serving' },
  { label: 'Reposn.', value: 'repositioning' },
];

/**
 * Trigger the same selection behavior as clicking a drone on the globe.
 * Uses MapToolController's exposed _triggerDroneSelection / _triggerDroneSelectionAdditive
 * which handle camera fly-to, halo, compass, and AppState sync.
 */
function selectOnGlobe(assetId: string, additive: boolean) {
  const viewer = (window as any).viewer;
  const controller = (window as any).MapToolController;
  if (!viewer || !controller) return;

  const entity = viewer.entities.getById(assetId);
  if (!entity) return;

  if (additive) {
    controller._triggerDroneSelectionAdditive(entity);
  } else {
    controller._triggerDroneSelection(entity, 'macro');
  }
}

export function AssetsPanel() {
  const assets = useAssetList();
  const primaryId = useAppStore((s) => s.selection.primaryAssetId);
  const selectedIds = useAppStore((s) => s.selection.assetIds);
  const [filter, setFilter] = useState('all');

  const filtered = filter === 'all'
    ? assets
    : assets.filter((a) => a.mode === filter);

  const handleClick = useCallback((assetId: string, shiftKey: boolean) => {
    // Delegate to MapToolController — same behavior as clicking on the globe
    selectOnGlobe(assetId, shiftKey);
  }, []);

  return (
    <div className="assets-panel">
      <div className="assets-filters">
        <SegmentedControl
          options={FILTERS}
          value={filter}
          onValueChange={(v) => setFilter(v as string)}
          small
        />
      </div>

      <div className="assets-list">
        {filtered.length === 0 && (
          <div className="empty-state">No assets match filter</div>
        )}
        {filtered.map((asset) => {
          const isPrimary = asset.id === primaryId;
          const isSecondary = !isPrimary && selectedIds.includes(asset.id);
          return (
            <AssetRow
              key={asset.id}
              asset={asset}
              isPrimary={isPrimary}
              isSecondary={isSecondary}
              onClick={handleClick}
            />
          );
        })}
      </div>
    </div>
  );
}

function AssetRow({
  asset,
  isPrimary,
  isSecondary,
  onClick,
}: {
  asset: Asset;
  isPrimary: boolean;
  isSecondary: boolean;
  onClick: (id: string, shiftKey: boolean) => void;
}) {
  const modeIntent = asset.mode === 'idle' ? Intent.PRIMARY
    : asset.mode === 'serving' ? Intent.SUCCESS
    : Intent.WARNING;

  const selClass = isPrimary ? ' asset-primary' : isSecondary ? ' asset-secondary' : '';

  return (
    <div
      className={`asset-row${selClass}`}
      onClick={(e) => onClick(asset.id, e.shiftKey)}
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData('uavId', asset.id.replace('uav_', ''));
      }}
    >
      <span className="asset-id">{asset.name || asset.id}</span>
      <Tag intent={modeIntent} minimal className="asset-mode-tag">
        {asset.mode || asset.status}
      </Tag>
    </div>
  );
}
