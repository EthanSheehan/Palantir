import { useCallback, useEffect, useRef, useState } from 'react';
import { HTMLSelect, Button, Intent } from '@blueprintjs/core';
import { SearchBar } from '../../components/SearchBar';
import type { SearchResult } from '../../components/SearchBar';
import { useAppStore } from '../../store/appStore';
import './TargetsPanel.css';

// ── Data Models ──

interface Target {
  id: number;
  lon: number;
  lat: number;
  type: string;
  description?: string;
  // Cesium entity refs (managed by app.js)
  topCone?: any;
  botCone?: any;
  lensTopCone?: any;
  lensBotCone?: any;
}

interface ComplexTarget {
  id: string;
  name: string;
  type: string;
  description: string;
  aimpoints: Array<{
    id: number;
    lon: number;
    lat: number;
    type: string;
    description: string;
  }>;
  createdAt: number;
}

function getTargets(): Target[] {
  return ((window as any)._targets as Target[]) || [];
}

function getComplexTargets(): ComplexTarget[] {
  if (!(window as any)._complexTargets) (window as any)._complexTargets = [];
  return (window as any)._complexTargets as ComplexTarget[];
}

let _complexIdCounter = 0;

/** Merge selected simple targets into a complex Multi Aim Point target */
function mergeTargetsIntoComplex(targetIds: number[]): ComplexTarget | null {
  const targets = getTargets();
  const selected = targetIds.map((id) => targets.find((t) => t.id === id)).filter(Boolean) as Target[];
  if (selected.length < 2) return null;

  const complex: ComplexTarget = {
    id: `cplx_${++_complexIdCounter}`,
    name: `MAP-${String(_complexIdCounter).padStart(3, '0')}`,
    type: 'multi-aim',
    description: '',
    aimpoints: selected.map((t) => ({
      id: t.id,
      lon: t.lon,
      lat: t.lat,
      type: t.type || 'unknown',
      description: t.description || '',
    })),
    createdAt: Date.now(),
  };

  getComplexTargets().push(complex);

  // Remove simple targets from the _targets array (keep Cesium entities)
  const simpleTargets = (window as any)._targets as Target[];
  targetIds.forEach((id) => {
    const idx = simpleTargets.findIndex((t) => t.id === id);
    if (idx >= 0) simpleTargets.splice(idx, 1);
  });

  // Add connecting lines on the globe
  addComplexTargetVisualization(complex);

  return complex;
}

/** Add Cesium polyline connecting all aimpoints of a complex target */
function addComplexTargetVisualization(complex: ComplexTarget) {
  const viewer = (window as any).viewer;
  const Cesium = (window as any).Cesium;
  if (!viewer || !Cesium || complex.aimpoints.length < 2) return;

  // Create connecting lines between all aimpoints
  const positions = complex.aimpoints.map((ap) =>
    Cesium.Cartesian3.fromDegrees(ap.lon, ap.lat, 100)
  );
  // Close the loop
  positions.push(positions[0]);

  viewer.entities.add({
    id: `_complex_line_${complex.id}`,
    polyline: {
      positions,
      width: 2,
      material: new Cesium.PolylineDashMaterialProperty({
        color: Cesium.Color.fromCssColorString('#f97316').withAlpha(0.6),
        dashLength: 12,
      }),
      clampToGround: true,
    },
  });

  // Add a label at the centroid
  const centLon = complex.aimpoints.reduce((s, a) => s + a.lon, 0) / complex.aimpoints.length;
  const centLat = complex.aimpoints.reduce((s, a) => s + a.lat, 0) / complex.aimpoints.length;

  viewer.entities.add({
    id: `_complex_label_${complex.id}`,
    position: Cesium.Cartesian3.fromDegrees(centLon, centLat, 200),
    label: {
      text: complex.name,
      font: '12px Inter, sans-serif',
      fillColor: Cesium.Color.fromCssColorString('#f97316'),
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 2,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
      pixelOffset: new Cesium.Cartesian2(0, -8),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  });

  viewer.scene.requestRender();
}

/** Manage Cesium highlight rings for selected targets */
function updateTargetHighlights(targetIds: number[]) {
  const viewer = (window as any).viewer;
  const Cesium = (window as any).Cesium;
  if (!viewer || !Cesium) return;

  const toRemove = viewer.entities.values.filter((e: any) => e.id?.startsWith('_target_highlight_'));
  toRemove.forEach((e: any) => viewer.entities.remove(e));

  if (targetIds.length === 0) { viewer.scene.requestRender(); return; }

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
    if (globe) { const h = globe.getHeight(carto); if (h !== undefined) terrainH = h; }

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

// ── Main Panel ──

export function TargetsPanel() {
  const [sortAnchor, setSortAnchor] = useState<{ lon: number; lat: number; label: string } | null>(null);
  const [typeFilter, setTypeFilter] = useState('all');
  const [isPainting, setIsPainting] = useState(false);
  const [, setTick] = useState(0);
  const selectedTargetIds = useAppStore((s) => s.selection.selectedTargetIds);
  const selectTarget = useAppStore((s) => s.selectTarget);

  useEffect(() => { updateTargetHighlights(selectedTargetIds); }, [selectedTargetIds]);

  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 1000);
    const controller = (window as any).MapToolController;
    if (controller?.onToolChange) {
      controller.onToolChange((toolId: string) => setIsPainting(toolId === 'paint_target'));
      setIsPainting(controller.getActiveTool?.() === 'paint_target');
    }
    return () => clearInterval(interval);
  }, []);

  const targets = getTargets();
  const complexTargets = getComplexTargets();
  // Collect types from both simple and complex targets
  const allTypes = [
    ...targets.map((t) => t.type || 'unknown'),
    ...complexTargets.map((c) => c.type || 'multi-aim'),
  ];
  const types = Array.from(new Set(allTypes)).sort();

  const filtered = typeFilter === 'all'
    ? targets
    : targets.filter((t) => (t.type || 'unknown') === typeFilter);

  const handleSearchResult = useCallback((result: SearchResult | null) => {
    const viewer = (window as any).viewer;
    const Cesium = (window as any).Cesium;
    if (viewer) {
      const existing = viewer.entities.getById('_search_marker');
      if (existing) viewer.entities.remove(existing);
      viewer.scene.requestRender();
    }
    if (!result) { setSortAnchor(null); return; }
    setSortAnchor({ lon: result.lon, lat: result.lat, label: result.label });
    if (result.type === 'target' && viewer && Cesium) {
      viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(result.lon, result.lat, 5000), orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 }, duration: 1.2 });
      return;
    }
    if (result.type === 'location' && viewer && Cesium) {
      viewer.entities.add({ id: '_search_marker', name: result.label, position: Cesium.Cartesian3.fromDegrees(result.lon, result.lat, 0), cylinder: { length: 3000, topRadius: 300, bottomRadius: 300, material: Cesium.Color.fromCssColorString('#f97316').withAlpha(0.85), outline: true, outlineColor: Cesium.Color.fromCssColorString('#fb923c'), heightReference: Cesium.HeightReference.CLAMP_TO_GROUND }, label: { text: result.label, font: '11px Inter, sans-serif', fillColor: Cesium.Color.fromCssColorString('#f97316'), outlineColor: Cesium.Color.BLACK, outlineWidth: 2, style: Cesium.LabelStyle.FILL_AND_OUTLINE, verticalOrigin: Cesium.VerticalOrigin.BOTTOM, pixelOffset: new Cesium.Cartesian2(0, -20), disableDepthTestDistance: Number.POSITIVE_INFINITY } });
      viewer.scene.requestRender();
      viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(result.lon, result.lat, 80000), orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 }, duration: 1.5 });
    }
  }, []);

  const handlePaint = useCallback(() => {
    const controller = (window as any).MapToolController;
    if (!controller) return;
    controller.setTool(controller.getActiveTool() === 'paint_target' ? 'select' : 'paint_target');
  }, []);

  const handleTargetClick = useCallback((t: Target, shiftKey: boolean) => {
    selectTarget(t.id, shiftKey);
  }, [selectTarget]);

  const handleRemove = useCallback((id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const targets = (window as any)._targets as Target[];
    const viewer = (window as any).viewer;
    const lensViewer = (window as any)._lensViewer;
    const idx = targets.findIndex((t) => t.id === id);
    if (idx === -1) return;
    const t = targets.splice(idx, 1)[0] as any;
    // Remove from main viewer (by ref or by ID)
    if (t.topCone) viewer?.entities.remove(t.topCone);
    else if (viewer) { const e = viewer.entities.getById(`target_top_${id}_main`); if (e) viewer.entities.remove(e); }
    if (t.botCone) viewer?.entities.remove(t.botCone);
    else if (viewer) { const e = viewer.entities.getById(`target_bot_${id}_main`); if (e) viewer.entities.remove(e); }
    // Remove from lens viewer
    if (t.lensTopCone && lensViewer) { lensViewer.entities.remove(t.lensTopCone); lensViewer.entities.remove(t.lensBotCone); }
    else if (lensViewer) {
      const lt = lensViewer.entities.getById(`target_top_${id}_lens`); if (lt) lensViewer.entities.remove(lt);
      const lb = lensViewer.entities.getById(`target_bot_${id}_lens`); if (lb) lensViewer.entities.remove(lb);
      lensViewer.scene.requestRender();
    }
    viewer?.scene.requestRender();
    setTick((v) => v + 1);
  }, []);

  const handleCreateMAP = useCallback(() => {
    if (selectedTargetIds.length < 2) return;
    mergeTargetsIntoComplex(selectedTargetIds);
    selectTarget(null); // clear selection
    setTick((v) => v + 1);
  }, [selectedTargetIds, selectTarget]);

  const handleRemoveComplex = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const viewer = (window as any).viewer;
    const lensViewer = (window as any)._lensViewer;
    const list = getComplexTargets();
    const idx = list.findIndex((c) => c.id === id);
    if (idx < 0) return;
    const complex = list[idx];

    // Remove all sub-target diamond entities from both viewers
    if (complex) {
      complex.aimpoints.forEach((ap) => {
        // Main viewer diamonds
        if (viewer) {
          const top = viewer.entities.getById(`target_top_${ap.id}_main`);
          if (top) viewer.entities.remove(top);
          const bot = viewer.entities.getById(`target_bot_${ap.id}_main`);
          if (bot) viewer.entities.remove(bot);
        }
        // Lens viewer diamonds
        if (lensViewer) {
          const lTop = lensViewer.entities.getById(`target_top_${ap.id}_lens`);
          if (lTop) lensViewer.entities.remove(lTop);
          const lBot = lensViewer.entities.getById(`target_bot_${ap.id}_lens`);
          if (lBot) lensViewer.entities.remove(lBot);
          lensViewer.scene.requestRender();
        }
      });
    }

    list.splice(idx, 1);

    // Remove connecting line and label
    if (viewer) {
      const line = viewer.entities.getById(`_complex_line_${id}`);
      if (line) viewer.entities.remove(line);
      const label = viewer.entities.getById(`_complex_label_${id}`);
      if (label) viewer.entities.remove(label);
      viewer.scene.requestRender();
    }
    setTick((v) => v + 1);
  }, []);

  return (
    <div className="targets-panel">
      <SearchBar includeTargets onResultSelected={handleSearchResult} placeholder="Search location, target..." />

      {sortAnchor && (
        <div className="sort-anchor-label">
          Sorted by distance to <strong>{sortAnchor.label}</strong>
        </div>
      )}

      <div className="targets-toolbar">
        <HTMLSelect value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="targets-type-select">
          <option value="all">All Types ({targets.length})</option>
          {types.map((t) => (
            <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)} ({targets.filter((tg) => (tg.type || 'unknown') === t).length})</option>
          ))}
        </HTMLSelect>
        <Button small intent={isPainting ? Intent.NONE : Intent.DANGER} icon={isPainting ? undefined : 'plus'}
          className={`targets-paint-btn${isPainting ? ' painting-active' : ''}`} onClick={handlePaint}
          title={isPainting ? 'Click to stop painting' : 'Paint Target'}>
          {isPainting ? 'Painting' : 'Paint'}
        </Button>
      </div>

      {/* Complex targets (Multi Aim Point) */}
      {complexTargets.length > 0 && (
        <div className="complex-targets-section">
          <div className="section-label">Multi Aim Point Targets</div>
          {complexTargets.map((ct) => (
            <ComplexTargetCard key={ct.id} complex={ct} onRemove={handleRemoveComplex}
              onUpdate={(field, value) => { (ct as any)[field] = value; setTick((v) => v + 1); }} />
          ))}
        </div>
      )}

      {/* Simple targets */}
      {(filtered.length > 0 || complexTargets.length === 0) && (
        <div className="section-label">{complexTargets.length > 0 ? 'Simple Targets' : ''}</div>
      )}

      <div className="targets-list">
        {filtered.length === 0 ? (
          <div className="empty-state">
            {targets.length === 0 ? 'No targets. Use + to paint.' : 'No targets match filter.'}
          </div>
        ) : (
          filtered.map((t) => (
            <TargetCard key={t.id} target={t} isSelected={selectedTargetIds.includes(t.id)}
              onClick={(shiftKey) => handleTargetClick(t, shiftKey)}
              onRemove={(e) => handleRemove(t.id, e)}
              onUpdate={(field, value) => { (t as any)[field] = value; setTick((v) => v + 1); }} />
          ))
        )}
      </div>

      {/* Merge button — appears when 2+ targets selected */}
      {selectedTargetIds.length >= 2 && (
        <div className="merge-bar">
          <Button intent={Intent.WARNING} fill className="merge-btn" onClick={handleCreateMAP}
            icon="merge-columns">
            Create Multi Aim Point ({selectedTargetIds.length} targets)
          </Button>
        </div>
      )}
    </div>
  );
}

// ── Complex Target Card ──

function ComplexTargetCard({
  complex,
  onRemove,
  onUpdate,
}: {
  complex: ComplexTarget;
  onRemove: (id: string, e: React.MouseEvent) => void;
  onUpdate: (field: string, value: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editingField, setEditingField] = useState<'type' | 'description' | null>(null);
  const [editValue, setEditValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingField && inputRef.current) { inputRef.current.focus(); inputRef.current.select(); }
  }, [editingField]);

  const startEdit = useCallback((field: 'type' | 'description', e: React.MouseEvent) => {
    e.stopPropagation();
    setEditValue(field === 'type' ? (complex.type || '') : (complex.description || ''));
    setEditingField(field);
  }, [complex.type, complex.description]);

  const commitEdit = useCallback(() => {
    if (editingField) onUpdate(editingField, editValue);
    setEditingField(null);
  }, [editingField, editValue, onUpdate]);

  const handleZoom = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    const viewer = (window as any).viewer;
    const Cesium = (window as any).Cesium;
    if (!viewer || !Cesium || complex.aimpoints.length === 0) return;
    const centLon = complex.aimpoints.reduce((s, a) => s + a.lon, 0) / complex.aimpoints.length;
    const centLat = complex.aimpoints.reduce((s, a) => s + a.lat, 0) / complex.aimpoints.length;
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(centLon, centLat, 15000),
      orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 },
      duration: 1.2,
    });
  }, [complex.aimpoints]);

  return (
    <div className="complex-target-card" onClick={() => setExpanded(!expanded)}>
      <div className="complex-card-header">
        <button className="target-remove-hover" onClick={(e) => onRemove(complex.id, e)} title="Remove">&times;</button>
        <span className="complex-icon">&#x2B23;</span>
        <span className="complex-name">{complex.name}</span>
        {/* Editable type badge */}
        {editingField === 'type' ? (
          <input ref={inputRef} className="target-type-input" value={editValue}
            onChange={(e) => setEditValue(e.target.value)} onBlur={commitEdit}
            onKeyDown={(e) => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') setEditingField(null); }}
            onClick={(e) => e.stopPropagation()} placeholder="type..." />
        ) : (
          <span className="target-type-badge" onClick={(e) => startEdit('type', e)} title="Click to edit type">
            {complex.type || 'multi-aim'}
          </span>
        )}
        <span className="complex-count">{complex.aimpoints.length} pts</span>
        <button className="target-zoom-btn" onClick={handleZoom} title="Zoom to target">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
            <path d="M2 1L6 5L2 9" stroke="currentColor" strokeWidth="1.5" fill="none"/>
            <path d="M6 1L10 5L6 9" stroke="currentColor" strokeWidth="1.5" fill="none"/>
          </svg>
        </button>
      </div>

      {/* Editable description */}
      {editingField === 'description' ? (
        <input ref={inputRef} className="target-desc-input" value={editValue}
          onChange={(e) => setEditValue(e.target.value)} onBlur={commitEdit}
          onKeyDown={(e) => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') setEditingField(null); }}
          onClick={(e) => e.stopPropagation()} placeholder="Add description..." />
      ) : (
        <div className="target-desc" onClick={(e) => startEdit('description', e)}>
          {complex.description || 'Click to add description...'}
        </div>
      )}

      {/* Expanded aimpoint details */}
      {expanded && (
        <div className="complex-aimpoints">
          <div className="aimpoints-header">Aimpoints ({complex.aimpoints.length})</div>
          <table className="aimpoints-table">
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
              {complex.aimpoints.map((ap) => (
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
      )}
    </div>
  );
}

// ── Simple Target Card ──

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
    if (editingField && inputRef.current) { inputRef.current.focus(); inputRef.current.select(); }
  }, [editingField]);

  const startEdit = useCallback((field: 'type' | 'description', e: React.MouseEvent) => {
    e.stopPropagation();
    setEditValue(field === 'type' ? (target.type || '') : (target.description || ''));
    setEditingField(field);
  }, [target.type, target.description]);

  const commitEdit = useCallback(() => {
    if (editingField) onUpdate(editingField, editValue);
    setEditingField(null);
  }, [editingField, editValue, onUpdate]);

  return (
    <div className={`target-card-react${isSelected ? ' target-selected' : ''}`} onClick={(e) => onClick(e.shiftKey)}>
      <div className="target-card-header">
        <button className="target-remove-hover" onClick={onRemove} title="Remove target">&times;</button>
        <span className="target-diamond">&#x25C7;</span>
        <span className="target-id">TGT-{String(target.id).padStart(3, '0')}</span>
        {editingField === 'type' ? (
          <input ref={inputRef} className="target-type-input" value={editValue}
            onChange={(e) => setEditValue(e.target.value)} onBlur={commitEdit}
            onKeyDown={(e) => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') setEditingField(null); }}
            onClick={(e) => e.stopPropagation()} placeholder="type..." />
        ) : (
          <span className="target-type-badge" onClick={(e) => startEdit('type', e)} title="Click to edit type">
            {target.type || 'unknown'}
          </span>
        )}
      </div>
      <div className="target-coords">
        {target.lat.toFixed(4)}&deg; N &nbsp; {target.lon.toFixed(4)}&deg; E
      </div>
      {editingField === 'description' ? (
        <input ref={inputRef} className="target-desc-input" value={editValue}
          onChange={(e) => setEditValue(e.target.value)} onBlur={commitEdit}
          onKeyDown={(e) => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') setEditingField(null); }}
          onClick={(e) => e.stopPropagation()} placeholder="Add description..." />
      ) : (
        <div className="target-desc" onClick={(e) => startEdit('description', e)}>
          {target.description || 'Click to add description...'}
        </div>
      )}
      <button className="target-zoom-btn" onClick={(e) => {
        e.stopPropagation();
        const viewer = (window as any).viewer; const Cesium = (window as any).Cesium;
        if (viewer && Cesium) viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(target.lon, target.lat, 5000), orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 }, duration: 1.2 });
      }} title="Zoom to target">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
          <path d="M2 1L6 5L2 9" stroke="currentColor" strokeWidth="1.5" fill="none"/>
          <path d="M6 1L10 5L6 9" stroke="currentColor" strokeWidth="1.5" fill="none"/>
        </svg>
      </button>
    </div>
  );
}
