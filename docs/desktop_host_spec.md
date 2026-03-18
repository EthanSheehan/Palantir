# Desktop Host Specification

> Defines the app startup sequence, backend process lifecycle, settings storage, layout persistence location, and window state handling for the AMS desktop application.

---

## 1. Overview

The Desktop Host is the outermost layer of the AMS application. It manages the native window, orchestrates backend/frontend process startup, persists user preferences, and provides the bridge between the web-based UI and the local operating system.

The current implementation (`start.py`) uses PyQt5 with QWebEngineView. This spec defines the target behavior for a more robust desktop host, building on that foundation.

---

## 2. Current State (`start.py`)

### 2.1 What Exists

```python
# start.py — current desktop launcher
- Spawns backend: subprocess.Popen(["python", "main.py"], cwd="backend/")
- Spawns frontend: subprocess.Popen(["python", "-m", "http.server", "8093", "-d", "frontend/"])
- Creates QWebEngineView window (1600x900) pointing to http://localhost:8093
- Clears QWebEngine cache on startup
- Terminates both subprocesses on window close
```

### 2.2 What's Missing

- No backend readiness detection (race condition: UI loads before backend is ready)
- No window state persistence (size/position lost on restart)
- No graceful shutdown (processes killed, not stopped)
- No error recovery (if backend crashes, UI shows a blank page)
- No application menu
- No startup splash/loading state
- No settings storage beyond what the browser provides

---

## 3. Target Startup Sequence

### 3.1 Full Startup Flow

```
1. Desktop host process starts
2. Read persisted settings (window state, layout path, backend config)
3. Show splash/loading screen in native window
4. Start backend process
5. Poll backend readiness: GET http://localhost:8012/api/v1/assets (or /health)
   - Retry every 500ms, timeout after 15s
   - Show "Starting backend..." status on splash
6. Backend ready → start frontend static server
7. Navigate QWebEngineView to http://localhost:8093
8. Frontend loads → WebSocket connects → splash dismissed
9. Restore window state (size, position, maximized)
10. Application is fully operational
```

### 3.2 Startup Error Handling

| Error | Response |
|-------|----------|
| Backend fails to start (process exits) | Show error dialog with stderr output, offer "Retry" or "Quit" |
| Backend fails readiness check (timeout) | Show error dialog: "Backend did not start within 15s", offer "Retry" or "Quit" |
| Frontend static server fails | Show error dialog, offer "Retry" or "Quit" |
| Port already in use | Show error: "Port 8012/8093 in use. Close the existing instance or change ports." |

---

## 4. Backend Process Lifecycle

### 4.1 Process Management

```python
class BackendProcess:
    def start(self):
        """Start the backend as a subprocess."""
        self.process = subprocess.Popen(
            ["python", "main.py"],
            cwd=self.backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP  # Windows
        )

    def stop(self):
        """Graceful shutdown: send SIGINT, wait 5s, then SIGKILL."""
        if self.process and self.process.poll() is None:
            # Send interrupt signal
            if sys.platform == 'win32':
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self.process.send_signal(signal.SIGINT)

            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def is_ready(self) -> bool:
        """Check if backend is accepting requests."""
        try:
            r = requests.get("http://localhost:8012/api/v1/assets", timeout=1)
            return r.status_code == 200
        except:
            return False

    def is_alive(self) -> bool:
        """Check if the process is still running."""
        return self.process and self.process.poll() is None
```

### 4.2 Health Monitoring

After startup, the desktop host periodically checks backend health:
- Poll interval: every 10 seconds
- If backend process exits unexpectedly:
  - Show notification: "Backend process stopped unexpectedly"
  - Offer: "Restart Backend" or "Quit"
- If backend becomes unresponsive (readiness check fails 3 times in a row):
  - Show notification: "Backend is not responding"
  - Offer: "Restart Backend" or "Quit"

### 4.3 Backend Configuration

The desktop host passes configuration to the backend via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `AMS_PORT` | `8012` | Backend API port |
| `AMS_DB_PATH` | `backend/ams.db` | SQLite database path |
| `AMS_ADAPTER` | `simulator` | Adapter type (simulator/playback/mavlink) |
| `AMS_LOG_LEVEL` | `INFO` | Logging level |

---

## 5. Frontend Static Server

### 5.1 Current Approach

Python's `http.server` module serves the `frontend/` directory on port 8093. This is simple and works for development.

### 5.2 Target Approach (Desktop .exe)

For a packaged desktop application:
- Option A: Bundle a lightweight static server (e.g., `aiohttp` static serving inside the backend process)
- Option B: Use `QWebEngineView.setUrl(QUrl.fromLocalFile(...))` to load directly from the filesystem, eliminating the need for a separate server process
- Option C: Keep the Python http.server but bundle it into the .exe

**Recommended**: Option A — add a static file mount to the FastAPI backend:
```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
```

This eliminates the separate frontend process entirely. The QWebEngineView points to `http://localhost:8012/` which serves both the API and the frontend.

---

## 6. Settings Storage

### 6.1 Settings Location

| Platform | Path |
|----------|------|
| Windows | `%APPDATA%\AMS\settings.json` |
| macOS | `~/Library/Application Support/AMS/settings.json` |
| Linux | `~/.config/ams/settings.json` |

Alternatively, use Qt's `QSettings` which handles platform-specific paths automatically.

### 6.2 Settings Schema

```json
{
  "version": 1,
  "window": {
    "x": 100,
    "y": 100,
    "width": 1600,
    "height": 900,
    "maximized": false,
    "screen": 0
  },
  "backend": {
    "port": 8012,
    "adapter": "simulator",
    "db_path": null
  },
  "ui": {
    "theme": "dark",
    "cesium_token": null
  },
  "layout_path": null
}
```

### 6.3 Settings API

```python
class Settings:
    def __init__(self):
        self._path = self._get_settings_path()
        self._data = self._load()

    def get(self, key, default=None):
        """Get a setting by dot-path (e.g., 'window.width')."""

    def set(self, key, value):
        """Set a setting and auto-save."""

    def save(self):
        """Write settings to disk."""

    def reset(self):
        """Reset to defaults."""
```

---

## 7. Window State Handling

### 7.1 Persisted State

On window close:
- Save `x`, `y`, `width`, `height`, `maximized` to settings
- Save which screen the window is on (multi-monitor support)

On startup:
- Restore saved position and size
- If the saved position is off-screen (monitor removed), reset to center of primary screen
- If `maximized` was true, restore maximized state

### 7.2 Implementation

```python
class MainWindow(QMainWindow):
    def closeEvent(self, event):
        # Save window state
        if not self.isMaximized():
            geo = self.geometry()
            settings.set('window.x', geo.x())
            settings.set('window.y', geo.y())
            settings.set('window.width', geo.width())
            settings.set('window.height', geo.height())
        settings.set('window.maximized', self.isMaximized())
        settings.save()

        # Shutdown backend
        self.backend.stop()
        self.frontend.stop()

        event.accept()

    def restore_window_state(self):
        x = settings.get('window.x', 100)
        y = settings.get('window.y', 100)
        w = settings.get('window.width', 1600)
        h = settings.get('window.height', 900)
        maximized = settings.get('window.maximized', False)

        # Validate position is on a visible screen
        screen_geo = QApplication.primaryScreen().availableGeometry()
        if not screen_geo.contains(QPoint(x, y)):
            x = screen_geo.x() + 50
            y = screen_geo.y() + 50

        self.setGeometry(x, y, w, h)
        if maximized:
            self.showMaximized()
```

---

## 8. Layout Persistence Location

### 8.1 Browser Mode (Development)

Layout state is persisted in `localStorage` under the key `ams.workspace.layout`. No desktop host involvement needed.

### 8.2 Desktop Mode

Layout state is persisted as a JSON file alongside settings:

| Platform | Path |
|----------|------|
| Windows | `%APPDATA%\AMS\layout.json` |
| macOS | `~/Library/Application Support/AMS/layout.json` |
| Linux | `~/.config/ams/layout.json` |

The desktop host provides this path to the frontend via a JavaScript bridge:

```python
# In QWebEngineView setup
channel = QWebChannel()
channel.registerObject('desktopHost', DesktopHostBridge())
view.page().setWebChannel(channel)
```

```javascript
// In frontend, detect desktop mode
if (typeof qt !== 'undefined' && qt.webChannelTransport) {
    new QWebChannel(qt.webChannelTransport, (channel) => {
        window.desktopHost = channel.objects.desktopHost;
        // Use desktopHost.saveLayout(json) / desktopHost.loadLayout() instead of localStorage
    });
}
```

### 8.3 Fallback

If the desktop bridge is not available (running in a plain browser), fall back to `localStorage`. The layout persistence module should abstract this:

```javascript
const LayoutPersistence = {
    save(state) {
        const json = JSON.stringify(state);
        if (window.desktopHost) {
            window.desktopHost.saveLayout(json);
        } else {
            localStorage.setItem('ams.workspace.layout', json);
        }
    },
    load() {
        if (window.desktopHost) {
            return JSON.parse(window.desktopHost.loadLayout() || 'null');
        }
        return JSON.parse(localStorage.getItem('ams.workspace.layout') || 'null');
    }
};
```

---

## 9. Application Menu

### 9.1 Menu Structure (Desktop Mode)

```
File
  ├── Reset Layout
  ├── Export Layout...
  ├── Import Layout...
  ├── ─────────────
  ├── Settings
  └── Quit

View
  ├── Toggle Left Panel
  ├── Toggle Right Panel
  ├── Toggle Bottom Panel
  ├── ─────────────
  ├── Full Screen
  └── Reset Zoom

Tools
  ├── Select (S)
  ├── Track Asset (T)
  ├── Set Waypoint (W)
  ├── Draw Route (R)
  ├── Draw Area (A)
  ├── Measure (M)
  └── Grid Inspect (G)

Help
  ├── Keyboard Shortcuts
  ├── About AMS
  └── Open Logs Folder
```

### 9.2 Implementation

```python
menubar = self.menuBar()

file_menu = menubar.addMenu("File")
file_menu.addAction("Reset Layout", self.reset_layout)
file_menu.addAction("Export Layout...", self.export_layout)
file_menu.addAction("Import Layout...", self.import_layout)
file_menu.addSeparator()
file_menu.addAction("Settings", self.open_settings)
file_menu.addAction("Quit", self.close)

# Menu actions communicate with the frontend via QWebChannel
```

---

## 10. Packaging Strategy (.exe)

### 10.1 Tool

Use **PyInstaller** to package the application as a single .exe (or directory bundle):

```bash
pyinstaller --onedir --windowed --name AMS \
  --add-data "frontend:frontend" \
  --add-data "backend:backend" \
  --add-data "romania_grid.py:." \
  start.py
```

### 10.2 Considerations

- **Cesium Ion token**: Must be configurable (settings or environment variable), not hardcoded
- **Database path**: Relative to the app data directory, not the install directory
- **Python path**: The bundled Python environment must include all backend dependencies (FastAPI, uvicorn, pydantic, etc.)
- **Size**: The .exe will be large (~200-500MB) due to PyQt5 + Chromium + Python runtime. Consider using a directory bundle instead of single-file for faster startup.

### 10.3 Future: Electron Alternative

If PyQt5 becomes limiting (e.g., QWebEngine version lags, WebChannel complexity), consider migrating to Electron with a Python backend subprocess. The architecture supports this cleanly since the frontend already communicates with the backend via HTTP/WS.

---

## 11. Implementation Phases

### Phase 7a: Improve `start.py` Startup

1. Add backend readiness polling before loading the frontend
2. Show a loading message in the QWebEngineView while waiting
3. Add graceful shutdown (SIGINT before SIGKILL)
4. Persist and restore window state

### Phase 7b: Settings Infrastructure

1. Create `Settings` class with platform-specific paths
2. Migrate hardcoded values (ports, token) to settings
3. Add QWebChannel bridge for frontend ↔ desktop communication

### Phase 7c: Application Menu

1. Add File/View/Tools/Help menus
2. Wire menu actions to frontend via QWebChannel
3. Add keyboard shortcuts

### Phase 7d: Packaging

1. Configure PyInstaller spec
2. Test .exe on clean Windows machine
3. Handle first-run setup (create data directory, initialize DB)
