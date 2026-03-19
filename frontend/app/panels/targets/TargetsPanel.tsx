import { useCallback, useEffect, useState } from 'react';
import { HTMLSelect, Button, Intent } from '@blueprintjs/core';
import { SearchBar } from '../../components/SearchBar';
import type { SearchResult } from '../../components/SearchBar';
import './TargetsPanel.css';

interface Target {
  id: number;
  lon: number;
  lat: number;
  type: string;
}

function getTargets(): Target[] {
  return ((window as any)._targets as Target[]) || [];
}

/**
 * TargetsPanel — React target list with search bar and type filter dropdown.
 * Replaces the legacy #tab-targets content entirely.
 */
export function TargetsPanel() {
  const [sortAnchor, setSortAnchor] = useState<{ lon: number; lat: number; label: string } | null>(null);
  const [typeFilter, setTypeFilter] = useState('all');
  const [isPainting, setIsPainting] = useState(false);
  const [, setTick] = useState(0); // force re-render when targets change

  // Poll targets array for changes + track paint mode
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 1000);

    // Listen for tool changes from MapToolController
    const controller = (window as any).MapToolController;
    if (controller?.onToolChange) {
      controller.onToolChange((toolId: string) => {
        setIsPainting(toolId === 'paint_target');
      });
      // Check initial state
      setIsPainting(controller.getActiveTool?.() === 'paint_target');
    }

    return () => clearInterval(interval);
  }, []);

  const targets = getTargets();

  // Collect unique target types for the dropdown
  const types = Array.from(new Set(targets.map((t) => t.type || 'unknown'))).sort();

  const filtered = typeFilter === 'all'
    ? targets
    : targets.filter((t) => (t.type || 'unknown') === typeFilter);

  const handleSearchResult = useCallback((result: SearchResult | null) => {
    const viewer = (window as any).viewer;
    const Cesium = (window as any).Cesium;

    // Remove previous search marker
    if (viewer) {
      const existing = viewer.entities.getById('_search_marker');
      if (existing) viewer.entities.remove(existing);
      viewer.scene.requestRender();
    }

    if (!result) {
      setSortAnchor(null);
      return;
    }

    setSortAnchor({ lon: result.lon, lat: result.lat, label: result.label });

    if (result.type === 'target') {
      if (viewer && Cesium) {
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(result.lon, result.lat, 5000),
          orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 },
          duration: 1.2,
        });
      }
      return;
    }

    if (result.type === 'location' && viewer && Cesium) {
      viewer.entities.add({
        id: '_search_marker',
        name: result.label,
        position: Cesium.Cartesian3.fromDegrees(result.lon, result.lat, 0),
        cylinder: {
          length: 3000, topRadius: 300, bottomRadius: 300,
          material: Cesium.Color.fromCssColorString('#f97316').withAlpha(0.85),
          outline: true, outlineColor: Cesium.Color.fromCssColorString('#fb923c'),
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        },
        label: {
          text: result.label, font: '11px Inter, sans-serif',
          fillColor: Cesium.Color.fromCssColorString('#f97316'),
          outlineColor: Cesium.Color.BLACK, outlineWidth: 2,
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
  }, []);

  const handlePaint = useCallback(() => {
    const controller = (window as any).MapToolController;
    if (!controller) return;
    const current = controller.getActiveTool();
    controller.setTool(current === 'paint_target' ? 'select' : 'paint_target');
  }, []);

  const handleTargetClick = useCallback((t: Target) => {
    const viewer = (window as any).viewer;
    const Cesium = (window as any).Cesium;
    if (viewer && Cesium) {
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 5000),
        orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 },
        duration: 1.2,
      });
    }
  }, []);

  const handleRemove = useCallback((id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    // Call legacy _removeTarget
    const targets = (window as any)._targets as Target[];
    const viewer = (window as any).viewer;
    const idx = targets.findIndex((t) => t.id === id);
    if (idx === -1) return;
    const t = targets.splice(idx, 1)[0] as any;
    if (t.topCone) viewer?.entities.remove(t.topCone);
    if (t.botCone) viewer?.entities.remove(t.botCone);
    if (t.lensTopCone) {
      const lv = (window as any)._lensViewer;
      if (lv) { lv.entities.remove(t.lensTopCone); lv.entities.remove(t.lensBotCone); }
    }
    viewer?.scene.requestRender();
    setTick((v) => v + 1); // trigger re-render
  }, []);

  return (
    <div className="targets-panel">
      <SearchBar
        includeTargets
        onResultSelected={handleSearchResult}
        placeholder="Search location, target..."
      />

      {sortAnchor && (
        <div className="sort-anchor-label">
          Sorted by distance to <strong>{sortAnchor.label}</strong>
        </div>
      )}

      {/* Filter + paint button row */}
      <div className="targets-toolbar">
        <HTMLSelect
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="targets-type-select"
        >
          <option value="all">All Types ({targets.length})</option>
          {types.map((t) => (
            <option key={t} value={t}>
              {t.charAt(0).toUpperCase() + t.slice(1)} ({targets.filter((tg) => (tg.type || 'unknown') === t).length})
            </option>
          ))}
        </HTMLSelect>
        <Button
          small
          intent={isPainting ? Intent.NONE : Intent.DANGER}
          icon={isPainting ? undefined : "plus"}
          className={`targets-paint-btn${isPainting ? ' painting-active' : ''}`}
          onClick={handlePaint}
          title={isPainting ? 'Click to stop painting' : 'Paint Target — click globe to place'}
        >
          {isPainting ? 'Painting' : 'Paint'}
        </Button>
      </div>

      {/* Target list */}
      <div className="targets-list">
        {filtered.length === 0 ? (
          <div className="empty-state">
            {targets.length === 0 ? 'No targets. Use + to paint.' : 'No targets match filter.'}
          </div>
        ) : (
          filtered.map((t) => (
            <div
              key={t.id}
              className="target-card-react"
              onClick={() => handleTargetClick(t)}
            >
              <div className="target-card-header">
                <span className="target-diamond">&#x25C7;</span>
                <span className="target-id">TGT-{String(t.id).padStart(3, '0')}</span>
                <span className="target-type-badge">{t.type || 'unknown'}</span>
                <button
                  className="target-remove"
                  onClick={(e) => handleRemove(t.id, e)}
                  title="Remove target"
                >
                  &times;
                </button>
              </div>
              <div className="target-coords">
                {t.lat.toFixed(4)}&deg; N &nbsp; {t.lon.toFixed(4)}&deg; E
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
