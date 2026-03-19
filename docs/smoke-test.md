# AMS Grid 2 — Smoke Test Checklist

Run through after every migration phase to verify nothing is broken.

## Startup
- [ ] Backend starts on port 8012 (`python main.py` in `backend/`)
- [ ] Frontend starts on port 8093
- [ ] No console errors on page load

## Cesium Globe
- [ ] Globe renders with dark CartoDB tiles
- [ ] 20 UAVs appear and animate smoothly
- [ ] Grid zones render with red intensity proportional to queue
- [ ] Flow lines (cyan) appear between zones
- [ ] Zone visibility toggle cycles ON → Outlines → OFF

## Sidebar / Tabs
- [ ] Left sidebar shows tabs: MISSION, TARGETS, ASSETS, OPS, ALERTS, GRID, CMDS
- [ ] Tab switching works — correct content shows for each tab
- [ ] Splitter drag resizes left panel

## Selection
- [ ] Single-click UAV on globe → selects it, sidebar updates
- [ ] Shift-click second UAV → multi-selection, both highlighted
- [ ] Selection propagates to Inspector (OPS tab)
- [ ] Selection propagates to Timeline (swimlanes appear)
- [ ] Clicking empty space clears selection

## Timeline
- [ ] Timeline pill shows clock at bottom
- [ ] Clicking pill opens timeline drawer
- [ ] Timeline shows time axis with "now" marker
- [ ] Selected UAV lanes appear in timeline
- [ ] Click to place playhead → scrub mode activates
- [ ] Toolbar shows "SCRUB: HH:MM:SS" with RETURN TO LIVE button
- [ ] Double-click timeline → returns to live
- [ ] Timeline drawer resizes via drag handle
- [ ] Scroll wheel zooms timeline

## Missions
- [ ] Mission creation form submits successfully
- [ ] New mission appears in mission list
- [ ] Propose/Approve/Pause/Abort buttons work

## Alerts
- [ ] Alerts appear when backend generates them (low battery, link loss)
- [ ] ACK button acknowledges alert
- [ ] Alert severity badges display correctly

## Macrogrid
- [ ] GRID tab shows recommendations
- [ ] "Convert to Mission" button works

## Camera
- [ ] Single-click UAV → macro tracking (10km altitude)
- [ ] Double-click UAV → third-person view
- [ ] Global View button returns to 500km view
- [ ] Decouple Camera button stops tracking
- [ ] Compass renders and follows heading

## Context Menu
- [ ] Right-click on globe shows context menu
- [ ] "Set Waypoint" appears when UAV is selected
- [ ] "Satellite Circle" toggle works

## Persistence
- [ ] Layout (panel width, active tab, timeline state) persists across page reload
- [ ] Waypoint markers visible for repositioning drones

## WebSocket Connections
- [ ] Legacy WS (/ws/stream) connected — UAVs animate
- [ ] Event WS (/ws/events) connected — panels update in real-time
- [ ] Reconnection works after brief backend restart
