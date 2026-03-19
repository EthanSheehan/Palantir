import React, { createContext, useContext, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { CesiumContainer } from './cesium/CesiumContainer';
import { Sidebar } from './panels/Sidebar';
import { DemoBanner } from './overlays/DemoBanner';
import { DetailMapDialog } from './cesium/DetailMapDialog';

// Expose sendMessage to the entire app via context
export const WebSocketContext = createContext<{ sendMessage: (msg: object) => void }>({
  sendMessage: () => {},
});

export function useSendMessage() {
  return useContext(WebSocketContext).sendMessage;
}

export default function App() {
  const { sendMessage } = useWebSocket();

  // Bridge window events from Cesium hooks to WebSocket
  useEffect(() => {
    function onSend(e: Event) {
      sendMessage((e as CustomEvent).detail);
    }
    window.addEventListener('palantir:send', onSend);
    return () => window.removeEventListener('palantir:send', onSend);
  }, [sendMessage]);

  return (
    <WebSocketContext.Provider value={{ sendMessage }}>
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        <DemoBanner />
        <div style={{ display: 'flex', flexDirection: 'row', flex: 1, overflow: 'hidden' }}>
          <Sidebar />
          <div style={{ flex: 1, minWidth: 0, position: 'relative', background: '#1c2127' }}>
            <CesiumContainer />
          </div>
        </div>
      </div>
      <DetailMapDialog />
    </WebSocketContext.Provider>
  );
}
