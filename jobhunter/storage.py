"""Carga y guardado de knowledge.json (historial de runs y aplicaciones)."""
import json
import os

from jobhunter.constants import KB_PATH


def load_kb():
    if os.path.exists(KB_PATH):
        with open(KB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"runs": [], "applications": [], "rejected_companies": []}


def save_kb(kb):
    with open(KB_PATH, "w", encoding="utf-8") as f:
        json.dump(kb, f, indent=2, ensure_ascii=False)
