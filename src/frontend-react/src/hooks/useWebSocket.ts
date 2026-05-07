import { useEffect, useCallback, useRef } from 'react';
import { useSimStore } from '../store/SimulationStore';
import { AssistantMessage, HitlUpdate } from '../store/types';

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const store = useSimStore;

  const sendMessage = useCallback((msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  useEffect(() => {
    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let isMounted = true;

    function connect() {
      if (!isMounted) return;
      const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${scheme}://${window.location.hostname}:8000/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        store.getState().setConnected(true);
        ws.send(JSON.stringify({ type: 'IDENTIFY', client_type: 'DASHBOARD' }));
        ws.send(JSON.stringify({ action: 'subscribe', feeds: ['INTEL_FEED', 'COMMAND_FEED'] }));
      };

      ws.onclose = () => {
        store.getState().setConnected(false);
        if (isMounted) {
          reconnectTimeout = setTimeout(connect, 1000);
        }
      };

      ws.onmessage = (event) => {
        let payload: any;
        try {
          payload = JSON.parse(event.data);
        } catch (err) {
          console.error('WebSocket: malformed message', err);
          return;
        }

        if (payload.type === 'ASSISTANT_MESSAGE') {
          const msg: AssistantMessage = {
            timestamp: payload.timestamp || new Date().toLocaleTimeString(),
            text: payload.text,
            severity: (payload.severity || 'INFO').toUpperCase() as 'INFO' | 'WARNING' | 'CRITICAL',
          };
          store.getState().addAssistantMessage(msg);
          return;
        }

        if (payload.type === 'FEED_EVENT') {
          const feed = payload.feed;
          if (feed === 'INTEL_FEED') {
            store.getState().addIntelEvent(payload.data);
          } else if (feed === 'COMMAND_FEED') {
            store.getState().addCommandEvent(payload.data);
          }
          return;
        }

        if (payload.type === 'FEED_HISTORY') {
          const feed = payload.feed;
          if (feed === 'INTEL_FEED') {
            store.getState().setIntelEvents(payload.events);
          } else if (feed === 'COMMAND_FEED') {
            store.getState().setCommandEvents(payload.events);
          }
          return;
        }

        if (payload.type === 'HITL_UPDATE') {
          const update = payload as HitlUpdate & { coas?: any[]; entry_id?: string };
          if (update.coas && update.entry_id) {
            store.getState().setCachedCoas(update.entry_id, update.coas);
          }
          return;
        }

        if (payload.type === 'state') {
          store.getState().setSimData(payload.data);
          return;
        }

        // ----- Maven-parity panel responses -----
        // The new panels (AIPChatPanel, AssetTaskingDrawer, ModelHubBadge,
        // ActivityTimeline, SLADashboard) listen for grid-sentinel:* CustomEvents
        // rather than reading store fields, so the WebSocket layer just
        // re-emits typed messages onto the window.
        const dispatch = (name: string, detail: unknown) =>
          window.dispatchEvent(new CustomEvent(name, { detail }));

        if (payload.type === 'AGENT_RESPONSE') {
          dispatch('grid-sentinel:agent-response', payload);
          return;
        }
        if (payload.type === 'TASKING_RESPONSE') {
          dispatch('grid-sentinel:tasking-response', payload);
          return;
        }
        if (payload.type === 'PROVIDER_STATUS') {
          dispatch('grid-sentinel:provider-status', payload);
          return;
        }
        if (payload.type === 'TARGET_HISTORY') {
          dispatch('grid-sentinel:target-history', payload);
          return;
        }
        if (payload.type === 'SLA_SNAPSHOT') {
          dispatch('grid-sentinel:sla-snapshot', payload);
          return;
        }
        if (payload.type === 'EFFECTOR_ACK') {
          dispatch('grid-sentinel:effector-ack', payload);
          return;
        }
        if (payload.type === 'PERSONA_UPDATED') {
          dispatch('grid-sentinel:persona-updated', payload);
          return;
        }
        if (payload.type === 'THEATER_SWAPPED') {
          dispatch('grid-sentinel:theater-swapped', payload);
          return;
        }
      };
    }

    connect();

    return () => {
      isMounted = false;
      clearTimeout(reconnectTimeout);
      wsRef.current?.close();
    };
  }, []);

  return { sendMessage };
}
