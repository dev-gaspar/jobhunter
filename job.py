#!/usr/bin/env python3
"""
JobHunter AI v1.0
Busqueda automatizada de empleo en LinkedIn + CVs con IA + Envio automatico

Uso:
    jobhunter                       Primera vez = asistente de config
    jobhunter --test <email>        Modo prueba (envia a tu correo)
    jobhunter run                   Buscar y enviar a reclutadores
    jobhunter run --dry             Pipeline completo sin enviar emails
    jobhunter login                 Iniciar sesion en LinkedIn
    jobhunter status                Ver configuracion y estadisticas
    jobhunter setup                 Configuracion inicial
"""
import json, os, sys, re, time, random, smtplib, subprocess, shutil, requests, base64
import urllib.parse
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

# ── Auto-install dependencies ──
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
        from playwright.sync_api import sync_playwright
    except:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True)

ensure_deps()

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn, TimeElapsedColumn
from rich.text import Text
from rich import print as rprint
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from jobhunter.constants import (
    BASE_DIR,
    CONFIG_PATH,
    SESSION_DIR,
    KB_PATH,
    VERSION,
    GEMINI_MODELS,
    BANNER_LARGE,
    BANNER_SMALL,
)
from jobhunter.ui import console
from jobhunter.banner import get_banner

from src.cv_builder import generate_cv_pdf, get_cv_filename
from src.offer_utils import (
    deduplicate_offers_by_title_company,
    extract_emails,
    was_already_applied,
)


# ══════════════════════════════════════════════
# CONFIG & KNOWLEDGE BASE
# ══════════════════════════════════════════════
from jobhunter.config import load_config, save_config, is_configured
from jobhunter.storage import load_kb, save_kb

# ══════════════════════════════════════════════
# GEMINI
# ══════════════════════════════════════════════
from jobhunter.ai.gemini import gemini_url, call_gemini, call_gemini_vision


# ══════════════════════════════════════════════
# EMAIL & UTILS
# ══════════════════════════════════════════════
from jobhunter.mailer import send_email

from jobhunter.browser import find_chrome, kill_playwright_zombies


# ══════════════════════════════════════════════
# SETUP WIZARD
# ══════════════════════════════════════════════
from jobhunter.cli.setup import (
    cmd_setup,
    _setup_screen,
    _ask,
    _ask_secret,
    _mask_secret,
)
from jobhunter.constants import BACK


# ══════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════
from jobhunter.cli.login import cmd_login


# ══════════════════════════════════════════════
# STATUS
# ══════════════════════════════════════════════
from jobhunter.cli.status import cmd_status


# ══════════════════════════════════════════════
# UPDATE
# ══════════════════════════════════════════════
from jobhunter.updater import cmd_update, check_for_updates


# ══════════════════════════════════════════════
# SCRAPING (headless)
# ══════════════════════════════════════════════
from jobhunter.scraper import scrape_posts, do_linkedin_login as _do_linkedin_login
from jobhunter.constants import TIME_FILTERS


# ══════════════════════════════════════════════
# MULTI-AGENT SYSTEM
# ══════════════════════════════════════════════
from jobhunter.agents.filter import agent_filter
from jobhunter.agents.cv import agent_cv
from jobhunter.agents.email import agent_email



# ══════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════
from jobhunter.pipeline import cmd_run
# ══════════════════════════════════════════════
# OPTIMIZE
# ══════════════════════════════════════════════
from jobhunter.cli.optimize import cmd_optimize


# ══════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════
from jobhunter.cli.history import cmd_history
from jobhunter.cli.blacklist import cmd_blacklist
from jobhunter.cli.help import cmd_help


# ══════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════
def parse_time_filter(args):
    """Extract --time filter from args. Default: 24h"""
    for i, a in enumerate(args):
        if a == "--time" and i + 1 < len(args):
            val = args[i + 1]
            if val in ("24h", "week", "month"):
                return val
            else:
                console.print(f"  [red]✗[/red] Filtro invalido: {val}  [dim](opciones: 24h, week, month)[/dim]")
                sys.exit(1)
    return "24h"


def main():
    check_for_updates()

    if len(sys.argv) < 2:
        if not is_configured():
            cmd_setup()
        else:
            cmd_help()
        return

    cmd = sys.argv[1]
    tf = parse_time_filter(sys.argv)
    auto = "--auto" in sys.argv
    dry = "--dry" in sys.argv
    export = None
    export_path = None
    for i, a in enumerate(sys.argv):
        if a == "--export" and i + 1 < len(sys.argv) and sys.argv[i + 1] in ("csv", "json"):
            export = sys.argv[i + 1]
            export_path = sys.argv[i + 2] if i + 2 < len(sys.argv) and not sys.argv[i + 2].startswith("--") else None

    if cmd in ("setup",):
        cmd_setup()
    elif cmd in ("login",):
        cmd_login()
    elif cmd in ("optimize",):
        user_prompt = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
        cmd_optimize(user_prompt)
    elif cmd in ("history",):
        last = 10
        company_filter = None
        since = None
        show_all = "--all" in sys.argv
        for i, a in enumerate(sys.argv):
            if a == "--last" and i + 1 < len(sys.argv):
                try: last = int(sys.argv[i + 1])
                except ValueError: pass
            elif a == "--company" and i + 1 < len(sys.argv):
                company_filter = sys.argv[i + 1]
            elif a == "--since" and i + 1 < len(sys.argv):
                since = sys.argv[i + 1]
        cmd_history(last=last, company_filter=company_filter, since=since, show_all=show_all)
    elif cmd in ("blacklist",):
        action = sys.argv[2] if len(sys.argv) > 2 else None
        company = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_blacklist(action, company)
    elif cmd in ("status",):
        cmd_status()
    elif cmd in ("update",):
        cmd_update()
    elif cmd in ("help", "--help", "-h"):
        cmd_help()
    elif cmd == "--test" and len(sys.argv) > 2:
        if export and not export_path:
            console.print("  [red]![/red] --export requiere ruta. Ej: jobhunter --test email --export csv ofertas.csv")
            return
        cmd_run(
            test_email=sys.argv[2],
            time_filter=tf,
            auto_apply=auto,
            dry_run=dry,
            export_fmt=export,
            export_path=export_path,
        )
    elif cmd in ("run",):
        if export and not export_path:
            console.print("  [red]![/red] --export requiere ruta. Ej: jobhunter run --export csv ofertas.csv")
            return
        cmd_run(
            time_filter=tf,
            auto_apply=auto,
            dry_run=dry,
            export_fmt=export,
            export_path=export_path,
        )
    else:
        console.print(get_banner())
        console.print(f"  [red]✗[/red] Comando desconocido: [bold]{cmd}[/bold]")
        console.print("  [dim]Ejecuta 'jobhunter help' para ver comandos[/dim]")
        console.print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n  [dim]Cancelado.[/dim]\n")
        sys.exit(0)
