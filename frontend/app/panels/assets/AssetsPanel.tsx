import { useCallback, useEffect, useRef, useState } from 'react';
import { Tag, Intent, ProgressBar } from '@blueprintjs/core';
import { useAppStore } from '../../store/appStore';
import type { Asset } from '../../store/types';
import './AssetsPanel.css';

const DOMAIN_FILTERS = ['Air', 'Land', 'Space'] as const;

/** Map asset to a domain category. Currently all UAVs are air. */
function getAssetDomain(_asset: Asset): string {
  return 'air';
}

/** Display name: "Fixed - 01" format. */
function getDisplayName(asset: Asset): string {
  const num = asset.id.replace(/\D/g, '');
  const idx = parseInt(num, 10);
  if (isNaN(idx)) return asset.id;
  return `Fixed - ${String(idx + 1).padStart(2, '0')}`;
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

/** Haversine distance in km between two lon/lat points. */
function haversineKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
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

// ── Search result types ──

interface SearchResult {
  label: string;
  sublabel: string;
  type: 'location' | 'asset' | 'target';
  lon: number;
  lat: number;
  assetId?: string;
}

/** Geocode a query using OpenStreetMap Nominatim. */
async function geocodeNominatim(query: string): Promise<SearchResult[]> {
  try {
    const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=5&countrycodes=ro&accept-language=en`;
    const res = await fetch(url);
    if (!res.ok) return [];
    const data = await res.json();
    return data.map((item: any) => ({
      label: item.display_name.split(',')[0],
      sublabel: item.display_name.split(',').slice(1, 3).join(',').trim(),
      type: 'location' as const,
      lon: parseFloat(item.lon),
      lat: parseFloat(item.lat),
    }));
  } catch {
    return [];
  }
}

/** Search local assets by display name. */
function searchAssets(query: string, assets: Asset[]): SearchResult[] {
  const q = query.toLowerCase();
  return assets
    .filter((a) => {
      const name = getDisplayName(a).toLowerCase();
      const id = a.id.toLowerCase();
      return name.includes(q) || id.includes(q);
    })
    .slice(0, 5)
    .map((a) => ({
      label: getDisplayName(a),
      sublabel: `${a.position?.lon?.toFixed(3)}, ${a.position?.lat?.toFixed(3)}`,
      type: 'asset' as const,
      lon: a.position?.lon ?? 0,
      lat: a.position?.lat ?? 0,
      assetId: a.id,
    }));
}

// ── Search Bar Component ──

function SearchBar({
  assets,
  onResultSelected,
}: {
  assets: Asset[];
  onResultSelected: (result: SearchResult) => void;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setResults([]);
      setIsOpen(false);
      return;
    }

    // Local asset/entity matches (instant)
    const localResults = searchAssets(q, assets);

    // Show local results immediately
    if (localResults.length > 0) {
      setResults(localResults);
      setIsOpen(true);
    }

    // Geocode in parallel (async)
    setLoading(true);
    const geoResults = await geocodeNominatim(q);
    setLoading(false);

    // Merge: assets first, then locations
    const merged = [...localResults, ...geoResults];
    setResults(merged);
    if (merged.length > 0) setIsOpen(true);
  }, [assets]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(val), 300);
  }, [doSearch]);

  const handleSelect = useCallback((result: SearchResult) => {
    setQuery(result.label);
    setIsOpen(false);
    onResultSelected(result);
  }, [onResultSelected]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setIsOpen(false);
      setQuery('');
      setResults([]);
      // Clear sort anchor
      onResultSelected(null as any);
    }
  }, [onResultSelected]);

  const handleClear = useCallback(() => {
    setQuery('');
    setResults([]);
    setIsOpen(false);
    onResultSelected(null as any);
  }, [onResultSelected]);

  return (
    <div className="search-bar-container" ref={containerRef}>
      <div className="search-bar-input-wrap">
        <svg className="search-bar-icon" viewBox="0 0 16 16" width="12" height="12">
          <path fill="#64748b" d="M11.7 10.3l3 3a1 1 0 01-1.4 1.4l-3-3a6 6 0 111.4-1.4zM7 11a4 4 0 100-8 4 4 0 000 8z"/>
        </svg>
        <input
          type="text"
          className="search-bar-input"
          placeholder="Search location, asset..."
          value={query}
          onChange={handleInputChange}
          onFocus={() => { if (results.length > 0) setIsOpen(true); }}
          onKeyDown={handleKeyDown}
        />
        {query && (
          <button className="search-bar-clear" onClick={handleClear}>&times;</button>
        )}
        {loading && <span className="search-bar-spinner" />}
      </div>
      {isOpen && results.length > 0 && (
        <div className="search-bar-dropdown">
          {results.map((r, i) => (
            <div
              key={`${r.type}-${r.label}-${i}`}
              className="search-result"
              onClick={() => handleSelect(r)}
            >
              <span className={`search-result-type search-type-${r.type}`}>
                {r.type === 'location' ? '\u25CB' : r.type === 'asset' ? '\u25A0' : '\u25C7'}
              </span>
              <div className="search-result-text">
                <span className="search-result-label">{r.label}</span>
                <span className="search-result-sub">{r.sublabel}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Panel ──

export function AssetsPanel() {
  const allAssets = useAppStore((s) => s.assets);
  const primaryId = useAppStore((s) => s.selection.primaryAssetId);
  const selectedIds = useAppStore((s) => s.selection.assetIds);
  const [activeFilters, setActiveFilters] = useState<Set<string>>(new Set());
  const [sortAnchor, setSortAnchor] = useState<{ lon: number; lat: number; label: string } | null>(null);

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
      setSortAnchor(null);
      return;
    }

    // Set sort anchor
    setSortAnchor({ lon: result.lon, lat: result.lat, label: result.label });

    // If it's an asset, select it on globe
    if (result.type === 'asset' && result.assetId) {
      selectOnGlobe(result.assetId, false);
      return;
    }

    // If it's a location, fly camera there
    const viewer = (window as any).viewer;
    if (viewer) {
      const Cesium = (window as any).Cesium;
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(result.lon, result.lat, 50000),
        orientation: { heading: 0, pitch: Cesium.Math.toRadians(-60), roll: 0 },
        duration: 1.5,
      });
    }
  }, []);

  return (
    <div className="assets-panel">
      <SearchBar assets={assets} onResultSelected={handleSearchResult} />

      {sortAnchor && (
        <div className="sort-anchor-label">
          Sorted by distance to <strong>{sortAnchor.label}</strong>
        </div>
      )}

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

  return (
    <div
      className={`asset-card${selClass}${isExpanded ? ' asset-expanded' : ''}`}
      onClick={(e) => onClick(asset.id, e.shiftKey)}
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData('uavId', asset.id.replace('uav_', ''));
      }}
    >
      {/* ── Compact header (always visible) ── */}
      <div className="asset-card-header">
        <div className="asset-card-name">
          <span className="asset-id">{displayName}</span>
          <span className="asset-manufacturer">AMS Fixed</span>
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

      {/* ── Compact inline telemetry (only when collapsed) ── */}
      {!isExpanded && (
        <>
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
    </div>
  );
}
