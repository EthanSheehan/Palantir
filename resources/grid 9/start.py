import subprocess
import time
import os
import sys
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(base_dir, "backend")
    frontend_dir = os.path.join(base_dir, "frontend")
    
    print("========================================")
    print("       Starting Grid 9 System...        ")
    print("========================================")
    
    print("[1/3] Starting Backend (FastAPI on Port 8010)...")
    # Use sys.executable to ensure we use the current Python interpreter
    backend_proc = subprocess.Popen([sys.executable, "main.py"], cwd=backend_dir)
    
    print("[2/3] Starting Frontend (HTTP Server on Port 8091)...")
    frontend_proc = subprocess.Popen([sys.executable, "-m", "http.server", "8091"], cwd=frontend_dir)
    
    print(f"\n[3/3] Servers initialized! Launching Grid 9 Desktop App...")
    
    # ---------------------------------------------------------
    # Launch Native PyQtWebEngine Window
    # ---------------------------------------------------------
    app = QApplication(sys.argv)
    
    # Force clear the cache so it always loads the latest app.js
    profile = QWebEngineProfile.defaultProfile()
    profile.clearHttpCache()
    
    window = QMainWindow()
    window.setWindowTitle("AMS V0.1")
    window.resize(1600, 900)
    
    webview = QWebEngineView()
    webview.setUrl(QUrl("http://localhost:8091"))
    
    window.setCentralWidget(webview)
    window.show()
    
    # Block until the user closes the window
    app.exec_()
    
    print("\n\nShutting down Grid 9 servers...")
    backend_proc.terminate()
    frontend_proc.terminate()
    backend_proc.wait()
    frontend_proc.wait()
    print("Shutdown complete. Goodbye!")

if __name__ == "__main__":
    main()
