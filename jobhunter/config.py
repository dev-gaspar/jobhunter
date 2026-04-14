"""Carga, guardado y validacion de config.json."""
import json
import os

from jobhunter.constants import CONFIG_PATH


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def is_configured():
    cfg = load_config()
    return all(cfg.get(k) for k in ["gemini_api_key", "smtp_email", "smtp_password", "profile"])
