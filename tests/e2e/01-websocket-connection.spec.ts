import { test, expect } from './fixtures/base';
import { buildState, mockUav, mockZone } from './helpers/ws-mock';

/**
 * CRITICAL: WebSocket Connection & Handshake
 *
 * Validates that the frontend correctly:
 *   1. Opens a WebSocket connection to ws://localhost:8000/ws
 *   2. Sends an IDENTIFY handshake with client_type "DASHBOARD"
 *   3. Updates the connection status indicator on connect
 *   4. Shows "Signal Lost" and schedules reconnect on disconnect
 *   5. Processes incoming state payloads and updates counters
 */

test.describe('WebSocket Connection', () => {
  test('sends IDENTIFY handshake immediately after connecting', async ({
    amcGridPage,
    wsMock,
  }) => {
    const identPayload = await wsMock.waitForIdentify();

    expect(identPayload.type).toBe('IDENTIFY');
    expect(identPayload.client_type).toBe('DASHBOARD');
  });

  test('shows "Uplink Active" status once WebSocket opens', async ({
    amcGridPage,
    wsMock,
  }) => {
    // Wait for the handshake — this also confirms the WS opened successfully
    await wsMock.waitForIdentify();

    await amcGridPage.assertConnected();
  });

  test('status is offline/disconnected before connection opens', async ({
    page,
  }) => {
    // Navigate WITHOUT the WS mock to observe the initial offline state
    await page.goto('/');
    const connStatus = page.locator('#connStatus');
    // Initially shows "Offline" (set in HTML) before WS opens
    await expect(connStatus).not.toHaveText('Uplink Active');
  });

  test('shows "Signal Lost" when WebSocket closes', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();
    await amcGridPage.assertConnected();

    await wsMock.closeConnection();

    await expect(amcGridPage.connStatus).toHaveText('Signal Lost', {
      timeout: 5000,
    });
    await expect(amcGridPage.connStatus).toHaveClass(/disconnected/);
  });

  test('updates UAV and zone counters from state payload', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    const state = buildState({
      uavs: [mockUav(1), mockUav(2), mockUav(3)],
      zones: [
        mockZone(0, 0),
        mockZone(1, 0),
        mockZone(2, 0),
        mockZone(0, 1),
        mockZone(1, 1),
      ],
    });

    await wsMock.sendState(state);

    await expect(amcGridPage.uavCount).toHaveText('3', { timeout: 5000 });
    await expect(amcGridPage.zoneCount).toHaveText('5', { timeout: 5000 });
  });

  test('ignores malformed/unknown message types gracefully', async ({
    amcGridPage,
    wsMock,
    page,
  }) => {
    await wsMock.waitForIdentify();

    // The page should not throw or crash on unexpected message types
    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));

    // We access the underlying page route to send raw data —
    // simulate unknown type by injecting via page.evaluate
    await page.evaluate(() => {
      // This exercises the ws.onmessage handler with an unknown type
      const event = new MessageEvent('message', {
        data: JSON.stringify({ type: 'UNKNOWN_TYPE', foo: 'bar' }),
      });
      // @ts-ignore: accessing internal ws variable for test
      if (window.__ws) window.__ws.dispatchEvent(event);
    });

    // Status should still be connected (no crash)
    await amcGridPage.assertConnected();

    // No uncaught errors from the unknown payload
    expect(
      errors.filter((e) => !e.includes('Cesium') && !e.includes('Ion'))
    ).toHaveLength(0);
  });
});
