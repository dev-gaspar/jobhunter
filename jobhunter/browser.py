"""Utilidades de navegador para Playwright: localizar Chrome/Edge y limpiar zombies."""
import os
import shutil
import time

from jobhunter.constants import SESSION_DIR


def find_chrome():
    """Busca Chrome o Edge en rutas estandar de Windows. Fallback a PATH."""
    for p in [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]:
        if os.path.exists(p):
            return p
    return shutil.which("chrome") or shutil.which("msedge")


def kill_playwright_zombies():
    """Borra el SingletonLock si existe (Playwright anterior crasheo).

    No mata procesos: solo limpia el lockfile que impediria reabrir la sesion.
    """
    lock = os.path.join(SESSION_DIR, "SingletonLock")
    if os.path.exists(lock):
        try:
            os.remove(lock)
        except Exception:
            pass
        time.sleep(1)
