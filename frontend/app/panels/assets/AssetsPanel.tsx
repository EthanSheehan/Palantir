import { useCallback, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Tag, Intent, ProgressBar, Card, Button, ButtonGroup, Tabs, Tab, NonIdealState, Menu, MenuItem } from '@blueprintjs/core';
import { useAppStore } from '../../store/appStore';
import type { Asset } from '../../store/types';
import { SearchBar, haversineKm } from '../../components/SearchBar';
import type { SearchResult } from '../../components/SearchBar';
import './AssetsPanel.css';
import '../targets/TargetsPanel.css';
import { updateTargetHighlights, targetDisplayName } from '../targets/TargetsPanel';

const DOMAIN_FILTERS = ['Air', 'Land', 'Space'] as const;

/** Map asset to a domain category. */
function getAssetDomain(asset: Asset): string {
  if (asset.id.startsWith('launcher_')) return 'land';
  return 'air';
}

/** Display name based on asset type. */
function getDisplayName(asset: Asset): string {
  const num = asset.id.replace(/\D/g, '');
  const idx = parseInt(num, 10);
  if (isNaN(idx)) return asset.id;
  if (asset.id.startsWith('launcher_')) return `Launcher - ${String(idx + 1).padStart(2, '0')}`;
  return `Fixed - ${String(idx + 1).padStart(2, '0')}`;
}

/** Manufacturer/vehicle label based on asset type. */
function getManufacturerLabel(asset: Asset): string {
  if (asset.id.startsWith('launcher_')) return 'Ground Vehicle';
  return 'AMS Fixed';
}

/** Cruise speed ~2.2 km/s (0.02 deg/s from sim.py). */
const CRUISE_SPEED_KMS = 2.2;

/** Format seconds into human-readable ETA. */
function formatEta(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function selectOnGlobe(assetId: string, additive: boolean) {
  const viewer = (window as any).viewer;
  const controller = (window as any).MapToolController;
  if (!viewer || !controller) return;
  let entityId = assetId;
  if (entityId.startsWith('ast_')) entityId = 'uav_' + entityId.replace('ast_', '');
  const entity = viewer.entities.getById(entityId);
  if (!entity) return;
  if (additive) controller._triggerDroneSelectionAdditive(entity);
  else controller._triggerDroneSelection(entity, 'macro');
}

// ── Shared search bar handler ──

/** Place/remove orange search marker on globe and fly camera. */
function handleSearchLocation(result: SearchResult | null) {
  const viewer = (window as any).viewer;
  const Cesium = (window as any).Cesium;

  // Remove previous search marker
  if (viewer) {
    const existing = viewer.entities.getById('_search_marker');
    if (existing) viewer.entities.remove(existing);
    viewer.scene.requestRender();
  }

  if (!result || result.type !== 'location') return;

  if (viewer && Cesium) {
    viewer.entities.add({
      id: '_search_marker',
      name: result.label,
      position: Cesium.Cartesian3.fromDegrees(result.lon, result.lat, 0),
      cylinder: {
        length: 3000,
        topRadius: 300,
        bottomRadius: 300,
        material: Cesium.Color.fromCssColorString('#f97316').withAlpha(0.85),
        outline: true,
        outlineColor: Cesium.Color.fromCssColorString('#fb923c'),
        outlineWidth: 1,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      },
      label: {
        text: result.label,
        font: '11px Inter, sans-serif',
        fillColor: Cesium.Color.fromCssColorString('#f97316'),
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 2,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        pixelOffset: new Cesium.Cartesian2(0, -20),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
    viewer.scene.requestRender();
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(result.lon, result.lat, 80000),
      orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 },
      duration: 1.5,
    });
  }
}

// ── Main Panel ──

export function AssetsPanel() {
  const allAssets = useAppStore((s) => s.assets);
  const primaryId = useAppStore((s) => s.selection.primaryAssetId);
  const selectedIds = useAppStore((s) => s.selection.assetIds);
  const pinnedTarget = useAppStore((s) => s.pinnedTarget);
  const setPinnedTarget = useAppStore((s) => s.setPinnedTarget);
  const setLeftPanelTab = useAppStore((s) => s.setLeftPanelTab);
  const [pinnedHighlighted, setPinnedHighlighted] = useState(false);
  const [activeFilters, setActiveFilters] = useState<Set<string>>(new Set());
  const [sortAnchor, setSortAnchor] = useState<{ lon: number; lat: number; label: string } | null>(null);
  const [subTab, setSubTab] = useState<'active' | 'create'>('active');

  // Auto-set/clear sortAnchor when a target is pinned/unpinned
  useEffect(() => {
    if (pinnedTarget) {
      setSortAnchor({ lon: pinnedTarget.lon, lat: pinnedTarget.lat, label: pinnedTarget.name });
    } else {
      setSortAnchor(null);
      setPinnedHighlighted(false);
    }
  }, [pinnedTarget]);

  // Sync highlight ring with pinnedHighlighted state
  useEffect(() => {
    if (pinnedHighlighted && pinnedTarget) {
      updateTargetHighlights([pinnedTarget.id]);
    } else {
      updateTargetHighlights([]);
    }
  }, [pinnedHighlighted, pinnedTarget]);

  const toggleFilter = useCallback((f: string) => {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(f)) next.delete(f);
      else next.add(f);
      return next;
    });
  }, []);

  // Deduplicate: keep only uav_N entries
  const assets = Object.values(allAssets).filter((a) => !a.id.startsWith('ast_'));

  // Sort: by distance to anchor if set, otherwise by ID
  const sorted = [...assets].sort((a, b) => {
    if (sortAnchor) {
      const dA = haversineKm(sortAnchor.lon, sortAnchor.lat, a.position?.lon ?? 0, a.position?.lat ?? 0);
      const dB = haversineKm(sortAnchor.lon, sortAnchor.lat, b.position?.lon ?? 0, b.position?.lat ?? 0);
      return dA - dB;
    }
    const numA = parseInt(a.id.replace(/\D/g, ''), 10);
    const numB = parseInt(b.id.replace(/\D/g, ''), 10);
    return numA - numB;
  });

  // Filter by domain
  const filtered = activeFilters.size === 0
    ? sorted
    : sorted.filter((a) => activeFilters.has(getAssetDomain(a).toLowerCase()));

  const handleClick = useCallback((assetId: string, shiftKey: boolean) => {
    selectOnGlobe(assetId, shiftKey);
  }, []);

  const handleSearchResult = useCallback((result: SearchResult | null) => {
    if (!result) {
      // Fall back to pinned target sort anchor if one exists
      if (pinnedTarget) {
        setSortAnchor({ lon: pinnedTarget.lon, lat: pinnedTarget.lat, label: pinnedTarget.name });
      } else {
        setSortAnchor(null);
      }
      handleSearchLocation(null);
      return;
    }

    setSortAnchor({ lon: result.lon, lat: result.lat, label: result.label });

    if (result.type === 'asset' && result.assetId) {
      selectOnGlobe(result.assetId, false);
      handleSearchLocation(null);
      return;
    }

    if (result.type === 'target') {
      // Fly to target location
      const viewer = (window as any).viewer;
      const Cesium = (window as any).Cesium;
      if (viewer && Cesium) {
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(result.lon, result.lat, 5000),
          orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 },
          duration: 1.2,
        });
      }
      handleSearchLocation(null);
      return;
    }

    handleSearchLocation(result);
  }, [pinnedTarget]);

  return (
    <div className="assets-panel">
      {pinnedTarget && (
        <Card className="pinned-target-map-card" interactive
          onClick={() => setPinnedHighlighted((v) => !v)}>
          <Button icon="cross" minimal small className="pinned-unpin-btn" onClick={(e) => { e.stopPropagation(); setPinnedTarget(null); setLeftPanelTab('targets' as any); }} title="Remove from Assets" />
          <div className="complex-card-header">
            <span className="complex-icon">{pinnedTarget.aimpoints ? '\u2B23' : '\u25C7'}</span>
            <span className="complex-name">{targetDisplayName(pinnedTarget.id, pinnedTarget.name)}</span>
            <span className="target-type-badge">multi-aim</span>
            {pinnedTarget.aimpoints && <span className="complex-count">{pinnedTarget.aimpoints.length} pts</span>}
            <Button icon="locate" minimal small className="target-zoom-btn" onClick={(e) => {
              e.stopPropagation();
              const viewer = (window as any).viewer;
              const Cesium = (window as any).Cesium;
              if (!viewer || !Cesium || !pinnedTarget.aimpoints?.length) return;
              const centLon = pinnedTarget.aimpoints.reduce((s, a) => s + a.lon, 0) / pinnedTarget.aimpoints.length;
              const centLat = pinnedTarget.aimpoints.reduce((s, a) => s + a.lat, 0) / pinnedTarget.aimpoints.length;
              viewer.camera.flyTo({
                destination: Cesium.Cartesian3.fromDegrees(centLon, centLat, 15000),
                orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 },
                duration: 1.2,
              });
            }} title="Zoom to Target" />
          </div>
          <div className="target-coords">
            {pinnedTarget.lat.toFixed(4)}&deg; N &nbsp; {pinnedTarget.lon.toFixed(4)}&deg; E
          </div>
          <div className="target-desc">{pinnedTarget.description || 'Click to add description...'}</div>
          {pinnedTarget.aimpoints && pinnedTarget.aimpoints.length > 0 && (
            <>
              <div className="complex-aimpoints-label">Aimpoints ({pinnedTarget.aimpoints.length})</div>
              <div className="complex-aimpoints">
                <table className="aimpoints-table" style={{ marginTop: 0 }}>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Type</th>
                      <th>Lat</th>
                      <th>Lon</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pinnedTarget.aimpoints.map((ap) => (
                      <tr key={ap.id}>
                        <td className="ap-id">AP-{String(ap.id).padStart(3, '0')}</td>
                        <td className="ap-type">{ap.type}</td>
                        <td className="ap-coord">{ap.lat.toFixed(4)}</td>
                        <td className="ap-coord">{ap.lon.toFixed(4)}</td>
                        <td className="ap-desc">{ap.description || '\u2014'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Card>
      )}

      {/* ── Sub-tab bar ── */}
      <Tabs
        id="assets-subtabs"
        selectedTabId={subTab}
        onChange={(id) => setSubTab(id as 'active' | 'create')}
        className="assets-subtabs"
      >
        <Tab id="active" title="Active" />
        <Tab id="create" title="Create Package" />
      </Tabs>

      <SearchBar
        assets={assets}
        getDisplayName={getDisplayName}
        includeTargets
        onResultSelected={handleSearchResult}
      />

      {subTab === 'active' && (
        <>
          {sortAnchor && (
            <div className="sort-anchor-label">
              Sorted by distance to <strong>{sortAnchor.label}</strong>
            </div>
          )}

          <ButtonGroup className="assets-filters" fill>
            {DOMAIN_FILTERS.map((f) => {
              const key = f.toLowerCase();
              const isActive = activeFilters.has(key);
              return (
                <Button
                  key={key}
                  small
                  active={isActive}
                  intent={isActive ? Intent.PRIMARY : Intent.NONE}
                  onClick={() => toggleFilter(key)}
                  className="filter-toggle"
                >
                  {f}
                </Button>
              );
            })}
          </ButtonGroup>

          <div className="assets-list">
            {filtered.length === 0 && (
              <NonIdealState description="No assets match filter" className="panel-empty-state" />
            )}
            {filtered.map((asset) => {
              const isPrimary = asset.id === primaryId;
              const isSecondary = !isPrimary && selectedIds.includes(asset.id);
              const dist = sortAnchor
                ? haversineKm(sortAnchor.lon, sortAnchor.lat, asset.position?.lon ?? 0, asset.position?.lat ?? 0)
                : null;
              return (
                <AssetCard
                  key={asset.id}
                  asset={asset}
                  isPrimary={isPrimary}
                  isSecondary={isSecondary}
                  onClick={handleClick}
                  distanceKm={dist}
                />
              );
            })}
          </div>
        </>
      )}

      {subTab === 'create' && (
        <>
          {sortAnchor && (
            <div className="sort-anchor-label">
              Sorted by distance to <strong>{sortAnchor.label}</strong>
            </div>
          )}
          <div className="assets-list">
            {(() => {
              const launchers = filtered.filter((a) => a.id.startsWith('launcher_'));
              if (launchers.length === 0) return <NonIdealState description="No launchers available" className="panel-empty-state" />;
              return launchers.map((asset) => {
                const isPrimary = asset.id === primaryId;
                const isSecondary = !isPrimary && selectedIds.includes(asset.id);
                const dist = sortAnchor
                  ? haversineKm(sortAnchor.lon, sortAnchor.lat, asset.position?.lon ?? 0, asset.position?.lat ?? 0)
                  : null;
                return (
                  <AssetCard
                    key={asset.id}
                    asset={asset}
                    isPrimary={isPrimary}
                    isSecondary={isSecondary}
                    onClick={handleClick}
                    distanceKm={dist}
                  />
                );
              });
            })()}
          </div>
        </>
      )}
    </div>
  );
}

function AssetCard({
  asset,
  isPrimary,
  isSecondary,
  onClick,
  distanceKm,
}: {
  asset: Asset;
  isPrimary: boolean;
  isSecondary: boolean;
  onClick: (id: string, shiftKey: boolean) => void;
  distanceKm: number | null;
}) {
  const isExpanded = isPrimary || isSecondary;
  const modeIntent = asset.mode === 'idle' ? Intent.PRIMARY
    : asset.mode === 'serving' ? Intent.SUCCESS
    : Intent.WARNING;

  const selClass = isPrimary ? ' asset-primary' : isSecondary ? ' asset-secondary' : '';
  const pos = asset.position || { lon: 0, lat: 0 };
  const batteryPct = asset.battery_pct ?? 0;
  const linkPct = (asset.link_quality ?? 0) * 100;
  const displayName = getDisplayName(asset);
  const etaSec = distanceKm !== null ? distanceKm / CRUISE_SPEED_KMS : null;
  const isLauncher = asset.id.startsWith('launcher_');
  const [ctxMenu, setCtxMenu] = useState<{ x: number; y: number } | null>(null);

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    if (!isLauncher) return;
    e.preventDefault();
    e.stopPropagation();
    setCtxMenu({ x: e.clientX, y: e.clientY });
  }, [isLauncher]);

  // Close context menu on outside click
  useEffect(() => {
    if (!ctxMenu) return;
    const close = () => setCtxMenu(null);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [ctxMenu]);

  const handleLaunch = useCallback(() => {
    const launcherId = parseInt(asset.id.replace('launcher_', ''), 10);
    const ws = new WebSocket('ws://localhost:8012/ws/events');
    ws.onopen = () => {
      ws.send(JSON.stringify({ action: 'launch_drone', launcher_id: launcherId }));
      setTimeout(() => ws.close(), 1000);
    };
    setCtxMenu(null);
  }, [asset.id]);

  return (
    <Card
      interactive
      className={`asset-card${selClass}${isExpanded ? ' asset-expanded' : ''}`}
      onClick={(e) => onClick(asset.id, (e as any).shiftKey)}
      onContextMenu={handleContextMenu}
      draggable
      onDragStart={(e) => {
        (e as any).dataTransfer.setData('uavId', asset.id.replace('uav_', ''));
      }}
    >
      {/* Launcher right-click context menu */}
      {ctxMenu && createPortal(
        <div className="bp5-dark" style={{ position: 'fixed', left: ctxMenu.x, top: ctxMenu.y, zIndex: 9999 }}
          onClick={(e) => e.stopPropagation()}>
          <Menu className="asset-ctx-menu" small>
            <MenuItem icon="rocket" text="Launch Fixed Asset" onClick={handleLaunch} />
          </Menu>
        </div>,
        document.body
      )}
      <Button icon="plus" minimal small className="asset-assign-btn" onClick={(e) => { e.stopPropagation(); }} title="Assign Asset to Target" />
      {/* ── Compact header (always visible) ── */}
      <div className="asset-card-header">
        <div className="asset-card-name">
          <span className="asset-id">{displayName}</span>
          <span className="asset-manufacturer">{getManufacturerLabel(asset)}</span>
        </div>
        <div className="asset-card-tags">
          {distanceKm !== null && !isExpanded && (
            <div className="asset-dist-group">
              <span className="asset-dist">{distanceKm < 1 ? `${(distanceKm * 1000).toFixed(0)}m` : `${distanceKm.toFixed(1)}km`}</span>
              <span className="asset-eta">{formatEta(etaSec!)}</span>
            </div>
          )}
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

      {/* ── Expanded detail table (only when selected) ── */}
      {isExpanded && (
        <div className="asset-detail">
          <table className="detail-table">
            <tbody>
              {distanceKm !== null && (
                <>
                  <tr>
                    <td className="detail-label">Distance</td>
                    <td className="detail-value">{distanceKm < 1 ? `${(distanceKm * 1000).toFixed(0)} m` : `${distanceKm.toFixed(2)} km`}</td>
                  </tr>
                  <tr>
                    <td className="detail-label">Time to Target</td>
                    <td className="detail-value detail-accent">{formatEta(etaSec!)}</td>
                  </tr>
                </>
              )}
              <tr>
                <td className="detail-label">Time on Station</td>
                <td className="detail-value">{asset.mode === 'serving' ? 'Active' : '\u2014'}</td>
              </tr>
              <tr className="detail-sep"><td colSpan={2}></td></tr>
              <tr>
                <td className="detail-label">Latitude</td>
                <td className="detail-value">{pos.lat?.toFixed(5)}&deg;</td>
              </tr>
              <tr>
                <td className="detail-label">Longitude</td>
                <td className="detail-value">{pos.lon?.toFixed(5)}&deg;</td>
              </tr>
              <tr>
                <td className="detail-label">Altitude</td>
                <td className="detail-value">{(pos.alt_m ?? 0).toFixed(0)} m</td>
              </tr>
              <tr>
                <td className="detail-label">Heading</td>
                <td className="detail-value">{(asset.heading_deg ?? 0).toFixed(1)}&deg;</td>
              </tr>
              <tr className="detail-sep"><td colSpan={2}></td></tr>
              <tr>
                <td className="detail-label">Battery</td>
                <td className="detail-value">
                  <div className="detail-bar-row">
                    <ProgressBar
                      value={batteryPct / 100}
                      intent={batteryPct > 30 ? Intent.SUCCESS : Intent.DANGER}
                      stripes={false}
                      className="detail-bar"
                    />
                    <span>{batteryPct.toFixed(1)}%</span>
                  </div>
                </td>
              </tr>
              <tr>
                <td className="detail-label">Link</td>
                <td className="detail-value">
                  <div className="detail-bar-row">
                    <ProgressBar
                      value={linkPct / 100}
                      intent={linkPct > 50 ? Intent.PRIMARY : Intent.WARNING}
                      stripes={false}
                      className="detail-bar"
                    />
                    <span>{linkPct.toFixed(0)}%</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {/* ── Coordinates (target-style, always visible when collapsed) ── */}
      {!isExpanded && (
        <>
          <div className="target-coords">
            {pos.lat?.toFixed(4)}&deg; N &nbsp; {pos.lon?.toFixed(4)}&deg; E &nbsp; {(pos.alt_m ?? 0).toFixed(0)}m &nbsp; {(asset.heading_deg ?? 0).toFixed(0)}&deg;
          </div>
          <div className="asset-card-systems">
            <div className="system-bar-group">
              <span className="system-label">BAT</span>
              <ProgressBar value={batteryPct / 100} intent={batteryPct > 30 ? Intent.SUCCESS : Intent.DANGER} stripes={false} className="system-bar" />
              <span className="system-pct">{batteryPct.toFixed(0)}%</span>
            </div>
            <div className="system-bar-group">
              <span className="system-label">LNK</span>
              <ProgressBar value={linkPct / 100} intent={linkPct > 50 ? Intent.PRIMARY : Intent.WARNING} stripes={false} className="system-bar" />
              <span className="system-pct">{linkPct.toFixed(0)}%</span>
            </div>
          </div>
        </>
      )}
    </Card>
  );
}
