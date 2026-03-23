import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { HTMLSelect, Button, Intent } from '@blueprintjs/core';
import { SearchBar } from '../../components/SearchBar';
import type { SearchResult } from '../../components/SearchBar';
import { useAppStore } from '../../store/appStore';
import type { Aimpoint as StoreAimpoint, Target as StoreTarget } from '../../store/types';
import * as api from '../../services/apiClient';
import './TargetsPanel.css';

// ── Data Models (legacy compat wrappers) ──

interface Target {
  id: number | string;
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
    id: number | string;
    lon: number;
    lat: number;
    type: string;
    description: string;
  }>;
  createdAt: number;
}

/** Read aimpoints from Zustand store, falling back to legacy window array */
function getTargets(): Target[] {
  const storeAimpoints = useAppStore.getState().aimpoints;
  const fromStore = Object.values(storeAimpoints);
  if (fromStore.length > 0) {
    return fromStore.map((a) => ({
      id: a.id,
      lon: a.lon,
      lat: a.lat,
      type: a.type || 'unknown',
      description: a.description || '',
    }));
  }
  // Legacy fallback
  return ((window as any)._targets as Target[]) || [];
}

/** Read targets from Zustand store, falling back to legacy window array */
function getComplexTargets(): ComplexTarget[] {
  const storeTargets = useAppStore.getState().targets;
  const storeAimpoints = useAppStore.getState().aimpoints;
  const fromStore = Object.values(storeTargets);
  if (fromStore.length > 0) {
    return fromStore.map((t) => ({
      id: t.id,
      name: t.name,
      type: t.type,
      description: t.description,
      aimpoints: t.aimpoint_ids
        .map((aid) => storeAimpoints[aid])
        .filter(Boolean)
        .map((a) => ({
          id: a.id,
          lon: a.lon,
          lat: a.lat,
          type: a.type || 'unknown',
          description: a.description || '',
        })),
      createdAt: t.created_at ? new Date(t.created_at).getTime() : Date.now(),
    }));
  }
  // Legacy fallback
  if (!(window as any)._complexTargets) (window as any)._complexTargets = [];
  return (window as any)._complexTargets as ComplexTarget[];
}

/** Generate a display name like APT-001 based on creation order */
function _aimpointDisplayName(id: number | string): string {
  if (typeof id === 'number') return `APT-${String(id).padStart(3, '0')}`;
  try {
    const aimpoints = useAppStore.getState().aimpoints;
    const sorted = Object.values(aimpoints)
      .sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''));
    const idx = sorted.findIndex((a) => a.id === id);
    if (idx >= 0) return `APT-${String(idx + 1).padStart(3, '0')}`;
  } catch { /* fallback below */ }
  return `APT-${String(id).slice(4, 8)}`;
}

/** Merge selected aimpoints into a target via backend API */
async function mergeTargetsIntoComplex(targetIds: (number | string)[]): Promise<ComplexTarget | null> {
  const aptIds = targetIds.map(String);
  if (aptIds.length < 2) return null;

  try {
    // Create target on backend
    const target = await api.createTarget({
      name: '',  // Backend will auto-name or we can generate
      aimpoint_ids: aptIds,
    });

    // The backend event will update the store; build a local ComplexTarget for immediate rendering
    const storeAimpoints = useAppStore.getState().aimpoints;
    const complex: ComplexTarget = {
      id: target.id,
      name: target.name,
      type: target.type,
      description: target.description,
      aimpoints: target.aimpoint_ids
        .map((aid) => storeAimpoints[aid])
        .filter(Boolean)
        .map((a) => ({
          id: a.id,
          lon: a.lon,
          lat: a.lat,
          type: a.type || 'unknown',
          description: a.description || '',
        })),
      createdAt: Date.now(),
    };

    // Add connecting lines on the globe
    addComplexTargetVisualization(complex);
    return complex;
  } catch (err) {
    console.error('Failed to create target:', err);
    return null;
  }
}

/** Generate a small orange diamond icon for billboard fallback at distance */
let _orangeDiamondIcon: string | null = null;
function _makeOrangeDiamondIcon(): string {
  if (_orangeDiamondIcon) return _orangeDiamondIcon;
  const canvas = document.createElement('canvas');
  canvas.width = 16;
  canvas.height = 16;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#f97316';
  ctx.beginPath();
  ctx.moveTo(8, 0);
  ctx.lineTo(16, 8);
  ctx.lineTo(8, 16);
  ctx.lineTo(0, 8);
  ctx.closePath();
  ctx.fill();
  _orangeDiamondIcon = canvas.toDataURL();
  return _orangeDiamondIcon;
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

  // Compute centroid and coverage radius
  const centLon = complex.aimpoints.reduce((s, a) => s + a.lon, 0) / complex.aimpoints.length;
  const centLat = complex.aimpoints.reduce((s, a) => s + a.lat, 0) / complex.aimpoints.length;

  // Coverage radius: max distance from centroid to any aimpoint (in degrees → meters)
  let maxDistDeg = 0;
  complex.aimpoints.forEach((ap) => {
    const d = Math.sqrt((ap.lon - centLon) ** 2 + (ap.lat - centLat) ** 2);
    if (d > maxDistDeg) maxDistDeg = d;
  });
  const coverageKm = maxDistDeg * 111; // rough deg→km

  // Diamond size proportional to coverage, clamped
  const diamondRadius = Math.max(60, Math.min(200, coverageKm * 2));
  const diamondHalfH = diamondRadius * 1.4;
  const diamondAlt = 500 + coverageKm * 5; // higher up than simple targets

  // Sample terrain at centroid
  let terrainH = 0;
  const carto = Cesium.Cartographic.fromDegrees(centLon, centLat);
  const globe = viewer.scene.globe;
  if (globe) { const h = globe.getHeight(carto); if (h !== undefined) terrainH = h; }
  const baseAlt = terrainH + diamondAlt;

  const color = Cesium.Color.fromCssColorString('#f97316').withAlpha(0.7);
  const outline = Cesium.Color.fromCssColorString('#fdba74');

  // Upper cone (tip up)
  viewer.entities.add({
    id: `_complex_diamond_top_${complex.id}`,
    position: Cesium.Cartesian3.fromDegrees(centLon, centLat, baseAlt + diamondHalfH / 2),
    cylinder: {
      length: diamondHalfH, topRadius: 0, bottomRadius: diamondRadius,
      material: color, outline: true, outlineColor: outline,
      outlineWidth: 1, numberOfVerticalLines: 0,
    },
  });

  // Lower cone (tip down)
  const botPos = Cesium.Cartesian3.fromDegrees(centLon, centLat, baseAlt - diamondHalfH / 2);
  const flipped = Cesium.Transforms.headingPitchRollQuaternion(
    botPos, new Cesium.HeadingPitchRoll(0, Math.PI, 0));
  viewer.entities.add({
    id: `_complex_diamond_bot_${complex.id}`,
    position: botPos,
    orientation: flipped,
    cylinder: {
      length: diamondHalfH, topRadius: 0, bottomRadius: diamondRadius,
      material: color, outline: true, outlineColor: outline,
      outlineWidth: 1, numberOfVerticalLines: 0,
    },
  });

  // Label next to the diamond
  viewer.entities.add({
    id: `_complex_label_${complex.id}`,
    position: Cesium.Cartesian3.fromDegrees(centLon, centLat, baseAlt + diamondHalfH + 50),
    label: {
      text: complex.name,
      font: '12px Inter, sans-serif',
      fillColor: Cesium.Color.fromCssColorString('#f97316'),
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 2,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
      pixelOffset: new Cesium.Cartesian2(0, -4),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
      scaleByDistance: new Cesium.NearFarScalar(1000, 1.0, 500000, 0.4),
    },
    // Billboard for adaptive sizing — keeps diamond visible when zoomed out
    billboard: {
      image: _makeOrangeDiamondIcon(),
      width: 16,
      height: 16,
      verticalOrigin: Cesium.VerticalOrigin.CENTER,
      scaleByDistance: new Cesium.NearFarScalar(5000, 0.0, 50000, 1.0),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
  });

  // Vertical line from ground to diamond
  viewer.entities.add({
    id: `_complex_stalk_${complex.id}`,
    polyline: {
      positions: [
        Cesium.Cartesian3.fromDegrees(centLon, centLat, terrainH),
        Cesium.Cartesian3.fromDegrees(centLon, centLat, baseAlt),
      ],
      width: 1,
      material: Cesium.Color.fromCssColorString('#f97316').withAlpha(0.3),
    },
  });

  viewer.scene.requestRender();
}

/** Manage Cesium highlight rings for selected targets (simple and MAP) */
export function updateTargetHighlights(targetIds: (number | string)[]) {
  const viewer = (window as any).viewer;
  const Cesium = (window as any).Cesium;
  if (!viewer || !Cesium) return;

  const toRemove = viewer.entities.values.filter((e: any) => e.id?.startsWith('_target_highlight_'));
  toRemove.forEach((e: any) => viewer.entities.remove(e));

  if (targetIds.length === 0) { viewer.scene.requestRender(); return; }

  const store = (window as any).__zustandStore;
  const storeAimpoints = store?.getState?.()?.aimpoints || {};
  const storeTargets = store?.getState?.()?.targets || {};
  const legacyTargets = (window as any)._targets as Target[] | undefined;
  const legacyComplex = (window as any)._complexTargets as ComplexTarget[] | undefined;
  const radius = 800;
  const segments = 48;

  targetIds.forEach((tid, idx) => {
    let lon: number | undefined, lat: number | undefined;
    const tidStr = String(tid);

    // Check store aimpoints first (apt_xxx IDs)
    if (storeAimpoints[tidStr]) {
      lon = storeAimpoints[tidStr].lon;
      lat = storeAimpoints[tidStr].lat;
    }
    // Check store targets (tgt_xxx IDs) — highlight at centroid
    else if (storeTargets[tidStr]) {
      const tgt = storeTargets[tidStr];
      const apts = tgt.aimpoint_ids.map((aid: string) => storeAimpoints[aid]).filter(Boolean);
      if (apts.length > 0) {
        lon = apts.reduce((s: number, a: any) => s + a.lon, 0) / apts.length;
        lat = apts.reduce((s: number, a: any) => s + a.lat, 0) / apts.length;
      }
    }
    // Legacy fallback: numeric ID simple target
    else if (typeof tid === 'number') {
      const target = legacyTargets?.find((t) => t.id === tid);
      if (target) { lon = target.lon; lat = target.lat; }
    }
    // Legacy fallback: complex target string ID
    else {
      const ct = legacyComplex?.find((c) => c.id === tidStr);
      if (ct && ct.aimpoints.length > 0) {
        lon = ct.aimpoints.reduce((s, a) => s + a.lon, 0) / ct.aimpoints.length;
        lat = ct.aimpoints.reduce((s, a) => s + a.lat, 0) / ct.aimpoints.length;
      }
    }
    if (lon === undefined || lat === undefined) return;

    let terrainH = 0;
    const carto = Cesium.Cartographic.fromDegrees(lon, lat);
    const globe = viewer.scene.globe;
    if (globe) { const h = globe.getHeight(carto); if (h !== undefined) terrainH = h; }

    const color = idx === 0
      ? Cesium.Color.fromCssColorString('#f97316').withAlpha(0.8)
      : Cesium.Color.fromCssColorString('#fb923c').withAlpha(0.6);

    const hlLon = lon, hlLat = lat;
    viewer.entities.add({
      id: `_target_highlight_${tid}`,
      polyline: {
        positions: new Cesium.CallbackProperty(() => {
          const center = Cesium.Cartesian3.fromDegrees(hlLon, hlLat, terrainH);
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
  const setPinnedTarget = useAppStore((s) => s.setPinnedTarget);

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
    selectTarget(String(t.id), shiftKey);
  }, [selectTarget]);

  const handleRemove = useCallback((id: number | string, e: React.MouseEvent) => {
    e.stopPropagation();
    const viewer = (window as any).viewer;
    const lensViewer = (window as any)._lensViewer;

    // Remove Cesium entities
    if (viewer) {
      const top = viewer.entities.getById(`target_top_${id}_main`); if (top) viewer.entities.remove(top);
      const bot = viewer.entities.getById(`target_bot_${id}_main`); if (bot) viewer.entities.remove(bot);
      viewer.scene.requestRender();
    }
    if (lensViewer) {
      const lt = lensViewer.entities.getById(`target_top_${id}_lens`); if (lt) lensViewer.entities.remove(lt);
      const lb = lensViewer.entities.getById(`target_bot_${id}_lens`); if (lb) lensViewer.entities.remove(lb);
      lensViewer.scene.requestRender();
    }

    // Delete via API (string ID = backend aimpoint)
    if (typeof id === 'string' && id.startsWith('apt_')) {
      api.deleteAimpoint(id).catch(console.error);
    } else {
      // Legacy numeric ID — remove from window._targets
      const targets = (window as any)._targets as Target[];
      if (targets) {
        const idx = targets.findIndex((t) => t.id === id);
        if (idx >= 0) targets.splice(idx, 1);
      }
    }
    setTick((v) => v + 1);
  }, []);

  const handlePinTarget = useCallback((id: number | string, name: string, lon: number, lat: number) => {
    const current = useAppStore.getState().pinnedTarget;
    if (current && current.id === id) {
      setPinnedTarget(null); // unpin if already pinned
    } else {
      setPinnedTarget({ id, name, lon, lat });
      // Switch to assets tab
      useAppStore.getState().setLeftPanelTab('assets');
    }
  }, [setPinnedTarget]);

  const handleCreateMAP = useCallback(() => {
    if (selectedTargetIds.length < 2) return;
    mergeTargetsIntoComplex(selectedTargetIds).then(() => {
      selectTarget(null); // clear selection
      setTick((v) => v + 1);
    });
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

    // Remove from legacy list if present
    list.splice(idx, 1);

    // Remove all complex target Cesium entities
    if (viewer) {
      ['_complex_line_', '_complex_label_', '_complex_diamond_top_', '_complex_diamond_bot_', '_complex_stalk_'].forEach((prefix) => {
        const e = viewer.entities.getById(`${prefix}${id}`);
        if (e) viewer.entities.remove(e);
      });
      viewer.scene.requestRender();
    }

    // Delete via API if it's a backend target
    if (id.startsWith('tgt_')) {
      api.deleteTarget(id).catch(console.error);
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
          <div className="section-label">Targets</div>
          {complexTargets.map((ct) => (
            <ComplexTargetCard key={ct.id} complex={ct}
              isSelected={selectedTargetIds.includes(ct.id)}
              onClick={(shiftKey) => selectTarget(ct.id, shiftKey)}
              onRemove={handleRemoveComplex}
              onPin={() => {
                if (ct.aimpoints.length === 0) return;
                const lon = ct.aimpoints.reduce((s, a) => s + a.lon, 0) / ct.aimpoints.length;
                const lat = ct.aimpoints.reduce((s, a) => s + a.lat, 0) / ct.aimpoints.length;
                const current = useAppStore.getState().pinnedTarget;
                if (current && current.id === ct.id) {
                  setPinnedTarget(null);
                } else {
                  setPinnedTarget({ id: ct.id, name: ct.name, description: ct.description, lon, lat, aimpoints: ct.aimpoints });
                  useAppStore.getState().setLeftPanelTab('assets');
                }
              }}
              onUpdate={(field, value) => { (ct as any)[field] = value; setTick((v) => v + 1); }} />
          ))}
        </div>
      )}

      {/* Simple targets */}
      {(filtered.length > 0 || complexTargets.length === 0) && (
        <div className="section-label">{complexTargets.length > 0 ? 'Aimpoints' : ''}</div>
      )}

      <div className="targets-list">
        {filtered.length === 0 ? (
          <div className="empty-state">
            {targets.length === 0 ? 'No aimpoints. Use + to paint.' : 'No aimpoints match filter.'}
          </div>
        ) : (
          filtered.map((t) => (
            <TargetCard key={t.id} target={t} isSelected={selectedTargetIds.includes(t.id)}
              onClick={(shiftKey) => handleTargetClick(t, shiftKey)}
              onRemove={(e) => handleRemove(t.id, e)}
              onPin={() => handlePinTarget(String(t.id), _aimpointDisplayName(t.id), t.lon, t.lat)}
              onUpdate={(field, value) => { (t as any)[field] = value; setTick((v) => v + 1); }} />
          ))
        )}
      </div>

      {/* Merge button — appears when 2+ targets selected */}
      {selectedTargetIds.length >= 2 && (
        <div className="merge-bar">
          <Button intent={Intent.WARNING} fill className="merge-btn" onClick={handleCreateMAP}
            icon="merge-columns">
            Create Target ({selectedTargetIds.length} aimpoints)
          </Button>
        </div>
      )}
    </div>
  );
}

// ── Complex Target Card ──

function ComplexTargetCard({
  complex,
  isSelected,
  onClick,
  onRemove,
  onPin,
  onUpdate,
}: {
  complex: ComplexTarget;
  isSelected: boolean;
  onClick: (shiftKey: boolean) => void;
  onRemove: (id: string, e: React.MouseEvent) => void;
  onPin: () => void;
  onUpdate: (field: string, value: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editingAimpoints, setEditingAimpoints] = useState(false);
  const [repaintingApId, setRepaintingApId] = useState<number | null>(null);
  const [highlightedApId, setHighlightedApId] = useState<number | null>(null);
  const [ctxMenu, setCtxMenu] = useState<{ x: number; y: number } | null>(null);
  const [editingField, setEditingField] = useState<'type' | 'description' | null>(null);
  const [editValue, setEditValue] = useState('');
  const [, setApTick] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingField && inputRef.current) { inputRef.current.focus(); inputRef.current.select(); }
  }, [editingField]);

  // Collapse when deselected
  useEffect(() => {
    if (!isSelected) { setExpanded(false); setEditingAimpoints(false); }
  }, [isSelected]);

  // Highlight individual aimpoint on globe
  useEffect(() => {
    const viewer = (window as any).viewer;
    const Cesium = (window as any).Cesium;
    if (!viewer || !Cesium) return;

    // Remove previous aimpoint highlight
    const old = viewer.entities.getById('_ap_highlight');
    if (old) viewer.entities.remove(old);

    if (highlightedApId === null) { viewer.scene.requestRender(); return; }

    const ap = complex.aimpoints.find((a) => a.id === highlightedApId);
    if (!ap) return;

    let terrainH = 0;
    const carto = Cesium.Cartographic.fromDegrees(ap.lon, ap.lat);
    const globe = viewer.scene.globe;
    if (globe) { const h = globe.getHeight(carto); if (h !== undefined) terrainH = h; }

    const radius = 500;
    const segments = 48;
    viewer.entities.add({
      id: '_ap_highlight',
      polyline: {
        positions: (() => {
          const center = Cesium.Cartesian3.fromDegrees(ap.lon, ap.lat, terrainH);
          const transform = Cesium.Transforms.eastNorthUpToFixedFrame(center);
          const pts: any[] = [];
          for (let i = 0; i <= segments; i++) {
            const angle = (i / segments) * Math.PI * 2;
            const local = new Cesium.Cartesian3(Math.cos(angle) * radius, Math.sin(angle) * radius, 0);
            pts.push(Cesium.Matrix4.multiplyByPoint(transform, local, new Cesium.Cartesian3()));
          }
          return pts;
        })(),
        width: 2.5,
        material: Cesium.Color.fromCssColorString('#f97316').withAlpha(0.8),
        clampToGround: true,
      },
    });
    viewer.scene.requestRender();

    return () => {
      const e = viewer.entities.getById('_ap_highlight');
      if (e) { viewer.entities.remove(e); viewer.scene.requestRender(); }
    };
  }, [highlightedApId, complex.aimpoints]);

  // Clear aimpoint highlight when card collapses or editing stops
  useEffect(() => {
    if (!expanded || !editingAimpoints) setHighlightedApId(null);
  }, [expanded, editingAimpoints]);

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

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setCtxMenu({ x: e.clientX, y: e.clientY });
  }, []);

  // Close context menu on outside click
  useEffect(() => {
    if (!ctxMenu) return;
    const close = () => setCtxMenu(null);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [ctxMenu]);

  // Clear repainting state if tool changes away
  useEffect(() => {
    if (repaintingApId === null) return;
    const controller = (window as any).MapToolController;
    if (!controller?.onToolChange) return;
    const cb = (toolId: string) => {
      if (toolId !== 'repaint_aimpoint') setRepaintingApId(null);
    };
    controller.onToolChange(cb);
    // No unsub available — cb is lightweight and self-guards via repaintingApId check
  }, [repaintingApId]);

  const handleRepaintAimpoint = useCallback((ap: ComplexTarget['aimpoints'][0]) => {
    const repaintFn = (window as any)._repaintAimpoint;
    if (!repaintFn) return;

    // Already repainting this one? Cancel.
    if (repaintingApId === ap.id) {
      setRepaintingApId(null);
      repaintFn(null);
      return;
    }

    setRepaintingApId(ap.id);

    repaintFn(ap.id, ({ lon, lat }: { lon: number; lat: number }) => {
      // Update aimpoint coordinates in-place
      ap.lon = lon;
      ap.lat = lat;

      // Refresh complex target visualization (connecting lines, centroid diamond)
      const viewer = (window as any).viewer;
      if (viewer) {
        ['_complex_line_', '_complex_label_', '_complex_diamond_top_', '_complex_diamond_bot_', '_complex_stalk_'].forEach((prefix: string) => {
          const e = viewer.entities.getById(`${prefix}${complex.id}`);
          if (e) viewer.entities.remove(e);
        });
        addComplexTargetVisualization(complex);
      }

      // Done
      setRepaintingApId(null);
      setApTick((v) => v + 1);
    });
  }, [complex, repaintingApId]);

  const updateAimpoint = useCallback((apId: number, field: string, value: string) => {
    const ap = complex.aimpoints.find((a) => a.id === apId);
    if (ap) { (ap as any)[field] = value; setApTick((v) => v + 1); }
  }, [complex.aimpoints]);

  return (
    <div className={`complex-target-card${isSelected ? ' target-selected' : ''}`}
      onClick={(e) => { onClick(e.shiftKey); setExpanded(!expanded); }}
      onContextMenu={handleContextMenu}>

      {/* Right-click context menu — rendered via portal to avoid overflow clipping */}
      {ctxMenu && createPortal(
        <div className="target-ctx-menu" style={{ position: 'fixed', left: ctxMenu.x, top: ctxMenu.y, zIndex: 9999 }}
          onClick={(e) => e.stopPropagation()}>
          <button className="target-ctx-item" onClick={() => { setEditingAimpoints(!editingAimpoints); setExpanded(true); setCtxMenu(null); }}>
            {editingAimpoints ? 'Stop Editing Aimpoints' : 'Edit Aimpoints'}
          </button>
        </div>,
        document.body
      )}
      <button className="target-pin-btn" onClick={(e) => { e.stopPropagation(); onPin(); }} title="Select Target">
        <svg width="12" height="12" viewBox="0 0 12 12" stroke="currentColor" strokeWidth="2" fill="none"><line x1="6" y1="1" x2="6" y2="11"/><line x1="1" y1="6" x2="11" y2="6"/></svg>
      </button>
      <div className="complex-card-header">
        <button className="target-remove-hover" onClick={(e) => onRemove(complex.id, e)} title="Remove">&times;</button>
        <span className="complex-icon">&#x2B23;</span>
        <span className="complex-name">{complex.name}</span>
        {/* Editable type badge — only editable when selected */}
        {editingField === 'type' ? (
          <input ref={inputRef} className="target-type-input" value={editValue}
            onChange={(e) => setEditValue(e.target.value)} onBlur={commitEdit}
            onKeyDown={(e) => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') setEditingField(null); }}
            onClick={(e) => e.stopPropagation()} placeholder="type..." />
        ) : (
          <span className={`target-type-badge${isSelected ? ' editable' : ''}`}
            onClick={isSelected ? (e) => startEdit('type', e) : undefined}
            title={isSelected ? 'Click to edit type' : undefined}>
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

      {/* Centroid coordinates — always visible, above description (consistent with simple targets) */}
      {complex.aimpoints.length > 0 && (
        <div className="target-coords">
          {(complex.aimpoints.reduce((s, a) => s + a.lat, 0) / complex.aimpoints.length).toFixed(4)}&deg; N &nbsp; {(complex.aimpoints.reduce((s, a) => s + a.lon, 0) / complex.aimpoints.length).toFixed(4)}&deg; E
        </div>
      )}

      {/* Editable description — always shows placeholder, only editable when selected */}
      {editingField === 'description' ? (
        <input ref={inputRef} className="target-desc-input" value={editValue}
          onChange={(e) => setEditValue(e.target.value)} onBlur={commitEdit}
          onKeyDown={(e) => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') setEditingField(null); }}
          onClick={(e) => e.stopPropagation()} placeholder="Add description..." />
      ) : (
        <div className={`target-desc${isSelected ? ' editable' : ''}`}
          onClick={isSelected ? (e) => startEdit('description', e) : undefined}>
          {complex.description || 'Click to add description...'}
        </div>
      )}

      {/* Aimpoints count — always visible */}
      <div className="complex-aimpoints-label">Aimpoints ({complex.aimpoints.length})</div>

      {/* Expanded aimpoint details */}
      {expanded && (
        <div className="complex-aimpoints" onClick={(e) => e.stopPropagation()}>
          <table className="aimpoints-table" style={{ marginTop: 0 }}>
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Lat</th>
                <th>Lon</th>
                <th>Description</th>
                {editingAimpoints && <th></th>}
              </tr>
            </thead>
            <tbody>
              {complex.aimpoints.map((ap) => (
                <tr key={ap.id}>
                  <td className={`ap-id ap-id-clickable${highlightedApId === ap.id ? ' ap-id-active' : ''}`}
                    onClick={() => setHighlightedApId(highlightedApId === ap.id ? null : ap.id)}
                    title="Click to highlight on globe">AP-{String(ap.id).padStart(3, '0')}</td>
                  {editingAimpoints ? (
                    <>
                      <td><input className="ap-edit-input" value={ap.type} onChange={(e) => updateAimpoint(ap.id, 'type', e.target.value)} /></td>
                      <td className="ap-coord">{ap.lat.toFixed(4)}</td>
                      <td className="ap-coord">{ap.lon.toFixed(4)}</td>
                      <td><input className="ap-edit-input ap-edit-desc" value={ap.description} onChange={(e) => updateAimpoint(ap.id, 'description', e.target.value)} placeholder="description..." /></td>
                      <td><button className={`ap-repaint-btn${repaintingApId === ap.id ? ' repainting-active' : ''}`} onClick={() => handleRepaintAimpoint(ap)} title={repaintingApId === ap.id ? 'Click to cancel' : 'Repaint on globe'}>&#x21BB;</button></td>
                    </>
                  ) : (
                    <>
                      <td className="ap-type">{ap.type}</td>
                      <td className="ap-coord">{ap.lat.toFixed(4)}</td>
                      <td className="ap-coord">{ap.lon.toFixed(4)}</td>
                      <td className="ap-desc">{ap.description || '\u2014'}</td>
                    </>
                  )}
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
  onPin,
  onUpdate,
}: {
  target: Target;
  isSelected: boolean;
  onClick: (shiftKey: boolean) => void;
  onRemove: (e: React.MouseEvent) => void;
  onPin: () => void;
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
      <button className="target-pin-btn" onClick={(e) => { e.stopPropagation(); onPin(); }} title="Select Target">
        <svg width="12" height="12" viewBox="0 0 12 12" stroke="currentColor" strokeWidth="2" fill="none"><line x1="6" y1="1" x2="6" y2="11"/><line x1="1" y1="6" x2="11" y2="6"/></svg>
      </button>
      <div className="target-card-header">
        <button className="target-remove-hover" onClick={onRemove} title="Remove target">&times;</button>
        <span className="target-diamond">&#x25C7;</span>
        <span className="target-id">{_aimpointDisplayName(target.id)}</span>
        {editingField === 'type' ? (
          <input ref={inputRef} className="target-type-input" value={editValue}
            onChange={(e) => setEditValue(e.target.value)} onBlur={commitEdit}
            onKeyDown={(e) => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') setEditingField(null); }}
            onClick={(e) => e.stopPropagation()} placeholder="type..." />
        ) : (
          <span className={`target-type-badge${isSelected ? ' editable' : ''}`}
            onClick={isSelected ? (e) => startEdit('type', e) : undefined}
            title={isSelected ? 'Click to edit type' : undefined}>
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
        <div className={`target-desc${isSelected ? ' editable' : ''}`}
          onClick={isSelected ? (e) => startEdit('description', e) : undefined}>
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
