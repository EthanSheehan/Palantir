import React from 'react';
import { Button, Menu, MenuItem, MenuDivider, Popover, Divider, Icon, IconName } from '@blueprintjs/core';
import { useSimStore } from '../store/SimulationStore';

/**
 * VerticalTaskbar — left-edge command rail.
 *
 * Originally lifted (in spirit) from grid-sentinel-2's `frontend/app/layout/
 * VerticalTaskbar.tsx`. Adapted to use this app's WorkspaceMode store and the
 * handful of overlays it actually owns. Sits flush against the screen edge so
 * it costs almost no horizontal real-estate.
 */

export interface VerticalTaskbarProps {
  onWorkbenchToggle: () => void;
  onChatToggle: () => void;
  onSlaToggle: () => void;
  onIntelLayerToggle: () => void;
  onAssetTaskingToggle: () => void;
  workbenchOpen?: boolean;
  chatOpen?: boolean;
  slaOpen?: boolean;
  intelLayerOpen?: boolean;
  assetTaskingOpen?: boolean;
}

function FileMenu() {
  return (
    <Menu small>
      <MenuItem icon={'document' as IconName} text="New Mission" disabled />
      <MenuItem icon={'folder-open' as IconName} text="Open Scenario" disabled />
      <MenuDivider />
      <MenuItem icon={'floppy-disk' as IconName} text="Save Checkpoint" disabled />
      <MenuItem icon={'export' as IconName} text="Export SITREP" disabled />
    </Menu>
  );
}

function ViewMenu() {
  return (
    <Menu small>
      <MenuItem icon={'eye-open' as IconName} text="Reset Camera" disabled />
      <MenuItem icon={'flag' as IconName} text="Fly To Theater Bounds" disabled />
      <MenuDivider />
      <MenuItem icon={'high-priority' as IconName} text="NVIS Mode (N)" />
      <MenuItem icon={'tint' as IconName} text="Colorblind Mode (Ctrl+Shift+A)" />
    </Menu>
  );
}

interface RailButtonProps {
  icon: IconName;
  label: string;
  active?: boolean;
  onClick: () => void;
  accent?: string;
}

function RailButton({ icon, label, active, onClick, accent = '#22d3ee' }: RailButtonProps) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2,
        background: active ? `${accent}22` : 'transparent',
        border: 'none',
        borderLeft: active ? `2px solid ${accent}` : '2px solid transparent',
        color: active ? accent : '#94a3b8',
        padding: '8px 4px',
        cursor: 'pointer',
        width: 56,
        fontSize: 8,
        fontFamily: 'monospace',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
      }}
    >
      <Icon icon={icon} size={16} color={active ? accent : '#94a3b8'} />
      <span>{label}</span>
    </button>
  );
}

export function VerticalTaskbar(props: VerticalTaskbarProps) {
  const workspaceMode = useSimStore(s => s.workspaceMode);
  const setWorkspaceMode = useSimStore(s => s.setWorkspaceMode);

  return (
    <div
      role="toolbar"
      aria-label="Workspace toolbar"
      style={{
        width: 56,
        background: 'rgba(7, 11, 17, 0.96)',
        borderRight: '1px solid rgba(255,255,255,0.08)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'stretch',
        flexShrink: 0,
      }}
    >
      {/* Top: app menus */}
      <div style={{ padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <Popover content={<FileMenu />} placement="right-start">
          <Button minimal small fill style={{ fontSize: 9, color: '#94a3b8' }} text="FILE" />
        </Popover>
        <Popover content={<ViewMenu />} placement="right-start">
          <Button minimal small fill style={{ fontSize: 9, color: '#94a3b8' }} text="VIEW" />
        </Popover>
      </div>

      <Divider style={{ margin: 0 }} />

      {/* Workspace tabs */}
      <div style={{ padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <RailButton icon={'eye-open' as IconName}      label="ISR"  active={workspaceMode === 'isr'}    onClick={() => setWorkspaceMode('isr')} />
        <RailButton icon={'send-to-map' as IconName}   label="PLAN" active={workspaceMode === 'plan'}   onClick={() => setWorkspaceMode('plan')} accent="#fbbf24" />
      </div>

      {/* Surfaces */}
      <div style={{ padding: '6px 0', flex: 1 }}>
        <RailButton icon={'target' as IconName}        label="WBENCH" active={props.workbenchOpen}     onClick={props.onWorkbenchToggle}    accent="#fbbf24" />
        <RailButton icon={'chat' as IconName}          label="AIP"    active={props.chatOpen}          onClick={props.onChatToggle}         accent="#a855f7" />
        <RailButton icon={'send-to-graph' as IconName} label="TASK"   active={props.assetTaskingOpen}  onClick={props.onAssetTaskingToggle} accent="#22d3ee" />
        <RailButton icon={'layers' as IconName}        label="LAYERS" active={props.intelLayerOpen}    onClick={props.onIntelLayerToggle}   accent="#7ED321" />
        <RailButton icon={'timeline-bar-chart' as IconName} label="SLA" active={props.slaOpen}         onClick={props.onSlaToggle}          accent="#ef4444" />
      </div>

      {/* Bottom: workspace label */}
      <div style={{
        padding: '6px 0',
        textAlign: 'center',
        fontSize: 8,
        fontFamily: 'monospace',
        letterSpacing: '0.16em',
        color: '#475569',
        borderTop: '1px solid rgba(255,255,255,0.05)',
      }}>
        GRID-SENTINEL
      </div>
    </div>
  );
}
