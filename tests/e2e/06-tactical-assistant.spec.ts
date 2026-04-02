import { test, expect } from './fixtures/base';

/**
 * CRITICAL: Tactical AIP Assistant Widget
 *
 * Validates that AI assistant messages pushed via WebSocket appear in the
 * assistant log widget on the MISSION tab.
 */

test.describe('Tactical AIP Assistant', () => {
  test('assistant widget is visible on MISSION tab', async ({
    amcGridPage,
  }) => {
    await expect(amcGridPage.assistantLog).toBeVisible();
  });

  test('shows system initialization message on load', async ({
    amcGridPage,
  }) => {
    // The HTML pre-populates "AIP System Initialized..."
    await expect(
      amcGridPage.assistantLog.locator('.assistant-msg.system')
    ).toContainText('AIP System Initialized');
  });

  test('ASSISTANT_MESSAGE from WebSocket appears in log', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendAssistantMessage(
      'NEW CONTACT: SAM localized at 26.1234, 44.5678'
    );

    await amcGridPage.assertAssistantMessageVisible('NEW CONTACT: SAM');
  });

  test('multiple assistant messages accumulate in log', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendAssistantMessage('Contact Alpha detected');
    await wsMock.sendAssistantMessage('Contact Bravo detected');
    await wsMock.sendAssistantMessage('Contact Charlie detected');

    await amcGridPage.assertAssistantMessageVisible('Contact Alpha detected');
    await amcGridPage.assertAssistantMessageVisible('Contact Bravo detected');
    await amcGridPage.assertAssistantMessageVisible('Contact Charlie detected');
  });

  test('assistant messages render with correct CSS class', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendAssistantMessage('Test operational message');

    // New messages should use 'assistant-msg' class
    const newMsg = amcGridPage.assistantLog.locator(
      '.assistant-msg:has-text("Test operational message")'
    );
    await expect(newMsg).toBeVisible({ timeout: 5000 });
  });

  test('assistant log messages include timestamp text', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    const ts = '14:35:22';
    await wsMock.sendAssistantMessage('Threat vector updated', ts);

    // The app.js template includes the timestamp in message text:
    // `[${msg.timestamp}] ${msg.text}`
    const logEl = amcGridPage.assistantLog;
    await expect(logEl).toContainText(ts, { timeout: 5000 });
  });

  test('assistant widget header shows correct title', async ({
    amcGridPage,
  }) => {
    await expect(
      amcGridPage.page.locator('.widget-header')
    ).toContainText('TACTICAL AIP ASSISTANT');
  });

  test('assistant messages remain after tab switch', async ({
    amcGridPage,
    wsMock,
  }) => {
    await wsMock.waitForIdentify();

    await wsMock.sendAssistantMessage('Persistent message test');

    await amcGridPage.assertAssistantMessageVisible('Persistent message test');

    // Switch away and back
    await amcGridPage.switchToAssetsTab();
    await amcGridPage.switchToMissionTab();

    // Message should still be there
    await amcGridPage.assertAssistantMessageVisible('Persistent message test');
  });
});
