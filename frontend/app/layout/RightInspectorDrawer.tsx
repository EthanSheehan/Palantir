import { useEffect, useRef, useCallback } from 'react';
import { Button } from '@blueprintjs/core';
import { useAppStore } from '../store/appStore';
import { InspectorPanel } from '../panels/inspector/InspectorPanel';
import { cesiumBridge } from '../store/adapters/cesiumBridge';

/**
 * Persistent right-side inspector drawer — Gotham-style context anchor.
 * Opens automatically when an entity is selected; can be manually closed.
 * Shows selected entity/mission/alert details alongside the map.
 */
export function RightInspectorDrawer() {
  const drawerRef = useRef<HTMLDivElement>(null);
  const selection = useAppStore((s) => s.selection);
  const layout = useAppStore((s) => s.ui.layout);
  const setLayout = useAppStore((s) => s.setLayout);
  const inspectorOpen = useAppStore((s) => s.ui.inspectorOpen);
  const setInspectorOpen = useAppStore((s) => s.setInspectorOpen);

  const hasSelection = !!(selection.primaryAssetId || selection.missionId || selection.alertId);

  // Auto-open when something is selected, auto-close when cleared
  useEffect(() => {
    if (hasSelection && !inspectorOpen) {
      setInspectorOpen(true);
    }
  }, [hasSelection, inspectorOpen, setInspectorOpen]);

  // Splitter drag
  const dragState = useRef({ startX: 0, startWidth: 0 });
  const isDragging = useRef(false);

  const onSplitterMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragState.current = { startX: e.clientX, startWidth: layout.rightWidth };
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    function onMouseMove(ev: MouseEvent) {
      if (!isDragging.current) return;
      const delta = dragState.current.startX - ev.clientX;
      const newWidth = Math.max(240, Math.min(600, dragState.current.startWidth + delta));
      setLayout({ rightWidth: newWidth });
      cesiumBridge.resize();
    }

    function onMouseUp() {
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }, [layout.rightWidth, setLayout]);

  const handleClose = useCallback(() => {
    setInspectorOpen(false);
  }, [setInspectorOpen]);

  if (!inspectorOpen) return null;

  return (
    <>
      {/* Splitter handle */}
      <div
        className="ws-right-splitter"
        onMouseDown={onSplitterMouseDown}
      />
      {/* Drawer */}
      <div
        ref={drawerRef}
        className="ws-right-drawer"
        style={{ width: layout.rightWidth }}
      >
        <div className="ws-right-drawer-header">
          <span className="ws-right-drawer-title">INSPECTOR</span>
          <Button icon="cross" minimal small onClick={handleClose} title="Close inspector" />
        </div>
        <div className="ws-right-drawer-content">
          <InspectorPanel />
        </div>
      </div>
    </>
  );
}
