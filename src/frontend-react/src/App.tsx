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
import './styles/nvis.css';
import './styles/accessibility.css';

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

  // Bridge window events from Cesium hooks to WebSocket
  // Only allowlisted actions may be dispatched via the event bridge
  useEffect(() => {
    const ALLOWED_ACTIONS = new Set([
      'move_drone', 'scan_area', 'follow_target', 'paint_target',
      'intercept_target', 'intercept_enemy', 'cancel_track',
      'request_swarm', 'release_swarm', 'verify_target',
    ]);
    function onSend(e: Event) {
      const detail = (e as CustomEvent).detail;
      if (detail && typeof detail === 'object' && ALLOWED_ACTIONS.has(detail.action)) {
        sendMessage(detail);
      }
    }
    window.addEventListener('palantir:send', onSend);
    return () => window.removeEventListener('palantir:send', onSend);
  }, [sendMessage]);

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
    }

    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <WebSocketContext.Provider value={{ sendMessage }}>
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        {/* Top banners */}
        <DemoBanner />
        {/* Kill chain ribbon */}
        <KillChainRibbon />
        {/* Header bar with connection status */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          padding: '2px 12px',
          background: 'rgba(15, 20, 30, 0.95)',
          borderBottom: '1px solid rgba(255,255,255,0.05)',
          flexShrink: 0,
          height: 24,
        }}>
          <ConnectionStatus />
        </div>

        <div style={{ display: 'flex', flexDirection: 'row', flex: 1, overflow: 'hidden' }}>
          <Sidebar />
          <div style={{ flex: 1, minWidth: 0, position: 'relative', background: '#1c2127' }}>
            <CesiumContainer />
            <MapLegend visible={legendVisible} />
          </div>
        </div>
      </div>
      <DetailMapDialog />
      <CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <GlobalAlertCenter visible={alertCenterVisible} onToggle={() => setAlertCenterVisible(v => !v)} />
      <FloatingStrikeBoard visible={strikeBoardVisible} onToggle={() => setStrikeBoardVisible(v => !v)} />
    </WebSocketContext.Provider>
  );
}
