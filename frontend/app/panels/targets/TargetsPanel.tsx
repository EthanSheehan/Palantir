import { useCallback, useEffect, useRef, useState } from 'react';
import { SearchBar } from '../../components/SearchBar';
import type { SearchResult } from '../../components/SearchBar';
import './TargetsPanel.css';

/**
 * TargetsPanel — wraps the legacy targets tab content with a React search bar.
 * The legacy target list, paint button, and filters are reparented from #tab-targets.
 */
export function TargetsPanel() {
  const legacyRef = useRef<HTMLDivElement>(null);
  const [sortAnchor, setSortAnchor] = useState<{ lon: number; lat: number; label: string } | null>(null);

  // Reparent legacy #tab-targets content into this component
  useEffect(() => {
    if (!legacyRef.current) return;
    const legacyTab = document.getElementById('tab-targets');
    if (!legacyTab) return;

    // Move all children from legacy tab into our container
    while (legacyTab.firstChild) {
      legacyRef.current.appendChild(legacyTab.firstChild);
    }
  }, []);

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

    // If it's a target result, fly to it
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

    // Location: place marker and fly
    if (result.type === 'location' && viewer && Cesium) {
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

      {/* Legacy target content reparented here */}
      <div ref={legacyRef} className="targets-legacy-content" />
    </div>
  );
}
