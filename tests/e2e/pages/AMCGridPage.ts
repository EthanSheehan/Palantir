import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object Model for the Grid-Sentinel C2 frontend.
 *
 * Centralises all selector knowledge so tests never hard-code CSS selectors
 * directly. If the HTML changes, only this file needs to be updated.
 */
export class AMCGridPage {
  readonly page: Page;

  // --- Top-level containers ---
  readonly sidebar: Locator;
  readonly cesiumContainer: Locator;
  readonly sidebarResizer: Locator;

  // --- Tab navigation ---
  readonly tabMissionBtn: Locator;
  readonly tabAssetsBtn: Locator;
  readonly tabEnemiesBtn: Locator;
  readonly tabMissionContent: Locator;
  readonly tabAssetsContent: Locator;
  readonly tabEnemiesContent: Locator;

  // --- Mission tab widgets ---
  readonly connStatus: Locator;
  readonly uavCount: Locator;
  readonly zoneCount: Locator;
  readonly assistantLog: Locator;

  // --- Control buttons ---
  readonly toggleGridBtn: Locator;
  readonly toggleWaypointsBtn: Locator;
  readonly resetQueueBtn: Locator;

  // --- Lists ---
  readonly droneListContainer: Locator;
  readonly enemyListContainer: Locator;

  // --- Tactical HUD ---
  readonly tacticalHud: Locator;
  readonly paintTargetBtn: Locator;
  readonly stopPaintingBtn: Locator;
  readonly cameraControls: Locator;
  readonly returnGlobalBtn: Locator;
  readonly decoupleCameraBtn: Locator;

  constructor(page: Page) {
    this.page = page;

    this.sidebar = page.locator('#uiPanel');
    this.cesiumContainer = page.locator('#cesiumContainer');
    this.sidebarResizer = page.locator('#sidebarResizer');

    this.tabMissionBtn = page.locator('.tab-btn[data-tab="tab-mission"]');
    this.tabAssetsBtn = page.locator('.tab-btn[data-tab="tab-drones"]');
    this.tabEnemiesBtn = page.locator('.tab-btn[data-tab="tab-enemies"]');
    this.tabMissionContent = page.locator('#tab-mission');
    this.tabAssetsContent = page.locator('#tab-drones');
    this.tabEnemiesContent = page.locator('#tab-enemies');

    this.connStatus = page.locator('#connStatus');
    this.uavCount = page.locator('#uavCount');
    this.zoneCount = page.locator('#zoneCount');
    this.assistantLog = page.locator('#assistant-log');

    this.toggleGridBtn = page.locator('#toggleGridBtn');
    this.toggleWaypointsBtn = page.locator('#toggleWaypointsBtn');
    this.resetQueueBtn = page.locator('#resetQueueBtn');

    this.droneListContainer = page.locator('#droneListContainer');
    this.enemyListContainer = page.locator('#enemyListContainer');

    this.tacticalHud = page.locator('#tacticalHud');
    this.paintTargetBtn = page.locator('#paintTargetBtn');
    this.stopPaintingBtn = page.locator('#stopPaintingBtn');
    this.cameraControls = page.locator('#cameraControls');
    this.returnGlobalBtn = page.locator('#returnGlobalBtn');
    this.decoupleCameraBtn = page.locator('#decoupleCameraBtn');
  }

  // ---------------------------------------------------------------------------
  // Navigation helpers
  // ---------------------------------------------------------------------------

  async goto() {
    await this.page.goto('/');
  }

  async switchToMissionTab() {
    await this.tabMissionBtn.click();
  }

  async switchToAssetsTab() {
    await this.tabAssetsBtn.click();
  }

  async switchToEnemiesTab() {
    await this.tabEnemiesBtn.click();
  }

  // ---------------------------------------------------------------------------
  // Assertion helpers — encapsulate common assertions so tests are readable
  // ---------------------------------------------------------------------------

  async assertConnected() {
    await expect(this.connStatus).toHaveText('Uplink Active');
    await expect(this.connStatus).toHaveClass(/connected/);
  }

  async assertDisconnected() {
    // Could be "Offline" on initial load or "Signal Lost" after disconnect
    await expect(this.connStatus).not.toHaveText('Uplink Active');
  }

  async assertMissionTabActive() {
    await expect(this.tabMissionBtn).toHaveClass(/active/);
    await expect(this.tabMissionContent).toHaveClass(/active-tab/);
  }

  async assertAssetsTabActive() {
    await expect(this.tabAssetsBtn).toHaveClass(/active/);
    await expect(this.tabAssetsContent).toHaveClass(/active-tab/);
  }

  async assertEnemiesTabActive() {
    await expect(this.tabEnemiesBtn).toHaveClass(/active/);
    await expect(this.tabEnemiesContent).toHaveClass(/active-tab/);
  }

  // ---------------------------------------------------------------------------
  // Drone list helpers
  // ---------------------------------------------------------------------------

  droneCard(id: number): Locator {
    return this.droneListContainer.locator(`[data-id="${id}"]`);
  }

  async assertDroneCardVisible(id: number) {
    await expect(this.droneCard(id)).toBeVisible();
  }

  async assertDroneCount(count: number) {
    await expect(
      this.droneListContainer.locator('.drone-card')
    ).toHaveCount(count);
  }

  // ---------------------------------------------------------------------------
  // Enemy list helpers
  // ---------------------------------------------------------------------------

  enemyCard(id: number): Locator {
    return this.enemyListContainer.locator(`[data-id="${id}"]`);
  }

  async assertEnemyCardVisible(id: number) {
    await expect(this.enemyCard(id)).toBeVisible();
  }

  async assertEnemyCount(count: number) {
    await expect(
      this.enemyListContainer.locator('.enemy-card')
    ).toHaveCount(count);
  }

  async assertEmptyEnemyState() {
    await expect(
      this.enemyListContainer.locator('.empty-state')
    ).toBeVisible();
  }

  // ---------------------------------------------------------------------------
  // Grid toggle helpers
  // ---------------------------------------------------------------------------

  async assertGridState(state: 'ON' | 'SQUARES ONLY' | 'OFF') {
    await expect(this.toggleGridBtn).toContainText(`Grid Visibility: ${state}`);
  }

  async cycleGrid() {
    await this.toggleGridBtn.click();
  }

  // ---------------------------------------------------------------------------
  // Waypoint toggle helpers
  // ---------------------------------------------------------------------------

  async assertWaypointsState(state: 'ON' | 'OFF') {
    await expect(this.toggleWaypointsBtn).toContainText(
      `All Waypoints: ${state}`
    );
  }

  async toggleWaypoints() {
    await this.toggleWaypointsBtn.click();
  }

  // ---------------------------------------------------------------------------
  // Assistant log helpers
  // ---------------------------------------------------------------------------

  async assistantMessages(): Promise<Locator> {
    return this.assistantLog.locator('.assistant-msg');
  }

  async assertAssistantMessageVisible(textFragment: string) {
    await expect(
      this.assistantLog.locator(`.assistant-msg:has-text("${textFragment}")`)
    ).toBeVisible();
  }

  // ---------------------------------------------------------------------------
  // Sidebar resize helpers
  // ---------------------------------------------------------------------------

  async getSidebarWidth(): Promise<number> {
    const box = await this.sidebar.boundingBox();
    if (!box) throw new Error('Sidebar bounding box not available');
    return box.width;
  }

  async dragSidebarResizer(deltaX: number) {
    const resizerBox = await this.sidebarResizer.boundingBox();
    if (!resizerBox) throw new Error('Resizer bounding box not available');

    const startX = resizerBox.x + resizerBox.width / 2;
    const startY = resizerBox.y + resizerBox.height / 2;

    await this.page.mouse.move(startX, startY);
    await this.page.mouse.down();
    await this.page.mouse.move(startX + deltaX, startY, { steps: 10 });
    await this.page.mouse.up();
  }
}
