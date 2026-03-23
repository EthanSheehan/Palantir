import { Menu, MenuItem, MenuDivider, Popover, Button, Divider } from '@blueprintjs/core';
import './VerticalTaskbar.css';

export type WorkspaceTab = 'plan' | 'isr';


function FileMenu() {
  return (
    <Menu small className="taskbar-menu">
      <MenuItem icon="document" text="New" />
      <MenuItem icon="folder-open" text="Open" />
      <MenuDivider />
      <MenuItem icon="floppy-disk" text="Save" />
      <MenuItem icon="export" text="Save As" />
    </Menu>
  );
}

function ViewMenu() {
  return (
    <Menu small className="taskbar-menu">
      <MenuItem icon="eye-open" text="View options coming soon" disabled />
    </Menu>
  );
}

export function VerticalTaskbar({
  activeTab,
  onTabChange,
}: {
  activeTab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
}) {
  return (
    <div className="ws-vertical-taskbar bp5-dark">
      {/* App-level menus */}
      <div className="taskbar-section">
        <Popover content={<FileMenu />} placement="right-start" portalClassName="taskbar-portal">
          <Button minimal text="File" className="taskbar-btn" />
        </Popover>
        <Popover content={<ViewMenu />} placement="right-start" portalClassName="taskbar-portal">
          <Button minimal text="View" className="taskbar-btn" />
        </Popover>
      </div>

      <Divider className="taskbar-divider" />

      {/* Workspace tabs */}
      <div className="taskbar-section">
        <Button
          minimal
          text="ISR"
          className={`taskbar-btn taskbar-tab${activeTab === 'isr' ? ' taskbar-tab-active' : ''}`}
          onClick={() => onTabChange('isr')}
        />
        <Button
          minimal
          text="Plan"
          className={`taskbar-btn taskbar-tab${activeTab === 'plan' ? ' taskbar-tab-active' : ''}`}
          onClick={() => onTabChange('plan')}
        />
      </div>
    </div>
  );
}
