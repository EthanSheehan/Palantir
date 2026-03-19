import React, { createContext, useContext } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { CesiumContainer } from './cesium/CesiumContainer';
import { Sidebar } from './panels/Sidebar';

// Expose sendMessage to the entire app via context
export const WebSocketContext = createContext<{ sendMessage: (msg: object) => void }>({
  sendMessage: () => {},
});

export function useSendMessage() {
  return useContext(WebSocketContext).sendMessage;
}

export default function App() {
  const { sendMessage } = useWebSocket();

  return (
    <WebSocketContext.Provider value={{ sendMessage }}>
      <div style={{ display: 'flex', flexDirection: 'row', height: '100vh', overflow: 'hidden' }}>
        <Sidebar />
        <div style={{ flex: 1, minWidth: 0, position: 'relative', background: '#1c2127' }}>
          <CesiumContainer />
        </div>
      </div>
    </WebSocketContext.Provider>
  );
}
