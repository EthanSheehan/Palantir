/**
 * MapToolController — Explicit tool modes for Cesium map interactions.
 * Replaces ad hoc click handlers with a structured tool system.
 * Tools: select, track_asset, set_waypoint, macrogrid_inspect
 */
const MapToolController = (() => {
    let _viewer = null;
    let _ws = null;          // WebSocket reference for sending commands
    let _activeTool = null;
    let _previousTool = null; // one-level stack for returning from transient tools
    let _tools = {};
    let _onToolChangeCbs = [];
    let _droneRightClickCbs = [];

    // Shared state accessible by all tools
    let _trackedDroneEntity = null;
    let _macroTrackedId = null;
    let _isMacroTrackingReady = false;
    let _lastDronePosition = null;
    let _mapClickTimer = null;
    let _zoomOnSelect = true;  // when false, selecting a drone won't fly the camera
    const _droneWaypoints = {}; // { droneId: { waypoint: Entity, trajectory: Entity } }

    function init(viewer, ws) {
        _viewer = viewer;
        _ws = ws;

        // Register built-in tools
        registerTool(_selectTool);
        registerTool(_setWaypointTool);

        // Wire Cesium ScreenSpaceEventHandler
        const handler = viewer.screenSpaceEventHandler;

        handler.setInputAction((movement) => {
            if (_activeTool && _tools[_activeTool] && _tools[_activeTool].onLeftClick) {
                _tools[_activeTool].onLeftClick(movement);
            }
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

        // Shift+click is a distinct Cesium event — route to additive selection
        handler.setInputAction((movement) => {
            if (_activeTool && _tools[_activeTool] && _tools[_activeTool].onShiftLeftClick) {
                _tools[_activeTool].onShiftLeftClick(movement);
            }
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK, Cesium.KeyboardEventModifier.SHIFT);

        handler.setInputAction((movement) => {
            if (_activeTool && _tools[_activeTool] && _tools[_activeTool].onDoubleClick) {
                _tools[_activeTool].onDoubleClick(movement);
            }
        }, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);

        handler.setInputAction((movement) => {
            if (_activeTool && _tools[_activeTool] && _tools[_activeTool].onMouseMove) {
                _tools[_activeTool].onMouseMove(movement);
            }
        }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

        handler.setInputAction((movement) => {
            const entity = _pickDroneEntity(movement.position);
            _droneRightClickCbs.forEach(cb => cb(entity, movement.position));
        }, Cesium.ScreenSpaceEventType.RIGHT_CLICK);

        // Ctrl+scroll wheel — route to active tool's onCtrlWheel callback
        viewer.canvas.addEventListener('wheel', (e) => {
            if (e.ctrlKey && _activeTool && _tools[_activeTool] && _tools[_activeTool].onCtrlWheel) {
                e.preventDefault();
                e.stopPropagation();
                _tools[_activeTool].onCtrlWheel(e.deltaY > 0 ? -1 : 1);
                _viewer.scene.requestRender();
            }
        }, { passive: false });

        // Suppress browser default context menu on the Cesium canvas
        viewer.canvas.addEventListener('contextmenu', (e) => e.preventDefault());

        // Camera decouple button
        const decoupleBtn = document.getElementById('decoupleCameraBtn');
        if (decoupleBtn) {
            decoupleBtn.addEventListener('click', () => {
                _deselectDrone();
            });
        }

        // Return to global button
        let _globalViewClicks = 0;
        const returnBtn = document.getElementById('returnGlobalBtn');
        if (returnBtn) {
            returnBtn.addEventListener('click', () => {
                _deselectDrone();
                viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);

                if (_globalViewClicks === 0) {
                    // First click: Romania overview (standard)
                    viewer.camera.flyTo({
                        destination: Cesium.Cartesian3.fromDegrees(24.9668, 41.2, 500000.0),
                        orientation: {
                            heading: Cesium.Math.toRadians(0),
                            pitch: Cesium.Math.toRadians(-45.0),
                            roll: 0.0
                        },
                        duration: 1.5
                    });
                    _globalViewClicks = 1;
                } else {
                    // Second click: full globe view, 0 tilt
                    viewer.camera.flyTo({
                        destination: Cesium.Cartesian3.fromDegrees(25.0, 46.0, 15000000.0),
                        orientation: {
                            heading: Cesium.Math.toRadians(0),
                            pitch: Cesium.Math.toRadians(-90.0),
                            roll: 0.0
                        },
                        duration: 2.0
                    });
                    _globalViewClicks = 0;
                }
            });

            // Reset click counter when any drone is selected
            onToolChange(() => { _globalViewClicks = 0; });
        }

        // Zoom-lock toggle button
        const lockBtn = document.getElementById('lockZoomBtn');
        if (lockBtn) {
            lockBtn.addEventListener('click', () => {
                _zoomOnSelect = !_zoomOnSelect;
                lockBtn.title = _zoomOnSelect
                    ? 'Zoom to Asset (click to disable)'
                    : 'Multi-view: no zoom on select (click to enable)';
                lockBtn.style.opacity = _zoomOnSelect ? '1' : '0.5';
                lockBtn.dispatchEvent(new CustomEvent('zoomToggle', { detail: { zoomOn: _zoomOnSelect } }));
            });
        }

        // Default tool
        setTool('select');

        // Build tool palette buttons in the toolbar
        _buildToolPalette();

        console.log('MapToolController: initialized');
    }

    function registerTool(tool) {
        _tools[tool.id] = tool;
    }

    function setTool(toolId) {
        if (!_tools[toolId]) {
            console.warn('MapToolController: unknown tool', toolId);
            return;
        }

        const prev = _activeTool;
        if (prev && _tools[prev] && _tools[prev].onDeactivate) {
            _tools[prev].onDeactivate();
        }

        _previousTool = prev;
        _activeTool = toolId;

        if (_tools[toolId].onActivate) {
            _tools[toolId].onActivate();
        }

        _onToolChangeCbs.forEach(cb => cb(toolId, prev));
    }

    function returnToPreviousTool() {
        if (_previousTool && _tools[_previousTool]) {
            setTool(_previousTool);
        } else {
            setTool('select');
        }
    }

    function getActiveTool() {
        return _activeTool;
    }

    function onToolChange(cb) {
        _onToolChangeCbs.push(cb);
    }

    function setWebSocket(ws) {
        _ws = ws;
    }

    function _buildToolPalette() {
        const palette = document.getElementById('ws-tool-palette');
        if (!palette) return;

        Object.values(_tools).forEach(tool => {
            const btn = document.createElement('button');
            btn.className = 'ws-tool-btn' + (tool.id === _activeTool ? ' ws-active' : '');
            btn.textContent = tool.label;
            btn.title = tool.hint || '';
            btn.dataset.toolId = tool.id;
            btn.addEventListener('click', () => setTool(tool.id));
            palette.appendChild(btn);
        });

        // Update palette when tool changes
        onToolChange((newId) => {
            palette.querySelectorAll('.ws-tool-btn').forEach(b => {
                if (b.dataset.toolId === newId) {
                    b.classList.add('ws-active');
                } else {
                    b.classList.remove('ws-active');
                }
            });
        });
    }

    // --- Shared helpers ---

    function _deselectDrone() {
        if (_trackedDroneEntity) {
            _trackedDroneEntity.viewFrom = undefined;
        }
        _trackedDroneEntity = null;
        _viewer.trackedEntity = undefined;
        _macroTrackedId = null;
        _isMacroTrackingReady = false;
        _lastDronePosition = null;
        // cameraControls is always visible now
        _viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);

        // Clear asset selection in AppState
        if (typeof AppState !== 'undefined') {
            AppState.select('asset', null);
        }
    }

    function _triggerDroneSelection(entity, viewMode) {
        // cameraControls is always visible now
        _trackedDroneEntity = entity;

        // Sync selection to AppState so timeline and other panels can react
        if (entity && entity.id && typeof AppState !== 'undefined') {
            const currentIds = AppState.state.selection.assetIds.slice();
            const idx = currentIds.indexOf(entity.id);
            if (idx > 0) {
                // Already a secondary — promote to primary, keep rest in place
                currentIds.splice(idx, 1);
                currentIds.unshift(entity.id);
                AppState.selectMulti(currentIds);
            } else if (idx === -1) {
                // Not in selection at all — replace selection with just this drone
                AppState.select('asset', entity.id);
            }
            // idx === 0: already primary, nothing to change
        }
        _viewer.trackedEntity = undefined;

        if (_viewer.camera.transform && !_viewer.camera.transform.equals(Cesium.Matrix4.IDENTITY)) {
            _viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
        }

        _macroTrackedId = null;
        _isMacroTrackingReady = false;
        _lastDronePosition = null;

        // Skip camera fly-to if zoom-on-select is disabled
        if (!_zoomOnSelect) return;

        if (viewMode === 'thirdPerson') {
            entity.viewFrom = undefined;
            _viewer.flyTo(entity, {
                duration: 1.5,
                offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-15), 150)
            }).then((result) => {
                if (result && _trackedDroneEntity === entity) {
                    entity.viewFrom = new Cesium.Cartesian3(0, -100, 30);
                    _viewer.trackedEntity = entity;
                }
            });
        } else {
            entity.viewFrom = undefined;
            const currentHeading = _viewer.camera.heading;
            const currentPitch = Math.min(_viewer.camera.pitch, Cesium.Math.toRadians(-20));
            _viewer.flyTo(entity, {
                duration: 1.5,
                offset: new Cesium.HeadingPitchRange(currentHeading, currentPitch, 10000)
            }).then((result) => {
                if (result && _trackedDroneEntity === entity) {
                    _macroTrackedId = parseInt(entity.id.replace('uav_', ''));
                    _isMacroTrackingReady = true;
                }
            });
        }
    }

    function _triggerDroneSelectionAdditive(entity) {
        if (!entity || !entity.id) return;
        const id = entity.id;
        const currentIds = (typeof AppState !== 'undefined')
            ? AppState.state.selection.assetIds.slice()
            : [];
        const idx = currentIds.indexOf(id);

        if (idx === -1) {
            // Not yet selected — add to set
            if (currentIds.length === 0) {
                // First selection: behave exactly like a normal click (camera, compass, etc.)
                _triggerDroneSelection(entity, 'macro');
            } else {
                // Secondary selection: append, no camera move
                currentIds.push(id);
                if (typeof AppState !== 'undefined') AppState.selectMulti(currentIds);
            }
        } else if (currentIds.length === 1) {
            // Sole selected drone — deselect
            _deselectDrone();
        } else if (idx === 0) {
            // Removing primary — promote next to primary
            currentIds.splice(0, 1);
            const newPrimary = _viewer.entities.getById(currentIds[0]);
            if (newPrimary) _trackedDroneEntity = newPrimary;
            if (typeof AppState !== 'undefined') AppState.selectMulti(currentIds);
        } else {
            // Removing a secondary
            currentIds.splice(idx, 1);
            if (typeof AppState !== 'undefined') AppState.selectMulti(currentIds);
        }
    }

    function _pickDroneEntity(position) {
        const pickedObjects = _viewer.scene.drillPick(position);
        for (let i = 0; i < pickedObjects.length; i++) {
            const picked = pickedObjects[i];
            if (Cesium.defined(picked) && picked.id) {
                const pickId = typeof picked.id === 'string' ? picked.id : picked.id.id;
                if (pickId && typeof pickId === 'string' && pickId.startsWith('uav_')) {
                    return _viewer.entities.getById(pickId);
                }
            }
        }
        return null;
    }

    function _pickTerrain(position) {
        let cartesian = _viewer.scene.pickPosition(position);
        if (!cartesian) {
            cartesian = _viewer.camera.pickEllipsoid(position, _viewer.scene.globe.ellipsoid);
        }
        return cartesian;
    }

    function _placeWaypoint(droneId, cartesian, altitude) {
        const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
        const lon = Cesium.Math.toDegrees(cartographic.longitude);
        const lat = Cesium.Math.toDegrees(cartographic.latitude);
        const alt = altitude || _waypointPreviewAlt || 2000;

        // Send WS command with altitude
        if (_ws && _ws.readyState === WebSocket.OPEN) {
            _ws.send(JSON.stringify({
                action: "move_drone",
                drone_id: droneId,
                target_lon: lon,
                target_lat: lat,
                target_alt: alt
            }));
        }

        // Create or update visual marker
        if (!_droneWaypoints[droneId]) {
            const waypointEntity = _viewer.entities.add({
                position: Cesium.Cartesian3.fromDegrees(lon, lat, alt / 2),
                cylinder: {
                    length: alt,
                    topRadius: 20.0,
                    bottomRadius: 20.0,
                    material: Cesium.Color.fromCssColorString('#22c55e').withAlpha(0.6),
                    outline: true,
                    outlineColor: Cesium.Color.fromCssColorString('#22c55e')
                }
            });

            const trajectoryEntity = _viewer.entities.add({
                polyline: {
                    positions: new Cesium.CallbackProperty(() => {
                        const activeDrone = _viewer.entities.getById(`uav_${droneId}`);
                        if (!activeDrone || !waypointEntity) return [];
                        const start = activeDrone.position.getValue(_viewer.clock.currentTime);
                        const end = waypointEntity.position.getValue(_viewer.clock.currentTime);
                        if (start && end) return [start, end];
                        return [];
                    }, false),
                    width: 2,
                    material: new Cesium.PolylineDashMaterialProperty({
                        color: Cesium.Color.fromCssColorString('#22c55e'),
                        dashLength: 20.0
                    }),
                    clampToGround: true
                }
            });

            _droneWaypoints[droneId] = {
                waypoint: waypointEntity,
                trajectory: trajectoryEntity
            };
        } else {
            // Update existing waypoint with new position and altitude
            _droneWaypoints[droneId].waypoint.position = Cesium.Cartesian3.fromDegrees(lon, lat, alt / 2);
            _droneWaypoints[droneId].waypoint.cylinder.length = alt;
        }
    }

    // ─── SELECT TOOL ───────────────────────────────────────────

    const _selectTool = {
        id: 'select',
        label: 'Select',
        icon: '🔍',
        hint: 'Click drone to select, double-click for 3rd-person. Double-click terrain for demand spike.',

        onLeftClick(movement) {
            const droneEntity = _pickDroneEntity(movement.position);
            if (droneEntity) {
                if (_mapClickTimer) clearTimeout(_mapClickTimer);
                _mapClickTimer = setTimeout(() => {
                    _triggerDroneSelection(droneEntity, 'macro');
                }, 250);
            }
        },

        onShiftLeftClick(movement) {
            const droneEntity = _pickDroneEntity(movement.position);
            if (droneEntity) {
                if (_mapClickTimer) clearTimeout(_mapClickTimer);
                _mapClickTimer = setTimeout(() => {
                    _triggerDroneSelectionAdditive(droneEntity);
                }, 250);
            }
        },

        onDoubleClick(movement) {
            if (_mapClickTimer) clearTimeout(_mapClickTimer);

            // Check for drone pick first
            const droneEntity = _pickDroneEntity(movement.position);
            if (droneEntity) {
                _triggerDroneSelection(droneEntity, 'thirdPerson');
                return;
            }

            // If tracking a drone and double-clicked background, ignore
            if (_trackedDroneEntity) return;

            // Terrain spike
            const cartesian = _pickTerrain(movement.position);
            if (cartesian) {
                const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
                const lon = Cesium.Math.toDegrees(cartographic.longitude);
                const lat = Cesium.Math.toDegrees(cartographic.latitude);

                if (_ws && _ws.readyState === WebSocket.OPEN) {
                    _ws.send(JSON.stringify({
                        action: "spike",
                        lon: lon,
                        lat: lat,
                        radius: 0.5,
                        magnitude: 20
                    }));

                    const entity = _viewer.entities.add({
                        position: cartesian,
                        cylinder: {
                            length: 10000.0,
                            topRadius: 3000.0,
                            bottomRadius: 3000.0,
                            material: Cesium.Color.RED.withAlpha(0.3),
                            outline: true,
                            outlineColor: Cesium.Color.RED.withAlpha(0.6)
                        }
                    });
                    _viewer.scene.requestRender();

                    setTimeout(() => {
                        _viewer.entities.remove(entity);
                        _viewer.scene.requestRender();
                    }, 500);
                }
            }
        },

        onMouseMove(movement) {
            if (!_trackedDroneEntity) {
                const cartesian = _pickTerrain(movement.endPosition);
                if (cartesian) {
                    // Expose as currentMousePosition for other modules
                    MapToolController._currentMousePosition = cartesian;
                    _viewer.scene.requestRender();
                }
            }
        },

        onActivate() {},
        onDeactivate() {}
    };

    // ─── SET WAYPOINT TOOL ─────────────────────────────────────

    // Waypoint preview state
    let _waypointPreview = null;       // { cylinder, trajectory }
    let _waypointPreviewAlt = 2000.0;  // Preview altitude in meters
    let _waypointPreviewPos = null;    // Current preview cartesian (ground)
    let _waypointPreviewLon = 0;       // Cached lon/lat for cylinder CallbackProperty
    let _waypointPreviewLat = 0;

    function _createWaypointPreview() {
        if (_waypointPreview) return; // Already exists

        // Cylinder uses CallbackProperty for smooth real-time position tracking
        const cylinderEntity = _viewer.entities.add({
            position: new Cesium.CallbackProperty(() => {
                if (!_waypointPreviewPos) return Cesium.Cartesian3.fromDegrees(0, 0, 0);
                return Cesium.Cartesian3.fromDegrees(_waypointPreviewLon, _waypointPreviewLat, _waypointPreviewAlt / 2);
            }, false),
            show: false,
            cylinder: {
                length: new Cesium.CallbackProperty(() => _waypointPreviewAlt, false),
                topRadius: 20.0,
                bottomRadius: 20.0,
                material: Cesium.Color.fromCssColorString('#22c55e').withAlpha(0.4),
                outline: true,
                outlineColor: Cesium.Color.fromCssColorString('#22c55e').withAlpha(0.6)
            }
        });
        const trajectoryEntity = _viewer.entities.add({
            show: false,
            polyline: {
                positions: new Cesium.CallbackProperty(() => {
                    if (!_trackedDroneEntity || !_waypointPreviewPos) return [];
                    const start = _trackedDroneEntity.position.getValue(_viewer.clock.currentTime);
                    if (start && _waypointPreviewPos) return [start, _waypointPreviewPos];
                    return [];
                }, false),
                width: 2,
                material: new Cesium.PolylineDashMaterialProperty({
                    color: Cesium.Color.fromCssColorString('#22c55e'),
                    dashLength: 20.0
                }),
                clampToGround: true
            }
        });
        _waypointPreview = { cylinder: cylinderEntity, trajectory: trajectoryEntity };
    }

    function _removeWaypointPreview() {
        if (!_waypointPreview) return;
        _viewer.entities.remove(_waypointPreview.cylinder);
        _viewer.entities.remove(_waypointPreview.trajectory);
        _waypointPreview = null;
        _waypointPreviewPos = null;
    }

    const _setWaypointTool = {
        id: 'set_waypoint',
        label: 'Waypoint',
        icon: '📍',
        hint: 'Click terrain to place waypoint. Ctrl+scroll to adjust altitude.',

        onLeftClick(movement) {
            if (!_trackedDroneEntity) {
                returnToPreviousTool();
                return;
            }

            const cartesian = _pickTerrain(movement.position);
            if (cartesian) {
                const markerId = _trackedDroneEntity.id.replace('uav_', '');
                const dId = parseInt(markerId);

                _placeWaypoint(dId, cartesian, _waypointPreviewAlt);

                // Reset inline button if present
                const inlineBtn = document.getElementById(`inlineSetWaypointBtn_${dId}`);
                if (inlineBtn) {
                    inlineBtn.textContent = 'Set Waypoint';
                    inlineBtn.style.background = '';
                    inlineBtn.style.borderColor = '';
                    inlineBtn.style.color = '';
                }

                _removeWaypointPreview();
                returnToPreviousTool();
            }
        },

        onDoubleClick() {},

        onMouseMove(movement) {
            if (!_trackedDroneEntity) return;
            const cartesian = _pickTerrain(movement.endPosition);
            if (!cartesian) return;

            // Update cached position for CallbackProperty to pick up
            const carto = Cesium.Cartographic.fromCartesian(cartesian);
            _waypointPreviewLon = Cesium.Math.toDegrees(carto.longitude);
            _waypointPreviewLat = Cesium.Math.toDegrees(carto.latitude);
            _waypointPreviewPos = cartesian;

            // Dynamically cap altitude based on distance to drone at max climb angle
            const MAX_CLIMB_DEG = 15.0;
            const dronePos = _trackedDroneEntity.position.getValue(_viewer.clock.currentTime);
            if (dronePos) {
                const droneCarto = Cesium.Cartographic.fromCartesian(dronePos);
                const droneAlt = droneCarto.height || 2000;
                const dLon = (_waypointPreviewLon - Cesium.Math.toDegrees(droneCarto.longitude)) * 111000 * Math.cos(droneCarto.latitude);
                const dLat = (_waypointPreviewLat - Cesium.Math.toDegrees(droneCarto.latitude)) * 111000;
                const horizDist = Math.sqrt(dLon * dLon + dLat * dLat);
                const maxAlt = droneAlt + horizDist * Math.tan(Cesium.Math.toRadians(MAX_CLIMB_DEG));
                if (_waypointPreviewAlt > maxAlt) {
                    _waypointPreviewAlt = Math.max(200, maxAlt);
                }
            }

            if (_waypointPreview) {
                _waypointPreview.cylinder.show = true;
                _waypointPreview.trajectory.show = true;
            }
            _viewer.scene.requestRender();
        },

        onCtrlWheel(direction) {
            // direction: +1 = scroll up (increase alt), -1 = scroll down (decrease alt)
            const MAX_CLIMB_DEG = 15.0; // Must match UAV.MAX_CLIMB_DEG in sim.py
            let newAlt = _waypointPreviewAlt + direction * 100;

            // When increasing altitude, cap by what the drone can achieve at max climb angle
            if (direction > 0 && _trackedDroneEntity && _waypointPreviewPos) {
                const dronePos = _trackedDroneEntity.position.getValue(_viewer.clock.currentTime);
                if (dronePos) {
                    const droneCarto = Cesium.Cartographic.fromCartesian(dronePos);
                    const droneAlt = droneCarto.height || 2000;
                    // Horizontal distance from drone to waypoint preview in meters
                    const dLon = (_waypointPreviewLon - Cesium.Math.toDegrees(droneCarto.longitude)) * 111000 * Math.cos(droneCarto.latitude);
                    const dLat = (_waypointPreviewLat - Cesium.Math.toDegrees(droneCarto.latitude)) * 111000;
                    const horizDist = Math.sqrt(dLon * dLon + dLat * dLat);
                    // Max achievable altitude = droneAlt + horizDist * tan(maxClimb)
                    const maxAlt = droneAlt + horizDist * Math.tan(Cesium.Math.toRadians(MAX_CLIMB_DEG));
                    newAlt = Math.min(newAlt, maxAlt);
                }
            }

            _waypointPreviewAlt = Math.max(200, Math.min(5000, newAlt));
            _viewer.scene.requestRender();
        },

        onActivate() {
            // Default altitude from tracked drone's current altitude
            if (_trackedDroneEntity) {
                const pos = _trackedDroneEntity.position.getValue(_viewer.clock.currentTime);
                if (pos) {
                    const carto = Cesium.Cartographic.fromCartesian(pos);
                    _waypointPreviewAlt = Math.max(200, carto.height || 2000);
                } else {
                    _waypointPreviewAlt = 2000.0;
                }
            } else {
                _waypointPreviewAlt = 2000.0;
            }
            _createWaypointPreview();
        },

        onDeactivate() {
            _removeWaypointPreview();
        }
    };

    // ─── Macro tracking tick (called from render loop in app.js) ───

    function tickMacroTracking() {
        if (!_isMacroTrackingReady || _macroTrackedId === null) return;

        const entity = _viewer.entities.getById(`uav_${_macroTrackedId}`);
        if (!entity) return;

        const pos = entity.position.getValue(_viewer.clock.currentTime);
        if (pos) {
            if (_lastDronePosition) {
                const dx = pos.x - _lastDronePosition.x;
                const dy = pos.y - _lastDronePosition.y;
                const dz = pos.z - _lastDronePosition.z;
                _viewer.camera.position.x += dx;
                _viewer.camera.position.y += dy;
                _viewer.camera.position.z += dz;
            }
            _lastDronePosition = pos;
        } else {
            _lastDronePosition = null;
        }
    }

    function onDroneRightClick(cb) { _droneRightClickCbs.push(cb); }

    // ─── Public getters for external state bridging ───

    function getTrackedDroneEntity() { return _trackedDroneEntity; }
    function getMacroTrackedId() { return _macroTrackedId; }
    function isMacroTrackingReady() { return _isMacroTrackingReady; }
    function getDroneWaypoints() { return _droneWaypoints; }

    return {
        init,
        registerTool,
        setTool,
        getActiveTool,
        returnToPreviousTool,
        onToolChange,
        setWebSocket,
        tickMacroTracking,
        getTrackedDroneEntity,
        getMacroTrackedId,
        isMacroTrackingReady,
        getDroneWaypoints,
        onDroneRightClick,
        _triggerDroneSelection,          // exposed for external callers (drone list clicks)
        _triggerDroneSelectionAdditive,  // exposed for shift+click callers
        _placeWaypoint,          // exposed for detail modal waypoint placement
        _currentMousePosition: null,
    };
})();
// Expose on window for ES module access
window.MapToolController = MapToolController;
