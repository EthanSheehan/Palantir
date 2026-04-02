import { Page } from '@playwright/test';

/**
 * WebSocket mock helper for AMC-Grid C2 E2E tests.
 *
 * Intercepts the WebSocket connection at ws://localhost:8000/ws and replaces
 * it with a controllable mock. This allows tests to:
 *   - Verify the IDENTIFY handshake is sent by the frontend
 *   - Push synthetic state payloads and assert UI reactions
 *   - Test reconnect logic by simulating close events
 *
 * Usage:
 *   const mock = await createWsMock(page);
 *   await page.goto('/');
 *   await mock.waitForIdentify();
 *   await mock.sendState(buildState({ uavs: [uav(1)], targets: [], zones: [] }));
 */

export interface MockUav {
  id: number;
  lon: number;
  lat: number;
  mode: 'idle' | 'serving' | 'repositioning';
}

export interface MockTarget {
  id: number;
  lon: number;
  lat: number;
  type: 'SAM' | 'TEL' | 'TRUCK' | 'CP';
  detected: boolean;
}

export interface MockZone {
  x_idx: number;
  y_idx: number;
  lon: number;
  lat: number;
  imbalance: number;
  width?: number;
  height?: number;
}

export interface MockState {
  uavs: MockUav[];
  targets: MockTarget[];
  zones: MockZone[];
  flows: unknown[];
}

export interface WsMock {
  /** Wait for the frontend to send the IDENTIFY handshake. */
  waitForIdentify(): Promise<{ type: string; client_type: string }>;
  /** Push a full state update to the frontend (wraps in {type:"state", data:...}). */
  sendState(state: MockState): Promise<void>;
  /** Push an ASSISTANT_MESSAGE to the frontend. */
  sendAssistantMessage(text: string, timestamp?: string): Promise<void>;
  /** Simulate a WebSocket close so reconnect logic triggers. */
  closeConnection(): Promise<void>;
  /** All messages received from the frontend. */
  receivedMessages: string[];
}

/**
 * Builds a minimal valid state fixture.
 * Merge overrides on top of the defaults.
 */
export function buildState(overrides: Partial<MockState> = {}): MockState {
  return {
    uavs: [],
    targets: [],
    zones: [],
    flows: [],
    ...overrides,
  };
}

export function mockUav(id: number, overrides: Partial<MockUav> = {}): MockUav {
  return {
    id,
    lon: 25.0 + id * 0.1,
    lat: 44.0 + id * 0.05,
    mode: 'idle',
    ...overrides,
  };
}

export function mockTarget(
  id: number,
  overrides: Partial<MockTarget> = {}
): MockTarget {
  return {
    id,
    lon: 26.5 + id * 0.2,
    lat: 45.0 + id * 0.1,
    type: 'SAM',
    detected: true,
    ...overrides,
  };
}

export function mockZone(
  xIdx: number,
  yIdx: number,
  overrides: Partial<MockZone> = {}
): MockZone {
  return {
    x_idx: xIdx,
    y_idx: yIdx,
    lon: 23.0 + xIdx * 0.192,
    lat: 43.5 + yIdx * 0.094,
    imbalance: 0,
    width: 0.192,
    height: 0.094,
    ...overrides,
  };
}

/**
 * Installs the WebSocket mock on the page BEFORE navigation so the page
 * script's `new WebSocket(...)` call is intercepted immediately.
 *
 * Playwright's `page.routeWebSocket` intercepts at the network layer; the
 * page-side JS sees a fully functional WebSocket object.
 */
export async function createWsMock(page: Page): Promise<WsMock> {
  const receivedMessages: string[] = [];
  let activeSend: ((data: string) => Promise<void>) | null = null;
  let activeClose: (() => Promise<void>) | null = null;

  const identifyPromise = new Promise<{ type: string; client_type: string }>(
    (resolve, reject) => {
      const timeout = setTimeout(
        () => reject(new Error('Timed out waiting for IDENTIFY message')),
        15000
      );

      page.routeWebSocket('ws://localhost:8000/ws', (ws) => {
        clearTimeout(timeout);

        // Wire up send so tests can push messages to the frontend
        activeSend = async (data: string) => {
          ws.send(data);
        };

        activeClose = async () => {
          ws.close();
        };

        ws.onMessage((message) => {
          const text = typeof message === 'string' ? message : String(message);
          receivedMessages.push(text);

          try {
            const payload = JSON.parse(text) as {
              type?: string;
              client_type?: string;
            };
            if (payload.type === 'IDENTIFY') {
              resolve(payload as { type: string; client_type: string });
            }
          } catch {
            // Not JSON — ignore
          }
        });
      });
    }
  );

  return {
    receivedMessages,

    async waitForIdentify() {
      return identifyPromise;
    },

    async sendState(state: MockState) {
      if (!activeSend) {
        throw new Error(
          'WebSocket not yet connected — call waitForIdentify() first'
        );
      }
      await activeSend(JSON.stringify({ type: 'state', data: state }));
    },

    async sendAssistantMessage(text: string, timestamp?: string) {
      if (!activeSend) {
        throw new Error(
          'WebSocket not yet connected — call waitForIdentify() first'
        );
      }
      await activeSend(
        JSON.stringify({
          type: 'ASSISTANT_MESSAGE',
          text,
          severity: 'INFO',
          timestamp: timestamp ?? new Date().toISOString().slice(11, 19),
        })
      );
    },

    async closeConnection() {
      if (!activeClose) {
        throw new Error('WebSocket not yet connected');
      }
      await activeClose();
    },
  };
}
