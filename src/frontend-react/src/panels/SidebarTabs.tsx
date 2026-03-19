import React from 'react';
import { Tabs, Tab } from '@blueprintjs/core';
import { MissionTab } from './mission/MissionTab';
import { AssetsTab } from './assets/AssetsTab';
import { EnemiesTab } from './enemies/EnemiesTab';

export function SidebarTabs() {
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
        defaultSelectedTabId="mission"
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
