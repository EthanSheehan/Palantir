/**
 * WorkspaceShell — Top-level layout manager
 * Owns region containers, splitters, tab groups, and pane mounting.
 * Does NOT own any business logic or operational state.
 */
const WorkspaceShell = (() => {
    // Layout state
    let _leftWidth = 380;
    let _bottomHeight = 240;
    let _rightWidth = 340;
    let _leftCollapsed = false;
    let _bottomCollapsed = false;
    let _rightVisible = false;

    // Splitter drag state
    let _activeSplitter = null;  // 'left' | 'right' | 'bottom' | null
    let _dragStartPos = 0;
    let _dragStartSize = 0;

    // Viewer reference for resize calls
    let _viewer = null;

    // Tab state per region: { regionId: { tabs: [paneId...], activeTab: paneId } }
    let _tabState = {
        left: { tabs: [], activeTab: null },
        right: { tabs: [], activeTab: null },
        bottom: { tabs: [], activeTab: null },
    };

    // Layout change callback
    let _onLayoutChange = null;

    /**
     * Build the shell DOM and reparent existing elements into regions.
     * Must be called after the Cesium viewer is initialized.
     */
    function init(viewer) {
        _viewer = viewer;

        // Load persisted layout state
        if (typeof LayoutPersistence !== 'undefined') {
            const saved = LayoutPersistence.load();
            if (saved && saved.regions) {
                const r = saved.regions;
                if (r.left) {
                    if (r.left.width) _leftWidth = r.left.width;
                    if (r.left.collapsed !== undefined) _leftCollapsed = r.left.collapsed;
                }
                if (r.right) {
                    if (r.right.width) _rightWidth = r.right.width;
                    if (r.right.visible !== undefined) _rightVisible = r.right.visible;
                }
                if (r.bottom) {
                    if (r.bottom.timelineHeight) _timelineHeight = r.bottom.timelineHeight;
                }
            }
        }

        const appContainer = document.getElementById('appContainer');
        if (!appContainer) {
            console.error('WorkspaceShell: #appContainer not found');
            return;
        }

        // Grab existing elements before reparenting
        const cesiumContainer = document.getElementById('cesiumContainer');
        const uiPanel = document.getElementById('uiPanel');
        const toolbarContainer = document.getElementById('toolbarContainer');
        const timelinePanel = document.getElementById('timelinePanel');
        const titleEl = uiPanel ? uiPanel.querySelector('.title') : null;

        // Build shell DOM
        const shell = document.createElement('div');
        shell.id = 'workspace-shell';

        // --- TOP REGION ---
        const regionTop = document.createElement('div');
        regionTop.id = 'ws-region-top';
        regionTop.className = 'ws-region ws-region-top';

        // Move toolbar into top region
        if (titleEl) {
            const titleSpan = document.createElement('span');
            titleSpan.className = 'ws-app-title';
            titleSpan.textContent = titleEl.textContent;
            titleSpan.style.cssText = 'font-size:1rem;font-weight:700;color:#f8fafc;text-transform:uppercase;letter-spacing:0.1em;margin-right:24px;white-space:nowrap;';
            regionTop.appendChild(titleSpan);
            titleEl.remove();
        }
        // toolbarContainer no longer needed in top bar (scrub controls moved to timeline drawer)
        if (toolbarContainer) toolbarContainer.remove();

        // Tool palette — populated after MapToolController is available
        const toolPalette = document.createElement('div');
        toolPalette.className = 'ws-tool-palette';
        toolPalette.id = 'ws-tool-palette';
        regionTop.appendChild(toolPalette);

        shell.appendChild(regionTop);

        // --- BODY (left + splitter + center + splitter + right) ---
        const body = document.createElement('div');
        body.id = 'ws-body';

        // Left region
        const regionLeft = document.createElement('div');
        regionLeft.id = 'ws-region-left';
        regionLeft.className = 'ws-region ws-region-left';

        // Left splitter
        const splitterLeft = document.createElement('div');
        splitterLeft.id = 'ws-splitter-left';
        splitterLeft.className = 'ws-splitter ws-splitter-v';

        // Center region
        const regionCenter = document.createElement('div');
        regionCenter.id = 'ws-region-center';
        regionCenter.className = 'ws-region ws-region-center';

        // Right splitter
        const splitterRight = document.createElement('div');
        splitterRight.id = 'ws-splitter-right';
        splitterRight.className = 'ws-splitter ws-splitter-v';
        splitterRight.style.display = 'none'; // hidden until right region is shown

        // Right region
        const regionRight = document.createElement('div');
        regionRight.id = 'ws-region-right';
        regionRight.className = 'ws-region ws-region-right';

        body.appendChild(regionLeft);
        body.appendChild(splitterLeft);
        body.appendChild(regionCenter);
        body.appendChild(splitterRight);
        body.appendChild(regionRight);

        shell.appendChild(body);

        // --- REPARENT EXISTING ELEMENTS ---

        // Move Cesium into center
        if (cesiumContainer) {
            // Reset flex/height styles that were for the old layout
            cesiumContainer.style.flex = '1';
            cesiumContainer.style.height = '100%';
            cesiumContainer.style.position = 'relative';
            regionCenter.appendChild(cesiumContainer);
        }

        // Move sidebar content into left region with shell-managed tabs
        if (uiPanel) {
            // Remove old sidebar styling that conflicts with shell
            uiPanel.style.width = '100%';
            uiPanel.style.height = '100%';
            uiPanel.style.minWidth = '0';
            uiPanel.style.maxWidth = 'none';
            uiPanel.style.boxShadow = 'none';
            uiPanel.style.borderRight = 'none';
            uiPanel.style.zIndex = 'auto';
            // Remove the old resizer if it still exists
            const oldResizer = uiPanel.querySelector('#sidebarResizer');
            if (oldResizer) oldResizer.remove();

            // Remove old tab navigation — shell will create its own
            const oldTabs = uiPanel.querySelector('.tabs');
            if (oldTabs) oldTabs.remove();

            // Build shell tab bar for left region
            const leftTabBar = document.createElement('div');
            leftTabBar.className = 'ws-tab-bar';
            leftTabBar.id = 'ws-tabs-left';

            // Map of tab definitions: id → { label, contentId }
            const leftTabs = [
                { id: 'missions', label: 'MISSION', icon: 'M', contentId: 'tab-mission' },
                { id: 'targets', label: 'TARGETS', icon: '◇', contentId: 'tab-targets' },
                { id: 'assets', label: 'ASSETS', icon: 'A', contentId: 'tab-drones' },
                { id: 'inspector', label: 'OPS', icon: 'O', contentId: 'tab-ops' },
                { id: 'alerts', label: 'ALERTS', icon: '!', contentId: 'tab-alerts' },
                { id: 'macrogrid', label: 'GRID', icon: 'G', contentId: 'tab-grid' },
                { id: 'commands', label: 'CMDS', icon: 'C', contentId: 'tab-commands' },
            ];

            _tabState.left.tabs = leftTabs.map(t => t.id);
            _tabState.left.activeTab = 'missions';

            leftTabs.forEach(tab => {
                const btn = document.createElement('button');
                btn.className = 'ws-tab-btn' + (tab.id === 'missions' ? ' ws-active' : '');
                btn.innerHTML = `<span class="ws-tab-icon">${tab.icon}</span><span class="ws-tab-label">${tab.label}</span>`;
                btn.dataset.paneId = tab.id;
                btn.dataset.contentId = tab.contentId;
                btn.addEventListener('click', () => {
                    setActiveTab('left', tab.id);
                });
                leftTabBar.appendChild(btn);
            });

            // Wrap the tab content area
            const leftContent = document.createElement('div');
            leftContent.className = 'ws-tab-content';
            leftContent.id = 'ws-content-left';

            // Move all tab-content divs into the shell content wrapper
            const tabContentDivs = uiPanel.querySelectorAll('.tab-content');
            tabContentDivs.forEach(div => {
                leftContent.appendChild(div);
            });

            // Clear the uiPanel and rebuild with shell structure
            // Keep any remaining non-tab content (stats, etc are inside tab-content)
            uiPanel.innerHTML = '';
            uiPanel.style.padding = '0';
            uiPanel.appendChild(leftTabBar);
            uiPanel.appendChild(leftContent);

            // Ensure a commands tab-content div exists in the left sidebar
            let commandsTab = document.getElementById('tab-commands');
            if (!commandsTab) {
                commandsTab = document.createElement('div');
                commandsTab.id = 'tab-commands';
                commandsTab.className = 'tab-content';
                commandsTab.innerHTML = '<h3 style="color:#94a3b8;padding:12px;">Command History</h3><div class="empty-state">No commands issued yet.</div>';
                leftContent.appendChild(commandsTab);
            }

            regionLeft.appendChild(uiPanel);
        }

        // Build the floating timeline pill (always visible, toggles drawer)
        _timelineExpanded = false;

        const timelinePill = document.createElement('div');
        timelinePill.id = 'ws-timeline-pill';
        timelinePill.className = 'ws-timeline-pill';

        function _updatePillClock() {
            const now = new Date();
            const day = now.getDate();
            const monthName = now.toLocaleString('en-US', { month: 'long' });
            const year = now.getFullYear();
            const hours = String(now.getHours()).padStart(2, '0');
            const mins = String(now.getMinutes()).padStart(2, '0');
            const secs = String(now.getSeconds()).padStart(2, '0');
            timelinePill.innerHTML = `<span class="ws-date-day">${day}</span> <span class="ws-date-month">${monthName}</span> <span class="ws-date-year">${year}</span> <span class="ws-date-sep">|</span> <span class="ws-date-time">${hours}:${mins}:${secs}</span>`;
        }
        _updatePillClock();
        setInterval(_updatePillClock, 1000);

        // Build the timeline drawer (hidden by default, appears below pill)
        const timelineDrawer = document.createElement('div');
        timelineDrawer.id = 'ws-timeline-drawer';
        timelineDrawer.className = 'ws-timeline-drawer';

        // Add timeline controls bar (scrub label + return to live) inside drawer
        const drawerHeader = document.createElement('div');
        drawerHeader.className = 'ws-timeline-drawer-header';
        timelineDrawer.appendChild(drawerHeader);

        if (timelinePanel) {
            timelinePanel.style.marginTop = '0';
            timelinePanel.style.flex = '1';
            timelinePanel.style.display = 'flex';
            timelinePanel.style.flexDirection = 'column';
            const canvas = timelinePanel.querySelector('canvas');
            if (canvas) {
                canvas.style.flex = '1';
                canvas.style.height = 'auto';
                canvas.style.minHeight = '0';
            }
            timelineDrawer.appendChild(timelinePanel);
        }

        // Click pill to toggle drawer
        timelinePill.addEventListener('click', () => {
            _toggleTimeline(timelineDrawer);
        });

        // Replace #appContainer contents with the shell
        appContainer.innerHTML = '';
        appContainer.appendChild(shell);

        // Append timeline drawer and pill to shell
        shell.appendChild(timelineDrawer);
        shell.appendChild(timelinePill);

        // Init vertical resize drag for expanded timeline drawer
        _initTimelineResize(timelineDrawer);

        // Also move the detailMapModal back to body (it's a fixed overlay)
        const modal = document.getElementById('detailMapModal');
        if (modal) {
            document.body.appendChild(modal);
        }

        // Apply initial sizes
        _applyLayout();

        // Set up splitter drag handlers
        _initSplitters(splitterLeft, splitterRight);

        // Move camera controls pill to the shell (so it's positioned relative to viewport)
        const camControls = document.getElementById('cameraControls');
        if (camControls) {
            shell.appendChild(camControls);
        }

        // Force layout flush before triggering Cesium resize
        shell.offsetHeight;

        // Trigger Cesium resize after DOM reflow
        requestAnimationFrame(() => {
            if (_viewer) _viewer.resize();
            // Re-init timeline canvas sizing
            if (typeof TimelinePanel !== 'undefined' && TimelinePanel.resize) {
                TimelinePanel.resize();
            }
        });

        // Wire up layout persistence
        if (typeof LayoutPersistence !== 'undefined') {
            onLayoutChange((state) => LayoutPersistence.save(state));

            // Restore persisted active tabs
            const saved = LayoutPersistence.load();
            if (saved && saved.regions) {
                if (saved.regions.left && saved.regions.left.activeTab) {
                    setActiveTab('left', saved.regions.left.activeTab);
                }
                // Restore timeline expanded state if persisted
                if (saved.regions.bottom && saved.regions.bottom.timelineExpanded) {
                    const drawer = document.getElementById('ws-timeline-drawer');
                    if (drawer) _expandTimeline(drawer);
                }
            }
        }

        console.log('WorkspaceShell: initialized');
    }

    function _applyLayout() {
        const shell = document.getElementById('workspace-shell');
        if (!shell) return;

        shell.style.setProperty('--ws-left-width', _leftWidth + 'px');
        shell.style.setProperty('--ws-bottom-height', _bottomHeight + 'px');
        shell.style.setProperty('--ws-right-width', _rightWidth + 'px');

        // Two rows: top toolbar + body (timeline is a floating overlay now)
        shell.style.gridTemplateRows = `48px 1fr`;

        // Left collapse
        const left = document.getElementById('ws-region-left');
        if (left) {
            if (_leftCollapsed) {
                left.classList.add('ws-collapsed');
            } else {
                left.classList.remove('ws-collapsed');
            }
        }

        // Right visibility
        const right = document.getElementById('ws-region-right');
        const rightSplitter = document.getElementById('ws-splitter-right');
        if (right) {
            if (_rightVisible) {
                right.classList.add('ws-visible');
                right.style.display = 'flex';
                if (rightSplitter) rightSplitter.style.display = '';
            } else {
                right.classList.remove('ws-visible');
                right.style.display = 'none';
                if (rightSplitter) rightSplitter.style.display = 'none';
            }
        }
    }

    function _initSplitters(splitterLeft, splitterRight) {
        // Left splitter
        splitterLeft.addEventListener('mousedown', (e) => {
            _activeSplitter = 'left';
            _dragStartPos = e.clientX;
            // If pane is collapsed, use the stored width as drag start size
            // (collapsed width is 48px but we want to restore to real width)
            _dragStartSize = _leftCollapsed ? _leftWidth : _leftWidth;
            _leftCollapsed = false; // dragging always expands
            splitterLeft.classList.add('ws-active');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            _applyLayout();
            e.preventDefault();
        });

        // Right splitter
        splitterRight.addEventListener('mousedown', (e) => {
            _activeSplitter = 'right';
            _dragStartPos = e.clientX;
            _dragStartSize = _rightWidth;
            splitterRight.classList.add('ws-active');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        });

        // Double-click to collapse/expand
        splitterLeft.addEventListener('dblclick', () => toggleRegion('left'));
        splitterRight.addEventListener('dblclick', () => toggleRegion('right'));

        // Global mouse move + up for drag
        document.addEventListener('mousemove', _onSplitterDrag);
        document.addEventListener('mouseup', _onSplitterDragEnd);
    }

    function _onSplitterDrag(e) {
        if (!_activeSplitter) return;

        if (_activeSplitter === 'left') {
            const leftEl = document.getElementById('ws-region-left');
            if (leftEl && !leftEl.classList.contains('ws-dragging')) {
                leftEl.classList.add('ws-dragging');
            }
            // Dragging the splitter always un-collapses the pane
            _leftCollapsed = false;
            const delta = e.clientX - _dragStartPos;
            _leftWidth = Math.max(240, Math.min(800, _dragStartSize + delta));
        } else if (_activeSplitter === 'right') {
            // Right splitter: dragging left increases right width
            const delta = _dragStartPos - e.clientX;
            _rightWidth = Math.max(240, Math.min(600, _dragStartSize + delta));
        }

        _applyLayout();

        // Keep Cesium viewport in sync
        if (_viewer) _viewer.resize();
        if (typeof TimelinePanel !== 'undefined' && TimelinePanel.resize) {
            TimelinePanel.resize();
        }
    }

    function _onSplitterDragEnd() {
        if (!_activeSplitter) return;

        // Remove active states
        document.querySelectorAll('.ws-splitter.ws-active').forEach(el => {
            el.classList.remove('ws-active');
        });
        const leftEl = document.getElementById('ws-region-left');
        if (leftEl) leftEl.classList.remove('ws-dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        _activeSplitter = null;

        // Notify layout change for persistence
        if (_onLayoutChange) _onLayoutChange(getLayoutState());
    }

    // --- Tab Management ---

    function setActiveTab(regionId, paneId) {
        const tabBar = document.getElementById(`ws-tabs-${regionId}`);
        const content = document.getElementById(`ws-content-${regionId}`);
        if (!tabBar || !content) return;

        _tabState[regionId].activeTab = paneId;

        // Update tab bar buttons
        tabBar.querySelectorAll('.ws-tab-btn').forEach(btn => {
            if (btn.dataset.paneId === paneId) {
                btn.classList.add('ws-active');
            } else {
                btn.classList.remove('ws-active');
            }
        });

        // Left region uses old tab-content class with contentId mapping
        const activeBtn = tabBar.querySelector(`.ws-tab-btn[data-pane-id="${paneId}"]`);
        const activeContentId = activeBtn ? activeBtn.dataset.contentId : null;
        content.querySelectorAll('.tab-content').forEach(div => {
            if (div.id === activeContentId) {
                div.classList.add('active-tab');
            } else {
                div.classList.remove('active-tab');
            }
        });

        // Notify layout change for persistence
        if (_onLayoutChange) _onLayoutChange(getLayoutState());
    }

    // --- Timeline Expand / Collapse ---

    let _timelineExpanded = false;
    let _timelineHeight = 25; // percentage of viewport height
    let _timelineDragging = false;
    let _timelineDragStartY = 0;
    let _timelineDragStartH = 0;

    function _updatePillPosition() {
        const pill = document.getElementById('ws-timeline-pill');
        if (!pill) return;
        if (_timelineExpanded) {
            // Position pill just above the drawer (drawer bottom gap 8px + drawer height + small gap)
            const drawerHeightPx = (window.innerHeight * _timelineHeight) / 100;
            pill.style.bottom = (8 + drawerHeightPx + 8) + 'px';
        } else {
            pill.style.bottom = '16px';
        }
    }

    function _expandTimeline(drawer) {
        _timelineExpanded = true;
        drawer.classList.add('ws-timeline-drawer-open');
        drawer.style.height = _timelineHeight + 'vh';
        _updatePillPosition();
        // Resize the timeline canvas after layout settles
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                if (typeof TimelinePanel !== 'undefined' && TimelinePanel.resize) {
                    TimelinePanel.resize();
                }
            });
        });
    }

    function _collapseTimeline(drawer) {
        _timelineExpanded = false;
        drawer.classList.remove('ws-timeline-drawer-open');
        drawer.style.height = '';
        _updatePillPosition();
    }

    function _toggleTimeline(drawer) {
        if (_timelineExpanded) {
            _collapseTimeline(drawer);
        } else {
            _expandTimeline(drawer);
        }
        if (_onLayoutChange) _onLayoutChange(getLayoutState());
    }

    function _initTimelineResize(pill) {
        const handle = document.createElement('div');
        handle.className = 'ws-timeline-resize-handle';
        pill.insertBefore(handle, pill.firstChild);

        handle.addEventListener('mousedown', (e) => {
            if (!_timelineExpanded) return;
            e.preventDefault();
            e.stopPropagation();
            _timelineDragging = true;
            _timelineDragStartY = e.clientY;
            _timelineDragStartH = pill.getBoundingClientRect().height;
            document.body.style.cursor = 'row-resize';
            document.body.style.userSelect = 'none';
            pill.classList.add('ws-dragging');
            const pillBtn = document.getElementById('ws-timeline-pill');
            if (pillBtn) pillBtn.classList.add('ws-dragging');
        });

        document.addEventListener('mousemove', (e) => {
            if (!_timelineDragging) return;
            const delta = _timelineDragStartY - e.clientY;
            const newH = _timelineDragStartH + delta;
            const vh = window.innerHeight;
            // Clamp between 15% and 80% of viewport
            const pct = Math.max(15, Math.min(80, (newH / vh) * 100));
            _timelineHeight = pct;
            pill.style.height = pct + 'vh';
            _updatePillPosition();
            if (typeof TimelinePanel !== 'undefined' && TimelinePanel.resize) {
                TimelinePanel.resize();
            }
        });

        document.addEventListener('mouseup', () => {
            if (!_timelineDragging) return;
            _timelineDragging = false;
            pill.classList.remove('ws-dragging');
            const pillBtn = document.getElementById('ws-timeline-pill');
            if (pillBtn) pillBtn.classList.remove('ws-dragging');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            if (_onLayoutChange) _onLayoutChange(getLayoutState());
        });
    }

    // --- Public API ---

    function collapseRegion(regionId) {
        if (regionId === 'left') { _leftCollapsed = true; }
        _applyLayout();
        if (_viewer) requestAnimationFrame(() => _viewer.resize());
        if (_onLayoutChange) _onLayoutChange(getLayoutState());
    }

    function expandRegion(regionId) {
        if (regionId === 'left') { _leftCollapsed = false; }
        else if (regionId === 'right') { _rightVisible = true; }
        _applyLayout();
        if (_viewer) requestAnimationFrame(() => _viewer.resize());
        if (_onLayoutChange) _onLayoutChange(getLayoutState());
    }

    function toggleRegion(regionId) {
        if (regionId === 'left') { _leftCollapsed = !_leftCollapsed; }
        else if (regionId === 'right') { _rightVisible = !_rightVisible; }
        _applyLayout();
        if (_viewer) requestAnimationFrame(() => _viewer.resize());
        if (_onLayoutChange) _onLayoutChange(getLayoutState());
    }

    function getLayoutState() {
        return {
            version: 1,
            regions: {
                left: { width: _leftWidth, collapsed: _leftCollapsed, activeTab: _tabState.left.activeTab },
                right: { width: _rightWidth, visible: _rightVisible },
                bottom: { timelineExpanded: _timelineExpanded, timelineHeight: _timelineHeight },
            },
        };
    }

    function applyLayoutState(state) {
        if (!state || !state.regions) return;
        const r = state.regions;
        if (r.left) {
            if (r.left.width) _leftWidth = r.left.width;
            if (r.left.collapsed !== undefined) _leftCollapsed = r.left.collapsed;
        }
        if (r.right) {
            if (r.right.width) _rightWidth = r.right.width;
            if (r.right.visible !== undefined) _rightVisible = r.right.visible;
        }
        if (r.bottom && r.bottom.timelineExpanded) {
            const drawer = document.getElementById('ws-timeline-drawer');
            if (drawer) _expandTimeline(drawer);
        }
        _applyLayout();
        if (_viewer) requestAnimationFrame(() => _viewer.resize());
    }

    function resetLayout() {
        _leftWidth = 380;
        _rightWidth = 340;
        _leftCollapsed = false;
        _rightVisible = false;
        const drawer = document.getElementById('ws-timeline-drawer');
        if (drawer) _collapseTimeline(drawer);
        _applyLayout();
        if (_viewer) requestAnimationFrame(() => _viewer.resize());
        if (_onLayoutChange) _onLayoutChange(getLayoutState());
    }

    function getRegion(regionId) {
        return document.getElementById(`ws-region-${regionId}`);
    }

    function onLayoutChange(callback) {
        _onLayoutChange = callback;
    }

    return {
        init,
        setActiveTab,
        collapseRegion,
        expandRegion,
        toggleRegion,
        getLayoutState,
        applyLayoutState,
        resetLayout,
        getRegion,
        onLayoutChange,
    };
})();
