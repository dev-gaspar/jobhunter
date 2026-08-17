# -*- coding: utf-8 -*-
"""Chequeo y descarga de actualizaciones desde GitHub Releases."""
import os
import re
import tempfile

import requests

RELEASES_LATEST = "https://api.github.com/repos/dev-gaspar/jobhunter/releases/latest"
ASSET_NAME = "JobHunterSetup-x64.exe"


def _semver(tag):
    try:
        clean = re.sub(r"^v", "", (tag or "").strip())
        parts = clean.split(".")[:3]
        return tuple(int(re.sub(r"[^0-9].*$", "", p) or 0) for p in parts)
    except Exception:
        return (0, 0, 0)


def get_latest(current_version):
    """Consulta el ultimo release. Nunca lanza: sin red retorna update_available False."""
    try:
        r = requests.get(RELEASES_LATEST, timeout=8,
                         headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        data = r.json()
        tag = data.get("tag_name", "")
        newer = _semver(tag) > _semver(current_version)
        url = None
        for a in data.get("assets", []):
            if a.get("name") == ASSET_NAME:
                url = a.get("browser_download_url")
                break
        return {"update_available": bool(newer and url), "latest": tag, "url": url}
    except Exception:
        return {"update_available": False, "latest": None, "url": None}


def download_installer(url, on_progress=None):
    """Descarga el instalador a %TEMP% y retorna la ruta. Lanza en error."""
    dest = os.path.join(tempfile.gettempdir(), ASSET_NAME)
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0) or 0)
        done = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                f.write(chunk)
                done += len(chunk)
                if on_progress and total:
                    on_progress(done, total)
    return dest
