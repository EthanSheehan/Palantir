import { useCallback, useState } from 'react';
import { Tag, Intent, ProgressBar } from '@blueprintjs/core';
import { useAppStore } from '../../store/appStore';
import type { Asset } from '../../store/types';
import './AssetsPanel.css';

const DOMAIN_FILTERS = ['Air', 'Land', 'Space'] as const;

/** Map asset to a domain category. Currently all UAVs are air. */
function getAssetDomain(_asset: Asset): string {
  // Future: check asset.type for ground vehicles, satellites, etc.
  return 'air';
}

/** Display name: "Fixed - 01" format. Extracts the number and 1-indexes it. */
function getDisplayName(asset: Asset): string {
  const num = asset.id.replace(/\D/g, '');
  const idx = parseInt(num, 10);
  if (isNaN(idx)) return asset.id;
  return `Fixed - ${String(idx + 1).padStart(2, '0')}`;
}

/**
 * Trigger the same selection behavior as clicking a drone on the globe.
 */
function selectOnGlobe(assetId: string, additive: boolean) {
  const viewer = (window as any).viewer;
  const controller = (window as any).MapToolController;
  if (!viewer || !controller) return;

  // The Cesium entity ID is uav_N — map ast_N to uav_N if needed
  let entityId = assetId;
  if (entityId.startsWith('ast_')) {
    entityId = 'uav_' + entityId.replace('ast_', '');
  }

  const entity = viewer.entities.getById(entityId);
  if (!entity) return;

  if (additive) {
    controller._triggerDroneSelectionAdditive(entity);
  } else {
    controller._triggerDroneSelection(entity, 'macro');
  }
}

export function AssetsPanel() {
  const allAssets = useAppStore((s) => s.assets);
  const primaryId = useAppStore((s) => s.selection.primaryAssetId);
  const selectedIds = useAppStore((s) => s.selection.assetIds);
  const [activeFilters, setActiveFilters] = useState<Set<string>>(new Set());

  const toggleFilter = useCallback((f: string) => {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(f)) next.delete(f);
      else next.add(f);
      return next;
    });
  }, []);

  // Deduplicate: keep only uav_N entries (Cesium canonical IDs), skip ast_N duplicates
  const assets = Object.values(allAssets)
    .filter((a) => !a.id.startsWith('ast_'))
    .sort((a, b) => {
      const numA = parseInt(a.id.replace(/\D/g, ''), 10);
      const numB = parseInt(b.id.replace(/\D/g, ''), 10);
      return numA - numB;
    });

  // If no filters active, show all; otherwise show only matching domains
  const filtered = activeFilters.size === 0
    ? assets
    : assets.filter((a) => activeFilters.has(getAssetDomain(a).toLowerCase()));

  const handleClick = useCallback((assetId: string, shiftKey: boolean) => {
    selectOnGlobe(assetId, shiftKey);
  }, []);

  return (
    <div className="assets-panel">
      <div className="assets-filters">
        {DOMAIN_FILTERS.map((f) => {
          const key = f.toLowerCase();
          const isActive = activeFilters.has(key);
          return (
            <button
              key={key}
              className={`filter-toggle${isActive ? ' filter-active' : ''}`}
              onClick={() => toggleFilter(key)}
            >
              {f}
            </button>
          );
        })}
      </div>

      <div className="assets-list">
        {filtered.length === 0 && (
          <div className="empty-state">No assets match filter</div>
        )}
        {filtered.map((asset) => {
          const isPrimary = asset.id === primaryId;
          const isSecondary = !isPrimary && selectedIds.includes(asset.id);
          return (
            <AssetCard
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

function AssetCard({
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

  const pos = asset.position || { lon: 0, lat: 0 };
  const batteryPct = asset.battery_pct ?? 0;
  const linkPct = (asset.link_quality ?? 0) * 100;
  const displayName = getDisplayName(asset);

  return (
    <div
      className={`asset-card${selClass}`}
      onClick={(e) => onClick(asset.id, e.shiftKey)}
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData('uavId', asset.id.replace('uav_', ''));
      }}
    >
      {/* Header row: name + status tags */}
      <div className="asset-card-header">
        <span className="asset-id">{displayName}</span>
        <div className="asset-card-tags">
          <Tag intent={modeIntent} minimal className="asset-tag-sm">
            {asset.mode || asset.status}
          </Tag>
          {asset.health && asset.health !== 'nominal' && (
            <Tag intent={Intent.DANGER} minimal className="asset-tag-sm">
              {asset.health}
            </Tag>
          )}
        </div>
      </div>

      {/* Telemetry grid */}
      <div className="asset-card-telem">
        <div className="telem-cell">
          <span className="telem-label">LON</span>
          <span className="telem-value">{pos.lon?.toFixed(4)}</span>
        </div>
        <div className="telem-cell">
          <span className="telem-label">LAT</span>
          <span className="telem-value">{pos.lat?.toFixed(4)}</span>
        </div>
        <div className="telem-cell">
          <span className="telem-label">ALT</span>
          <span className="telem-value">{(pos.alt_m ?? 0).toFixed(0)}m</span>
        </div>
        <div className="telem-cell">
          <span className="telem-label">HDG</span>
          <span className="telem-value">{(asset.heading_deg ?? 0).toFixed(0)}&deg;</span>
        </div>
      </div>

      {/* Systems row: battery bar + link */}
      <div className="asset-card-systems">
        <div className="system-bar-group">
          <span className="system-label">BAT</span>
          <ProgressBar
            value={batteryPct / 100}
            intent={batteryPct > 30 ? Intent.SUCCESS : Intent.DANGER}
            stripes={false}
            className="system-bar"
          />
          <span className="system-pct">{batteryPct.toFixed(0)}%</span>
        </div>
        <div className="system-bar-group">
          <span className="system-label">LNK</span>
          <ProgressBar
            value={linkPct / 100}
            intent={linkPct > 50 ? Intent.PRIMARY : Intent.WARNING}
            stripes={false}
            className="system-bar"
          />
          <span className="system-pct">{linkPct.toFixed(0)}%</span>
        </div>
      </div>
    </div>
  );
}
