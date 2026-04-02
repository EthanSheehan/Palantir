import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useSimStore } from '../store/SimulationStore';

interface SearchResult {
  label: string;
  sublabel: string;
  type: 'uav' | 'target' | 'location';
  lon: number;
  lat: number;
  entityId?: number;
}

function haversineKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function searchLocal(query: string): SearchResult[] {
  const q = query.toLowerCase();
  const state = useSimStore.getState();
  const results: SearchResult[] = [];

  state.uavs
    .filter((u) => `uav ${u.id}`.includes(q) || `uav-${u.id}`.includes(q) || u.mode.toLowerCase().includes(q))
    .slice(0, 5)
    .forEach((u) =>
      results.push({
        label: `UAV-${u.id}`,
        sublabel: `${u.mode} | ${u.lat.toFixed(3)}, ${u.lon.toFixed(3)}`,
        type: 'uav',
        lon: u.lon,
        lat: u.lat,
        entityId: u.id,
      })
    );

  state.targets
    .filter((t) => `target ${t.id}`.includes(q) || `tgt-${t.id}`.includes(q) || t.type.toLowerCase().includes(q))
    .slice(0, 5)
    .forEach((t) =>
      results.push({
        label: `TGT-${t.id} (${t.type})`,
        sublabel: `${t.state} | ${t.lat.toFixed(3)}, ${t.lon.toFixed(3)}`,
        type: 'target',
        lon: t.lon,
        lat: t.lat,
        entityId: t.id,
      })
    );

  return results;
}

export function SearchBar() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [activeIdx, setActiveIdx] = useState(0);
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const doSearch = useCallback((q: string) => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    const local = searchLocal(q);
    setResults(local);
    setActiveIdx(0);
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(query), 150);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, doSearch]);

  const flyTo = useCallback((result: SearchResult) => {
    window.dispatchEvent(
      new CustomEvent('amc-grid:flyTo', {
        detail: { lon: result.lon, lat: result.lat, altitude: 15000 },
      })
    );
    if (result.type === 'uav' && result.entityId !== undefined) {
      useSimStore.getState().selectDrone(result.entityId);
    }
    setOpen(false);
    setQuery('');
  }, []);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx((i) => Math.min(i + 1, results.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter' && results[activeIdx]) {
        e.preventDefault();
        flyTo(results[activeIdx]);
      } else if (e.key === 'Escape') {
        setOpen(false);
        setQuery('');
      }
    },
    [results, activeIdx, flyTo]
  );

  const TYPE_COLORS: Record<string, string> = {
    uav: '#3b82f6',
    target: '#ef4444',
    location: '#10b981',
  };

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <input
        ref={inputRef}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder="Search UAVs, targets, locations..."
        style={{
          width: '100%',
          padding: '6px 10px',
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 3,
          color: '#cbd5e1',
          fontSize: 12,
          fontFamily: 'monospace',
          outline: 'none',
        }}
      />
      {open && results.length > 0 && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            zIndex: 9500,
            background: 'rgba(15,20,30,0.98)',
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: 3,
            boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
            maxHeight: 240,
            overflowY: 'auto',
          }}
        >
          {results.map((r, i) => (
            <div
              key={`${r.type}-${r.label}-${i}`}
              onClick={() => flyTo(r)}
              onMouseEnter={() => setActiveIdx(i)}
              style={{
                padding: '6px 10px',
                cursor: 'pointer',
                background: i === activeIdx ? 'rgba(59,130,246,0.15)' : 'transparent',
                borderLeft: i === activeIdx ? '2px solid #3b82f6' : '2px solid transparent',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <span
                style={{
                  fontSize: 9,
                  fontWeight: 700,
                  padding: '1px 4px',
                  borderRadius: 2,
                  textTransform: 'uppercase',
                  color: TYPE_COLORS[r.type] || '#94a3b8',
                  background: `${TYPE_COLORS[r.type] || '#94a3b8'}1a`,
                  border: `1px solid ${TYPE_COLORS[r.type] || '#94a3b8'}33`,
                }}
              >
                {r.type}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ color: '#e2e8f0', fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {r.label}
                </div>
                <div style={{ color: '#64748b', fontSize: 10 }}>{r.sublabel}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
