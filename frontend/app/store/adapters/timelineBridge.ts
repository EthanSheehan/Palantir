/**
 * Narrow imperative bridge between React/Zustand and the Timeline canvas.
 * All communication from React to Timeline goes through these methods.
 */

function getTimelinePanel(): any {
  return (window as any).TimelinePanel;
}

export const timelineBridge = {
  /** Update which assets have lanes in the timeline */
  setSelectedAssets(ids: string[]) {
    // Timeline reads from AppState.state.selection.assetIds directly,
    // which is kept in sync by the legacy bridge. No extra action needed.
    void ids;
  },

  /** Set the time cursor position */
  setCursor(ms: number | null) {
    const AppState = (window as any).AppState;
    if (AppState) {
      AppState.setTimeCursor(ms);
    }
  },

  /** Return to live mode */
  setLiveMode(live: boolean) {
    if (live) {
      const AppState = (window as any).AppState;
      if (AppState) {
        AppState.setTimeCursor(null);
      }
    }
  },

  /** Trigger timeline canvas resize */
  resize() {
    const panel = getTimelinePanel();
    if (panel?.resize) {
      panel.resize();
    }
  },
};
