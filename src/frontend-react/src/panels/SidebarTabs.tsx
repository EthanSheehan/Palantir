import React from 'react';
import { Tabs, Tab } from '@blueprintjs/core';
import { useSimStore } from '../store/SimulationStore';
import { MissionTab } from './mission/MissionTab';
import { AssetsTab } from './assets/AssetsTab';
import { EnemiesTab } from './enemies/EnemiesTab';

export function SidebarTabs() {
  const activeTab = useSimStore(s => s.activeTab);
  const setActiveTab = useSimStore(s => s.setActiveTab);

  const panelStyle: React.CSSProperties = {
    overflow: 'auto',
    flex: 1,
  };

  return (
    <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <Tabs
        id="sidebar-tabs"
        animate
        renderActiveTabPanelOnly
        selectedTabId={activeTab}
        onChange={(newTab: string) => setActiveTab(newTab)}
      >
        <Tab
          id="mission"
          title="MISSION"
          panel={<div style={panelStyle}><MissionTab /></div>}
        />
        <Tab
          id="assets"
          title="ASSETS"
          panel={<div style={panelStyle}><AssetsTab /></div>}
        />
        <Tab
          id="enemies"
          title="ENEMIES"
          panel={<div style={panelStyle}><EnemiesTab /></div>}
        />
      </Tabs>
    </div>
  );
}
