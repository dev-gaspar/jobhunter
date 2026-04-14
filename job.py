#!/usr/bin/env python3
"""JobHunter AI - entry point.

Mantiene compatibilidad con install.sh / install.ps1 (apuntan a job.py).
La logica vive en el paquete jobhunter/. Este shim solo:
  1. Auto-instala dependencias antes de importar nada de jobhunter (Playwright,
     rich, etc. se requieren para el import)
  2. Llama al dispatcher de cli/main.py
"""
import subprocess
import sys


def ensure_deps():
    needed = []
    for mod in ["rich", "requests", "playwright", "reportlab"]:
        try:
            __import__(mod)
        except ImportError:
            needed.append(mod)
    if needed:
        print(f"Instalando dependencias: {', '.join(needed)}...")
        subprocess.run([sys.executable, "-m", "pip", "install"] + needed, capture_output=True)
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except Exception:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True)


ensure_deps()

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from jobhunter.cli.main import main
from jobhunter.ui import console


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n  [dim]Cancelado.[/dim]\n")
        sys.exit(0)
