#!/usr/bin/env python3
"""
Everest Textile Manufacturing System (ETMS)
Universal Startup Script

Starts the full-stack ETMS Core API and Web HUD on port 8000.
"""

import os
import sys
import subprocess
import webbrowser
import time

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root_dir)

    print("=" * 65)
    print(" [ETMS] EVEREST TEXTILE MANUFACTURING SYSTEM (ETMS v2.0)")
    print(" Enterprise Digital Backbone & Operational Mesh")
    print("=" * 65)

    # Detect python executable in .venv
    venv_python = os.path.join(root_dir, ".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    print(f"[*] Working Directory: {root_dir}")
    print(f"[*] Runtime Python:    {venv_python}")
    print(f"[*] Starting Server on http://localhost:8000 ...")

    # Try starting FastAPI with uvicorn
    cmd = [
        venv_python, "-m", "uvicorn", 
        "backend.app.main:app", 
        "--host", "0.0.0.0", 
        "--port", "8000",
        "--reload"
    ]

    try:
        # Give server a moment then open browser
        def open_browser():
            time.sleep(1.5)
            webbrowser.open("http://localhost:8000")

        import threading
        threading.Thread(target=open_browser, daemon=True).start()

        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n[*] ETMS Server stopped gracefully.")
    except Exception as e:
        print(f"[!] Falling back to static web server: {e}")
        frontend_dir = os.path.join(root_dir, "frontend")
        os.chdir(frontend_dir)
        subprocess.run([sys.executable, "-m", "http.server", "8000"])

if __name__ == "__main__":
    main()
