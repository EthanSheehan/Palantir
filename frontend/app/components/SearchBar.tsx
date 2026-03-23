import { useCallback, useEffect, useRef, useState } from 'react';
import { InputGroup, Button, Spinner, Icon, Menu, MenuItem } from '@blueprintjs/core';
import type { Asset } from '../store/types';
import './SearchBar.css';

// ── Search result types ──

export interface SearchResult {
  label: string;
  sublabel: string;
  type: 'location' | 'asset' | 'target';
  lon: number;
  lat: number;
  assetId?: string;
}

/** Haversine distance in km between two lon/lat points. */
export function haversineKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
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
function searchEntities(query: string, assets: Asset[], getDisplayName: (a: Asset) => string): SearchResult[] {
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

/** Search targets from both simple _targets and complex _complexTargets arrays. */
function searchTargets(query: string): SearchResult[] {
  const q = query.toLowerCase();
  const results: SearchResult[] = [];

  // Simple targets
  const targets = (window as any)._targets as Array<{ id: number; lon: number; lat: number }> | undefined;
  if (targets) {
    targets
      .filter((t) => `tgt-${String(t.id).padStart(3, '0')}`.includes(q) || `target ${t.id}`.includes(q))
      .slice(0, 3)
      .forEach((t) => results.push({
        label: `TGT-${String(t.id).padStart(3, '0')}`,
        sublabel: `${t.lat.toFixed(3)}, ${t.lon.toFixed(3)}`,
        type: 'target' as const,
        lon: t.lon,
        lat: t.lat,
      }));
  }

  // Complex (MAP) targets
  const complexTargets = (window as any)._complexTargets as Array<{ id: string; name: string; aimpoints: Array<{ lon: number; lat: number }> }> | undefined;
  if (complexTargets) {
    complexTargets
      .filter((c) => c.name.toLowerCase().includes(q) || c.id.toLowerCase().includes(q) || 'map'.includes(q) || 'multi'.includes(q))
      .slice(0, 3)
      .forEach((c) => {
        const centLon = c.aimpoints.reduce((s, a) => s + a.lon, 0) / c.aimpoints.length;
        const centLat = c.aimpoints.reduce((s, a) => s + a.lat, 0) / c.aimpoints.length;
        results.push({
          label: c.name,
          sublabel: `${c.aimpoints.length} aimpoints`,
          type: 'target' as const,
          lon: centLon,
          lat: centLat,
        });
      });
  }

  return results.slice(0, 5);
}

const TYPE_ICON: Record<string, { icon: string; className: string }> = {
  location: { icon: 'map-marker', className: 'search-type-location' },
  asset: { icon: 'cube', className: 'search-type-asset' },
  target: { icon: 'diamond', className: 'search-type-target' },
};

// ── SearchBar Component ──

export function SearchBar({
  assets,
  getDisplayName,
  includeTargets,
  onResultSelected,
  placeholder,
}: {
  assets?: Asset[];
  getDisplayName?: (a: Asset) => string;
  includeTargets?: boolean;
  onResultSelected: (result: SearchResult | null) => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const containerRef = useRef<HTMLDivElement>(null);

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

    const localResults: SearchResult[] = [];

    // Asset matches
    if (assets && getDisplayName) {
      localResults.push(...searchEntities(q, assets, getDisplayName));
    }

    // Target matches
    if (includeTargets) {
      localResults.push(...searchTargets(q));
    }

    if (localResults.length > 0) {
      setResults(localResults);
      setIsOpen(true);
    }

    // Geocode in parallel
    setLoading(true);
    const geoResults = await geocodeNominatim(q);
    setLoading(false);

    const merged = [...localResults, ...geoResults];
    setResults(merged);
    if (merged.length > 0) setIsOpen(true);
  }, [assets, getDisplayName, includeTargets]);

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
      onResultSelected(null);
    }
  }, [onResultSelected]);

  const handleClear = useCallback(() => {
    setQuery('');
    setResults([]);
    setIsOpen(false);
    onResultSelected(null);
  }, [onResultSelected]);

  const rightElement = (
    <>
      {loading && <Spinner size={12} />}
      {query && (
        <Button icon="cross" minimal small onClick={handleClear} />
      )}
    </>
  );

  return (
    <div className="search-bar-container" ref={containerRef}>
      <InputGroup
        leftIcon="search"
        placeholder={placeholder ?? 'Search location, asset...'}
        value={query}
        onChange={handleInputChange}
        onFocus={() => { if (results.length > 0) setIsOpen(true); }}
        onKeyDown={handleKeyDown}
        rightElement={rightElement}
        small
        className="search-bar-input"
      />
      {isOpen && results.length > 0 && (
        <Menu className="search-bar-dropdown">
          {results.map((r, i) => {
            const typeInfo = TYPE_ICON[r.type] ?? { icon: 'dot', className: '' };
            return (
              <MenuItem
                key={`${r.type}-${r.label}-${i}`}
                icon={<Icon icon={typeInfo.icon as any} className={typeInfo.className} size={12} />}
                text={<span className="search-result-label">{r.label}</span>}
                labelElement={<span className="search-result-sub">{r.sublabel}</span>}
                onClick={() => handleSelect(r)}
                className="search-result-item"
              />
            );
          })}
        </Menu>
      )}
    </div>
  );
}
