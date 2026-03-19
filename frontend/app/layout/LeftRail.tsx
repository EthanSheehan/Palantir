import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '../store/appStore';
import type { LeftPanelTab } from '../store/appStore';
import { cesiumBridge } from '../store/adapters/cesiumBridge';
import { timelineBridge } from '../store/adapters/timelineBridge';
import { AlertsPanel } from '../panels/alerts/AlertsPanel';
import { InspectorPanel } from '../panels/inspector/InspectorPanel';
import { AssetsPanel } from '../panels/assets/AssetsPanel';
import { MissionsPanel } from '../panels/missions/MissionsPanel';
import { CommandsPanel } from '../panels/commands/CommandsPanel';
import { MacrogridPanel } from '../panels/macrogrid/MacrogridPanel';

/** Tabs migrated to React. 'targets' remains legacy (tight Cesium coupling in app.js). */
const REACT_PANELS: Partial<Record<LeftPanelTab, () => JSX.Element>> = {
  missions: MissionsPanel,
  assets: AssetsPanel,
  inspector: InspectorPanel,
  alerts: AlertsPanel,
  commands: CommandsPanel,
  macrogrid: MacrogridPanel,
};

interface TabDef {
  id: LeftPanelTab;
  label: string;
  icon: string;
  contentId: string;
}

const TABS: TabDef[] = [
  { id: 'missions',  label: 'MISSION',  icon: 'M', contentId: 'tab-mission' },
  { id: 'targets' as LeftPanelTab, label: 'TARGETS', icon: '\u25C7', contentId: 'tab-targets' },
  { id: 'assets',    label: 'ASSETS',   icon: 'A', contentId: 'tab-drones' },
  { id: 'inspector', label: 'OPS',      icon: 'O', contentId: 'tab-ops' },
  { id: 'alerts',    label: 'ALERTS',   icon: '!', contentId: 'tab-alerts' },
  { id: 'macrogrid', label: 'GRID',     icon: 'G', contentId: 'tab-grid' },
  { id: 'commands',  label: 'CMDS',     icon: 'C', contentId: 'tab-commands' },
];

/**
 * Floating left rail panel with tabs.
 * Hosts legacy panel content by reparenting tab-content divs.
 */
export function LeftRail() {
  const railRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const activeTab = useAppStore((s) => s.ui.leftPanelTab);
  const setLeftPanelTab = useAppStore((s) => s.setLeftPanelTab);
  const layout = useAppStore((s) => s.ui.layout);
  const setLayout = useAppStore((s) => s.setLayout);

  const [isDragging, setIsDragging] = useState(false);

  // Reparent legacy tab content divs into this component
  useEffect(() => {
    if (!contentRef.current) return;
    const uiPanel = document.getElementById('uiPanel');
    if (!uiPanel) return;

    // Move all .tab-content divs from the legacy uiPanel
    const tabContents = uiPanel.querySelectorAll('.tab-content');
    tabContents.forEach((div) => {
      contentRef.current!.appendChild(div);
    });

    // Ensure commands tab exists
    let commandsTab = document.getElementById('tab-commands');
    if (!commandsTab) {
      commandsTab = document.createElement('div');
      commandsTab.id = 'tab-commands';
      commandsTab.className = 'tab-content';
      commandsTab.innerHTML = '<h3 style="color:#94a3b8;padding:12px;">Command History</h3><div class="empty-state">No commands issued yet.</div>';
      contentRef.current!.appendChild(commandsTab);
    }

    // Hide the legacy uiPanel since we've taken its content
    uiPanel.style.display = 'none';
  }, []);

  // Show/hide tab content based on active tab
  useEffect(() => {
    if (!contentRef.current) return;
    const tabDef = TABS.find((t) => t.id === activeTab);
    const activeContentId = tabDef?.contentId;

    contentRef.current.querySelectorAll('.tab-content').forEach((div) => {
      if (div.id === activeContentId) {
        div.classList.add('active-tab');
      } else {
        div.classList.remove('active-tab');
      }
    });
  }, [activeTab]);

  // Splitter drag handling
  const dragState = useRef({ startX: 0, startWidth: 0 });

  const onSplitterMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragState.current = { startX: e.clientX, startWidth: layout.leftWidth };
    setIsDragging(true);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [layout.leftWidth]);

  useEffect(() => {
    if (!isDragging) return;

    function onMouseMove(e: MouseEvent) {
      const delta = e.clientX - dragState.current.startX;
      const newWidth = Math.max(240, Math.min(800, dragState.current.startWidth + delta));
      setLayout({ leftWidth: newWidth, leftCollapsed: false });
      cesiumBridge.resize();
      timelineBridge.resize();
    }

    function onMouseUp() {
      setIsDragging(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
  }, [isDragging, setLayout]);

  return (
    <>
      <div
        ref={railRef}
        className={`ws-left-rail${layout.leftCollapsed ? ' ws-collapsed' : ''}${isDragging ? ' ws-dragging' : ''}`}
        style={{ width: layout.leftCollapsed ? undefined : layout.leftWidth }}
      >
        {/* Tab bar */}
        <div className="ws-tab-bar">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={`ws-tab-btn${activeTab === tab.id ? ' ws-active' : ''}`}
              onClick={() => setLeftPanelTab(tab.id)}
            >
              <span className="ws-tab-icon">{tab.icon}</span>
              <span className="ws-tab-label">{tab.label}</span>
            </button>
          ))}
        </div>

        {/* React panels for migrated tabs */}
        {Object.entries(REACT_PANELS).map(([tabId, Panel]) => (
          <div
            key={tabId}
            className="ws-tab-content"
            style={{ display: activeTab === tabId ? 'block' : 'none' }}
          >
            <Panel />
          </div>
        ))}
        {/* Legacy content for unmigrated tabs */}
        <div
          ref={contentRef}
          className="ws-tab-content"
          style={{ display: activeTab in REACT_PANELS ? 'none' : 'block' }}
        />
      </div>

      {/* Splitter handle */}
      <div
        className={`ws-left-splitter${isDragging ? ' ws-active' : ''}`}
        style={{ left: layout.leftCollapsed ? 56 : layout.leftWidth + 8 }}
        onMouseDown={onSplitterMouseDown}
        onDoubleClick={() => setLayout({ leftCollapsed: !layout.leftCollapsed })}
      />
    </>
  );
}
