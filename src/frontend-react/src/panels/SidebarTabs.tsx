import React from 'react';
import { Tabs, Tab } from '@blueprintjs/core';
import { MissionTab } from './mission/MissionTab';

export function SidebarTabs() {
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
          panel={<MissionTab />}
          style={{ flex: 1, overflow: 'auto' }}
        />
        <Tab
          id="assets"
          title="ASSETS"
          panel={<div style={{ padding: 16, color: '#94a3b8' }}>No UAVs Active.</div>}
        />
        <Tab
          id="enemies"
          title="ENEMIES"
          panel={<div style={{ padding: 16, color: '#94a3b8' }}>No hostile entities detected.</div>}
        />
      </Tabs>
    </div>
  );
}
