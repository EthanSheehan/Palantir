import { useEffect, useRef } from 'react';
import { Tabs, Tab } from '@blueprintjs/core';
import { useSimStore } from '../store/SimulationStore';
import { MissionTab } from './mission/MissionTab';
import { AssetsTab } from './assets/AssetsTab';
import { EnemiesTab } from './enemies/EnemiesTab';
import { AssessmentTab } from './assessment/AssessmentTab';

export function SidebarTabs() {
  const activeTab = useSimStore(s => s.activeTab);
  const setActiveTab = useSimStore(s => s.setActiveTab);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    // Style the BP5 tabs wrapper (class component, no style prop)
    const tabs = el.querySelector<HTMLElement>('.bp5-tabs');
    if (tabs) {
      tabs.style.display = 'flex';
      tabs.style.flexDirection = 'column';
      tabs.style.flex = '1';
      tabs.style.minHeight = '0';
    }
    // Style the active tab panel
    const panel = el.querySelector<HTMLElement>('[role="tabpanel"]');
    if (panel) {
      panel.style.flex = '1';
      panel.style.overflowY = 'auto';
      panel.style.minHeight = '0';
      panel.style.marginTop = '0';
    }
  }, [activeTab]);

  return (
    <div
      ref={containerRef}
      style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' }}
    >
      <Tabs
        id="sidebar-tabs"
        animate
        renderActiveTabPanelOnly
        selectedTabId={activeTab}
        onChange={(newTab: string) => setActiveTab(newTab)}
      >
        <Tab id="mission" title="MISSION" panel={<MissionTab />} />
        <Tab id="assets" title="ASSETS" panel={<AssetsTab />} />
        <Tab id="enemies" title="ENEMIES" panel={<EnemiesTab />} />
        <Tab id="assess" title="ASSESS" panel={<AssessmentTab />} />
      </Tabs>
    </div>
  );
}
