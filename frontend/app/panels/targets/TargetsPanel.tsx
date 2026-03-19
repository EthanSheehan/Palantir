import { useCallback, useEffect, useRef, useState } from 'react';
import { HTMLSelect, Button, Intent } from '@blueprintjs/core';
import { SearchBar } from '../../components/SearchBar';
import type { SearchResult } from '../../components/SearchBar';
import { useAppStore } from '../../store/appStore';
import './TargetsPanel.css';

interface Target {
  id: number;
  lon: number;
  lat: number;
  type: string;
  description?: string;
}

function getTargets(): Target[] {
  return ((window as any)._targets as Target[]) || [];
}

/**
 * TargetsPanel — React target list with search bar and type filter dropdown.
 * Replaces the legacy #tab-targets content entirely.
 */
/** Manage Cesium highlight rings for selected targets */
function updateTargetHighlights(targetIds: number[]) {
  const viewer = (window as any).viewer;
  const Cesium = (window as any).Cesium;
  if (!viewer || !Cesium) return;

  // Remove all previous highlight rings
  const toRemove = viewer.entities.values.filter((e: any) => e.id?.startsWith('_target_highlight_'));
  toRemove.forEach((e: any) => viewer.entities.remove(e));

  if (targetIds.length === 0) {
    viewer.scene.requestRender();
    return;
  }

  const targets = (window as any)._targets as Target[] | undefined;
  if (!targets) return;

  const radius = 800;
  const segments = 48;

  targetIds.forEach((tid, idx) => {
    const target = targets.find((t) => t.id === tid);
    if (!target) return;

    let terrainH = 0;
    const carto = Cesium.Cartographic.fromDegrees(target.lon, target.lat);
    const globe = viewer.scene.globe;
    if (globe) {
      const h = globe.getHeight(carto);
      if (h !== undefined) terrainH = h;
    }

    // Primary = orange, secondary = lighter orange
    const color = idx === 0
      ? Cesium.Color.fromCssColorString('#f97316').withAlpha(0.8)
      : Cesium.Color.fromCssColorString('#fb923c').withAlpha(0.6);

    viewer.entities.add({
      id: `_target_highlight_${tid}`,
      polyline: {
        positions: new Cesium.CallbackProperty(() => {
          const center = Cesium.Cartesian3.fromDegrees(target.lon, target.lat, terrainH);
          const transform = Cesium.Transforms.eastNorthUpToFixedFrame(center);
          const pts: any[] = [];
          for (let i = 0; i <= segments; i++) {
            const angle = (i / segments) * Math.PI * 2;
            const local = new Cesium.Cartesian3(Math.cos(angle) * radius, Math.sin(angle) * radius, 0);
            pts.push(Cesium.Matrix4.multiplyByPoint(transform, local, new Cesium.Cartesian3()));
          }
          return pts;
        }, false),
        width: idx === 0 ? 2.5 : 2,
        material: color,
        clampToGround: true,
      },
    });
  });
  viewer.scene.requestRender();
}

export function TargetsPanel() {
  const [sortAnchor, setSortAnchor] = useState<{ lon: number; lat: number; label: string } | null>(null);
  const [typeFilter, setTypeFilter] = useState('all');
  const [isPainting, setIsPainting] = useState(false);
  const [, setTick] = useState(0);
  const selectedTargetIds = useAppStore((s) => s.selection.selectedTargetIds);
  const selectTarget = useAppStore((s) => s.selectTarget);

  // Sync Cesium highlight rings when selection changes
  useEffect(() => {
    updateTargetHighlights(selectedTargetIds);
  }, [selectedTargetIds]);

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

  const handleTargetClick = useCallback((t: Target, shiftKey: boolean) => {
    // Toggle selection — no camera attach, no compass change
    selectTarget(t.id, shiftKey);
  }, [selectTarget]);

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
            <TargetCard
              key={t.id}
              target={t}
              isSelected={selectedTargetIds.includes(t.id)}
              onClick={(shiftKey) => handleTargetClick(t, shiftKey)}
              onRemove={(e) => handleRemove(t.id, e)}
              onUpdate={(field, value) => {
                (t as any)[field] = value;
                setTick((v) => v + 1);
              }}
            />
          ))
        )}
      </div>
    </div>
  );
}

function TargetCard({
  target,
  isSelected,
  onClick,
  onRemove,
  onUpdate,
}: {
  target: Target;
  isSelected: boolean;
  onClick: (shiftKey: boolean) => void;
  onRemove: (e: React.MouseEvent) => void;
  onUpdate: (field: string, value: string) => void;
}) {
  const [editingField, setEditingField] = useState<'type' | 'description' | null>(null);
  const [editValue, setEditValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingField && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingField]);

  const startEdit = useCallback((field: 'type' | 'description', e: React.MouseEvent) => {
    e.stopPropagation();
    setEditValue(field === 'type' ? (target.type || '') : (target.description || ''));
    setEditingField(field);
  }, [target.type, target.description]);

  const commitEdit = useCallback(() => {
    if (editingField) {
      onUpdate(editingField, editValue);
    }
    setEditingField(null);
  }, [editingField, editValue, onUpdate]);

  const cancelEdit = useCallback(() => {
    setEditingField(null);
  }, []);

  return (
    <div className={`target-card-react${isSelected ? ' target-selected' : ''}`} onClick={(e) => onClick(e.shiftKey)}>
      <div className="target-card-header">
        {/* Delete × on the left, visible only on hover */}
        <button className="target-remove-hover" onClick={onRemove} title="Remove target">
          &times;
        </button>
        <span className="target-diamond">&#x25C7;</span>
        <span className="target-id">TGT-{String(target.id).padStart(3, '0')}</span>
        {/* Editable type badge */}
        {editingField === 'type' ? (
          <input
            ref={inputRef}
            className="target-type-input"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commitEdit();
              if (e.key === 'Escape') cancelEdit();
            }}
            onClick={(e) => e.stopPropagation()}
            placeholder="type..."
          />
        ) : (
          <span
            className="target-type-badge"
            onClick={(e) => startEdit('type', e)}
            title="Click to edit type"
          >
            {target.type || 'unknown'}
          </span>
        )}
      </div>
      <div className="target-coords">
        {target.lat.toFixed(4)}&deg; N &nbsp; {target.lon.toFixed(4)}&deg; E
      </div>
      {/* Inline-editable description */}
      {editingField === 'description' ? (
        <input
          ref={inputRef}
          className="target-desc-input"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onBlur={commitEdit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commitEdit();
            if (e.key === 'Escape') cancelEdit();
          }}
          onClick={(e) => e.stopPropagation()}
          placeholder="Add description..."
        />
      ) : (
        <div className="target-desc" onClick={(e) => startEdit('description', e)}>
          {target.description || 'Click to add description...'}
        </div>
      )}
      {/* Zoom-to button — bottom right */}
      <button
        className="target-zoom-btn"
        onClick={(e) => {
          e.stopPropagation();
          const viewer = (window as any).viewer;
          const Cesium = (window as any).Cesium;
          if (viewer && Cesium) {
            viewer.camera.flyTo({
              destination: Cesium.Cartesian3.fromDegrees(target.lon, target.lat, 5000),
              orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 },
              duration: 1.2,
            });
          }
        }}
        title="Zoom to target"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
          <path d="M2 1L6 5L2 9" stroke="currentColor" strokeWidth="1.5" fill="none"/>
          <path d="M6 1L10 5L6 9" stroke="currentColor" strokeWidth="1.5" fill="none"/>
        </svg>
      </button>
    </div>
  );
}
