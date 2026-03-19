import { Tabs, Tab } from '@blueprintjs/core';
import { useSimStore } from '../store/SimulationStore';
import { MissionTab } from './mission/MissionTab';
import { AssetsTab } from './assets/AssetsTab';
import { EnemiesTab } from './enemies/EnemiesTab';

export function SidebarTabs() {
  const activeTab = useSimStore(s => s.activeTab);
  const setActiveTab = useSimStore(s => s.setActiveTab);

  return (
    <>
      <style>{`
        #sidebar-tabs { display: flex; flex-direction: column; flex: 1; overflow: hidden; }
        #sidebar-tabs > .bp5-tab-list { flex-shrink: 0; }
        #sidebar-tabs > .bp5-tab-panel { flex: 1; overflow: auto; }
      `}</style>
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
      </Tabs>
    </>
  );
}
