import React, { createContext, useContext, useEffect, useState } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { CesiumContainer } from './cesium/CesiumContainer';
import { Sidebar } from './panels/Sidebar';
import { DemoBanner } from './overlays/DemoBanner';
import { DetailMapDialog } from './cesium/DetailMapDialog';
import { KillChainRibbon } from './overlays/KillChainRibbon';
import { ConnectionStatus } from './components/ConnectionStatus';
import { MapLegend } from './overlays/MapLegend';
import { CommandPalette } from './overlays/CommandPalette';
import { GlobalAlertCenter } from './overlays/GlobalAlertCenter';
import { FloatingStrikeBoard } from './overlays/FloatingStrikeBoard';
import { BottomTimelineDock } from './overlays/BottomTimelineDock';
import { ClassificationBanner } from './overlays/ClassificationBanner';
import { TargetWorkbench } from './panels/TargetWorkbench';
import { AssetTaskingDrawer } from './panels/AssetTaskingDrawer';
import { ActivityTimeline } from './panels/ActivityTimeline';
import { SLADashboard } from './panels/SLADashboard';
import { IntelLayerPanel } from './overlays/IntelLayerPanel';
import { AIPChatPanel } from './overlays/AIPChatPanel';
import { ModelHubBadge } from './components/ModelHubBadge';
import { VerticalTaskbar } from './components/VerticalTaskbar';
import { TwoPersonConcurrencePanel } from './panels/TwoPersonConcurrencePanel';
import { useSimStore } from './store/SimulationStore';
import './styles/nvis.css';
import './styles/accessibility.css';
import './styles/glass.css';

// Expose sendMessage to the entire app via context
export const WebSocketContext = createContext<{ sendMessage: (msg: object) => void }>({
  sendMessage: () => {},
});

export function useSendMessage() {
  return useContext(WebSocketContext).sendMessage;
}

export default function App() {
  const { sendMessage } = useWebSocket();
  const [legendVisible, setLegendVisible] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [alertCenterVisible, setAlertCenterVisible] = useState(false);
  const [strikeBoardVisible, setStrikeBoardVisible] = useState(false);
  const [timelineVisible, setTimelineVisible] = useState(false);
  // New Maven-parity panels
  const [workbenchVisible, setWorkbenchVisible] = useState(true);
  const [chatVisible, setChatVisible] = useState(false);
  const [slaVisible, setSlaVisible] = useState(false);
  const [intelLayerVisible, setIntelLayerVisible] = useState(true);
  const [taskingVisible, setTaskingVisible] = useState(false);
  const [activityTimelineVisible, setActivityTimelineVisible] = useState(false);
  const [tpcVisible, setTpcVisible] = useState(false);

  // Bridge window events from Cesium hooks to WebSocket
  // Only allowlisted actions may be dispatched via the event bridge
  useEffect(() => {
    const ALLOWED_ACTIONS = new Set([
      'move_drone', 'scan_area', 'follow_target', 'paint_target',
      'intercept_target', 'intercept_enemy', 'cancel_track',
      'request_swarm', 'release_swarm', 'verify_target', 'spike',
    ]);
    function onSend(e: Event) {
      const detail = (e as CustomEvent).detail;
      if (detail && typeof detail === 'object' && ALLOWED_ACTIONS.has(detail.action)) {
        sendMessage(detail);
      }
    }
    window.addEventListener('grid-sentinel:send', onSend);
    return () => window.removeEventListener('grid-sentinel:send', onSend);
  }, [sendMessage]);

  // Handle drone target assignment: select the drone and switch to ENEMIES tab
  useEffect(() => {
    function onAssignTarget(e: Event) {
      const { droneId } = (e as CustomEvent<{ droneId: number }>).detail;
      useSimStore.getState().selectDrone(droneId);
      useSimStore.getState().setActiveTab('enemies');
    }
    window.addEventListener('grid-sentinel:assignTarget', onAssignTarget);
    return () => window.removeEventListener('grid-sentinel:assignTarget', onAssignTarget);
  }, []);

  // Keyboard shortcuts: N = NVIS, Ctrl+Shift+A = accessibility, L = legend
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea') return;

      if (e.key === 'n' || e.key === 'N') {
        document.body.classList.toggle('nvis-mode');
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'a' || e.key === 'A')) {
        e.preventDefault();
        document.body.classList.toggle('colorblind-mode');
        return;
      }

      if (e.key === 'l' || e.key === 'L') {
        setLegendVisible(v => !v);
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setPaletteOpen(v => !v);
        return;
      }

      if (e.key === 'g' || e.key === 'G') {
        setAlertCenterVisible(v => !v);
        return;
      }

      if (e.key === 'b' || e.key === 'B') {
        setStrikeBoardVisible(v => !v);
        return;
      }

      if (e.key === 't' || e.key === 'T') {
        setTimelineVisible(v => !v);
        return;
      }

      if (e.key === 'i' || e.key === 'I') {
        const store = useSimStore.getState();
        store.setWorkspaceMode(store.workspaceMode === 'isr' ? 'plan' : 'isr');
        return;
      }

      // New panel hotkeys: W=workbench, /=AIP chat, S=SLA, A=tasking, H=history
      if (e.key === 'w' || e.key === 'W') { setWorkbenchVisible(v => !v); return; }
      if (e.key === '/') { e.preventDefault(); setChatVisible(v => !v); return; }
      if (e.key === 's' || e.key === 'S') { setSlaVisible(v => !v); return; }
      if (e.key === 'a' || e.key === 'A') {
        if (!(e.ctrlKey || e.metaKey || e.shiftKey)) { setTaskingVisible(v => !v); return; }
      }
      if (e.key === 'h' || e.key === 'H') { setActivityTimelineVisible(v => !v); return; }
      // 2 = two-person concurrence panel (FedRAMP-High control)
      if (e.key === '2' && !(e.ctrlKey || e.metaKey || e.shiftKey)) {
        setTpcVisible(v => !v); return;
      }
    }

    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <WebSocketContext.Provider value={{ sendMessage }}>
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        {/* Top classification banner — reads persona from store, recolors live */}
        <ClassificationBanner position="top" />
        {/* Demo banner */}
        <DemoBanner />
        {/* Kill chain ribbon */}
        <KillChainRibbon />
        {/* Header bar with connection status + LLM model hub */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '2px 12px',
          background: 'rgba(15, 20, 30, 0.95)',
          borderBottom: '1px solid rgba(255,255,255,0.05)',
          flexShrink: 0,
          height: 26,
        }}>
          <ModelHubBadge />
          <ConnectionStatus />
        </div>

        <div style={{ display: 'flex', flexDirection: 'row', flex: 1, overflow: 'hidden' }}>
          <VerticalTaskbar
            onWorkbenchToggle={() => setWorkbenchVisible(v => !v)}
            onChatToggle={() => setChatVisible(v => !v)}
            onSlaToggle={() => setSlaVisible(v => !v)}
            onIntelLayerToggle={() => setIntelLayerVisible(v => !v)}
            onAssetTaskingToggle={() => setTaskingVisible(v => !v)}
            workbenchOpen={workbenchVisible}
            chatOpen={chatVisible}
            slaOpen={slaVisible}
            intelLayerOpen={intelLayerVisible}
            assetTaskingOpen={taskingVisible}
          />
          <Sidebar />
          <div style={{ flex: 1, minWidth: 0, position: 'relative', background: '#1c2127' }}>
            <CesiumContainer />
            <MapLegend visible={legendVisible} />
            <IntelLayerPanel visible={intelLayerVisible} />
          </div>
        </div>

        {/* Bottom classification banner */}
        <ClassificationBanner position="bottom" />
      </div>
      <DetailMapDialog />
      <CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <GlobalAlertCenter visible={alertCenterVisible} onToggle={() => setAlertCenterVisible(v => !v)} />
      <FloatingStrikeBoard visible={strikeBoardVisible} onToggle={() => setStrikeBoardVisible(v => !v)} />
      <BottomTimelineDock visible={timelineVisible} onToggle={() => setTimelineVisible(v => !v)} />
      <TargetWorkbench visible={workbenchVisible} onToggle={() => setWorkbenchVisible(v => !v)} />
      <AssetTaskingDrawer visible={taskingVisible} onClose={() => setTaskingVisible(false)} />
      <ActivityTimeline visible={activityTimelineVisible} onClose={() => setActivityTimelineVisible(false)} />
      <SLADashboard visible={slaVisible} onClose={() => setSlaVisible(false)} />
      <AIPChatPanel visible={chatVisible} onClose={() => setChatVisible(false)} />
      <TwoPersonConcurrencePanel visible={tpcVisible} onClose={() => setTpcVisible(false)} />
    </WebSocketContext.Provider>
  );
}
