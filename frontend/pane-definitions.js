/**
 * Pane Definitions — registers all panes with metadata.
 * Must be loaded after pane-registry.js.
 */
(() => {
    PaneRegistry.register({
        id: 'toolbar',
        title: 'Toolbar',
        icon: 'settings',
        component: 'Toolbar',
        defaultRegion: 'top',
        allowedRegions: ['top'],
        closable: false,
        collapsible: false,
        defaultVisible: true,
        minWidth: null,
        minHeight: 48,
        preferredSize: { width: null, height: 48 },
        persistenceKey: 'pane.toolbar',
    });

    PaneRegistry.register({
        id: 'map',
        title: 'Globe',
        icon: 'globe',
        component: 'CesiumMap',
        defaultRegion: 'center',
        allowedRegions: ['center'],
        closable: false,
        collapsible: false,
        defaultVisible: true,
        minWidth: null,
        minHeight: null,
        preferredSize: { width: null, height: null },
        persistenceKey: 'pane.map',
    });

    PaneRegistry.register({
        id: 'assets',
        title: 'Assets',
        icon: 'drone',
        component: 'AssetsPane',
        defaultRegion: 'left',
        allowedRegions: ['left', 'right'],
        closable: true,
        collapsible: true,
        defaultVisible: true,
        minWidth: 280,
        minHeight: 200,
        preferredSize: { width: 380, height: null },
        persistenceKey: 'pane.assets',
    });

    PaneRegistry.register({
        id: 'missions',
        title: 'Missions',
        icon: 'mission',
        component: 'MissionPanel',
        defaultRegion: 'left',
        allowedRegions: ['left', 'right'],
        closable: true,
        collapsible: true,
        defaultVisible: true,
        minWidth: 280,
        minHeight: 200,
        preferredSize: { width: 380, height: null },
        persistenceKey: 'pane.missions',
    });

    PaneRegistry.register({
        id: 'inspector',
        title: 'Inspector',
        icon: 'inspect',
        component: 'InspectorPanel',
        defaultRegion: 'left',
        allowedRegions: ['left', 'right'],
        closable: true,
        collapsible: true,
        defaultVisible: true,
        minWidth: 280,
        minHeight: 150,
        preferredSize: { width: 380, height: null },
        persistenceKey: 'pane.inspector',
    });

    PaneRegistry.register({
        id: 'alerts',
        title: 'Alerts',
        icon: 'alert',
        component: 'AlertsPanel',
        defaultRegion: 'bottom',
        allowedRegions: ['left', 'right', 'bottom'],
        closable: true,
        collapsible: true,
        defaultVisible: true,
        minWidth: 240,
        minHeight: 120,
        preferredSize: { width: 340, height: 200 },
        persistenceKey: 'pane.alerts',
    });

    PaneRegistry.register({
        id: 'timeline',
        title: 'Timeline',
        icon: 'timeline',
        component: 'TimelinePanel',
        defaultRegion: 'bottom',
        allowedRegions: ['bottom'],
        closable: false,
        collapsible: true,
        defaultVisible: true,
        minWidth: null,
        minHeight: 120,
        preferredSize: { width: null, height: 240 },
        persistenceKey: 'pane.timeline',
    });

    PaneRegistry.register({
        id: 'macrogrid',
        title: 'Grid Ops',
        icon: 'grid',
        component: 'MacrogridPanel',
        defaultRegion: 'right',
        allowedRegions: ['left', 'right', 'bottom'],
        closable: true,
        collapsible: true,
        defaultVisible: false,
        minWidth: 240,
        minHeight: 150,
        preferredSize: { width: 340, height: 200 },
        persistenceKey: 'pane.macrogrid',
    });

    PaneRegistry.register({
        id: 'command_history',
        title: 'Commands',
        icon: 'command',
        component: 'CommandHistoryPane',
        defaultRegion: 'bottom',
        allowedRegions: ['bottom', 'right'],
        closable: true,
        collapsible: true,
        defaultVisible: true,
        minWidth: 240,
        minHeight: 120,
        preferredSize: { width: null, height: 200 },
        persistenceKey: 'pane.command_history',
    });

    PaneRegistry.register({
        id: 'event_log',
        title: 'Events',
        icon: 'log',
        component: 'EventLogPane',
        defaultRegion: 'right',
        allowedRegions: ['right', 'bottom'],
        closable: true,
        collapsible: true,
        defaultVisible: false,
        minWidth: 240,
        minHeight: 120,
        preferredSize: { width: 340, height: 200 },
        persistenceKey: 'pane.event_log',
    });
})();
