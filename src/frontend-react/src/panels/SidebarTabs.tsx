import { Tabs, Tab } from '@blueprintjs/core';
import { useSimStore } from '../store/SimulationStore';
import { MissionTab } from './mission/MissionTab';
import { AssetsTab } from './assets/AssetsTab';
import { EnemiesTab } from './enemies/EnemiesTab';

const TABS_CSS = `
  #sidebar-tabs.bp5-tabs { display: flex; flex-direction: column; flex: 1; overflow: hidden; min-height: 0; }
  #sidebar-tabs > .bp5-tab-list { flex-shrink: 0; }
  #sidebar-tabs .bp5-tab-panel[role="tabpanel"] { flex: 1; overflow-y: auto; min-height: 0; display: flex; flex-direction: column; }
`;

let styleInjected = false;
function injectStyle() {
  if (styleInjected) return;
  const el = document.createElement('style');
  el.textContent = TABS_CSS;
  document.head.appendChild(el);
  styleInjected = true;
}

export function SidebarTabs() {
  const activeTab = useSimStore(s => s.activeTab);
  const setActiveTab = useSimStore(s => s.setActiveTab);

  injectStyle();

  return (
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
  );
}
