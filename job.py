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
def cmd_login():
    console.print(get_banner())
    console.print()
    _do_linkedin_login()
    console.print()
    console.print("  [bold]Siguiente paso:[/bold]")
    console.print(f"  [cyan]jobhunter --test tu@email.com[/cyan]  prueba")
    console.print(f"  [cyan]jobhunter run[/cyan]                   enviar a reclutadores")
    console.print()


# ══════════════════════════════════════════════
# STATUS
# ══════════════════════════════════════════════
def cmd_status():
    console.print(get_banner())
    cfg = load_config()
    kb = load_kb()

    # Config section
    ok = lambda v: f"[green]✓[/green] {v}" if v else "[red]✗[/red] No configurado"
    secret_ok = lambda v: "[green]✓[/green] Configurado" if v else "[red]✗[/red] No configurado"

    runs = kb.get("runs", [])
    apps = kb.get("applications", [])
    total_sent = sum(1 for a in apps if a.get("mode") == "run")
    total_test = sum(1 for a in apps if a.get("mode") == "test")
    last_run = runs[-1]["date"][:10] if runs else "-"

    table = Table(border_style="cyan", show_header=False, padding=(0, 2), expand=False)
    table.add_column("key", style="dim", width=14)
    table.add_column("value")

    table.add_row("Nombre", cfg.get("profile",{}).get("name") or "[yellow]?[/yellow]")
    table.add_row("Correo", cfg.get("smtp_email") or "[red]No configurado[/red]")
    table.add_row("Clave API", secret_ok(cfg.get("gemini_api_key")))
    table.add_row("Contrasena", secret_ok(cfg.get("smtp_password")))
    table.add_row("Modelo", cfg.get("gemini_model", "gemini-2.5-flash"))
    table.add_row("CV", cfg.get("cv_path") or "[yellow]No configurado[/yellow]")
    table.add_row("Busqueda", cfg.get("job_types_raw") or "[yellow]No configurado[/yellow]")
    table.add_row("Queries", str(len(cfg.get("search_queries",[]))))
    table.add_row("LinkedIn", "[green]✓[/green] Sesion guardada" if os.path.exists(SESSION_DIR) else "[red]✗[/red] Sin sesion")

    console.print(Panel(table, border_style="cyan", title="[bold]Configuracion[/bold]"))

    # Stats
    stats_table = Table(show_header=False, border_style="dim", padding=(0, 2), expand=False)
    stats_table.add_column("key", style="dim", width=14)
    stats_table.add_column("value")
    stats_table.add_row("Ejecuciones", f"[bold]{len(runs)}[/bold]")
    stats_table.add_row("Enviados", f"[bold green]{total_sent}[/bold green]")
    stats_table.add_row("Tests", f"[bold]{total_test}[/bold]")
    stats_table.add_row("Ultima vez", last_run)

    console.print(Panel(stats_table, border_style="dim", title="[bold]Estadisticas[/bold]"))
    console.print()


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
# OPTIMIZE (AI agent for search query optimization)
# ══════════════════════════════════════════════
def cmd_optimize(user_prompt=None):
    from jobhunter.agents.optimizer import optimize_queries

    cfg = load_config()
    kb = load_kb()

    if not cfg.get("gemini_api_key"):
        console.print("  [red]✗[/red] Falta configuracion. Ejecuta: [cyan]jobhunter setup[/cyan]")
        return

    console.print(get_banner())
    console.print()
    console.print("  [bold dim]Optimizando queries de busqueda...[/bold dim]")
    console.print()

    current_queries = cfg.get("search_queries", [])

    with console.status("  [dim]Analizando y generando queries optimizadas...[/dim]"):
        result = optimize_queries(cfg, kb, user_prompt=user_prompt)

    new_queries = result.get("queries", [])
    analysis = result.get("analysis", "")
    summary = result.get("changes_summary", "")

    if not new_queries:
        console.print("  [yellow]![/yellow] El agente no genero queries nuevas.")
        return

    # Show analysis
    if analysis:
        console.print(f"  [bold]Analisis[/bold]")
        console.print(f"  [dim]{analysis}[/dim]")
        console.print()

    # Show diff
    console.print(f"  [bold]Queries actuales[/bold] [dim]({len(current_queries)})[/dim]")
    for q in current_queries:
        console.print(f"    [red]-[/red] [dim]{q}[/dim]")

    console.print()
    console.print(f"  [bold]Queries propuestas[/bold] [dim]({len(new_queries)})[/dim]")
    for q in new_queries:
        console.print(f"    [green]+[/green] {q}")

    console.print()
    if summary:
        console.print(f"  [dim]{summary}[/dim]")
        console.print()

    # Confirm
    if not Confirm.ask("  Aplicar cambios?", default=True):
        console.print("  [dim]Sin cambios.[/dim]")
        return

    cfg["search_queries"] = new_queries
    save_config(cfg)
    console.print(f"  [green]✓[/green] {len(new_queries)} queries guardadas")
    console.print()


# ══════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════
def cmd_history(last=10, company_filter=None, since=None, show_all=False):
    """Show application history from knowledge.json."""
    kb = load_kb()
    apps = kb.get("applications", [])
    if not apps:
        console.print("  [yellow]![/yellow] No hay aplicaciones registradas.")
        return

    # Sort by date descending
    apps = sorted(apps, key=lambda a: a.get("date", ""), reverse=True)

    # Filter by company
    if company_filter:
        cf = company_filter.lower()
        apps = [a for a in apps if cf in (a.get("company") or "").lower()]

    # Filter by date
    if since:
        try:
            cutoff = datetime.fromisoformat(since)
            apps = [a for a in apps if datetime.fromisoformat(a.get("date", "1970-01-01")) >= cutoff]
        except ValueError:
            console.print(f"  [red]![/red] Formato de fecha invalido: {since} (usa YYYY-MM-DD)")
            return

    # Limit
    if not show_all:
        apps = apps[:last]

    if not apps:
        console.print("  [yellow]![/yellow] No se encontraron aplicaciones con esos filtros.")
        return

    table = Table(border_style="cyan", padding=(0, 1), expand=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Fecha", style="dim", width=12)
    table.add_column("Puesto", style="bold", max_width=35)
    table.add_column("Empresa", max_width=25)
    table.add_column("Email reclutador", style="dim", max_width=30)
    table.add_column("Modo", width=6)
    table.add_column("Post", width=6, justify="center")

    for i, app in enumerate(apps, 1):
        date_str = app.get("date", "")[:10]
        mode = (app.get("mode") or "run").lower()
        mode_style = "[yellow]TEST[/yellow]" if mode == "test" else "[green]RUN[/green]"
        post_link = f"[link={app['post_url']}]Ver[/link]" if app.get("post_url") else "[dim]—[/dim]"
        table.add_row(
            str(i),
            date_str,
            (app.get("job_title") or "-")[:35],
            (app.get("company") or "-")[:25],
            (app.get("recruiter_email") or app.get("sent_to") or "-")[:30],
            mode_style,
            post_link,
        )

    console.print()
    console.print(Panel(table, border_style="cyan", title=f"[bold]Historial de aplicaciones ({len(apps)})[/bold]"))
    console.print()


def cmd_blacklist(action=None, company=None):
    """Manage company blacklist."""
    kb = load_kb()
    rejected = kb.get("rejected_companies", [])

    if action == "add" and company:
        norm = company.strip()
        if norm.lower() in [r.lower() for r in rejected]:
            console.print(f"  [yellow]![/yellow] '{norm}' ya esta en la blacklist.")
        else:
            rejected.append(norm)
            kb["rejected_companies"] = rejected
            save_kb(kb)
            console.print(f"  [green]>[/green] '{norm}' agregada a la blacklist.")
    elif action == "remove" and company:
        norm = company.strip().lower()
        match = [r for r in rejected if r.lower() == norm]
        if match:
            rejected.remove(match[0])
            kb["rejected_companies"] = rejected
            save_kb(kb)
            console.print(f"  [green]>[/green] '{match[0]}' removida de la blacklist.")
        else:
            console.print(f"  [yellow]![/yellow] '{company}' no esta en la blacklist.")
    else:
        # List
        if not rejected:
            console.print("  [dim]Blacklist vacia. Usa: jobhunter blacklist add \"Empresa\"[/dim]")
            return
        console.print()
        for i, r in enumerate(rejected, 1):
            console.print(f"  [cyan]{i}.[/cyan] {r}")
        console.print(f"\n  [dim]{len(rejected)} empresas bloqueadas[/dim]")
        console.print()


def cmd_help():
    console.print(get_banner())

    # Commands table
    cmds = Table(show_header=False, border_style="cyan", padding=(0, 2), expand=False)
    cmds.add_column("cmd", style="cyan", width=32)
    cmds.add_column("desc")
    cmds.add_row("jobhunter setup", "Configuracion inicial")
    cmds.add_row("jobhunter login", "Iniciar sesion en LinkedIn")
    cmds.add_row("jobhunter --test email@test.com", "Modo prueba (envia a tu correo)")
    cmds.add_row("jobhunter run", "Buscar y enviar a reclutadores")
    cmds.add_row("jobhunter optimize", "Optimizar queries con IA")
    cmds.add_row("jobhunter optimize \"...\"", "Optimizar con feedback tuyo")
    cmds.add_row("jobhunter history", "Historial de aplicaciones")
    cmds.add_row("jobhunter blacklist", "Ver/agregar/quitar empresas bloqueadas")
    cmds.add_row("jobhunter status", "Ver configuracion y estadisticas")
    cmds.add_row("jobhunter update", "Actualizar desde GitHub")
    cmds.add_row("jobhunter help", "Mostrar esta ayuda")
    console.print(Panel(cmds, border_style="cyan", title="[bold]Comandos[/bold]"))

    # Options table
    opts = Table(show_header=False, border_style="dim", padding=(0, 2), expand=False)
    opts.add_column("opt", style="cyan", width=20)
    opts.add_column("desc")
    opts.add_row("--time 24h", "Ultimas 24 horas [dim](defecto)[/dim]")
    opts.add_row("--time week", "Esta semana")
    opts.add_row("--time month", "Este mes")
    opts.add_row("--auto", "Aplicar a todas sin preguntar")
    opts.add_row("--dry", "Generar CVs y emails sin enviar [dim](run / --test)[/dim]")
    opts.add_row("--export csv|json ruta", "Exportar ofertas a archivo [dim](run)[/dim]")
    opts.add_row("--last N", "Ultimas N aplicaciones [dim](history)[/dim]")
    opts.add_row("--company \"...\"", "Filtrar por empresa [dim](history)[/dim]")
    opts.add_row("--since YYYY-MM-DD", "Desde fecha [dim](history)[/dim]")
    opts.add_row("--all", "Mostrar todas [dim](history)[/dim]")
    console.print(Panel(opts, border_style="dim", title="[bold]Opciones[/bold]"))

    # Selection info
    console.print("  [bold]Seleccion de ofertas[/bold]")
    console.print("  [dim]Despues del analisis puedes elegir a cuales aplicar:[/dim]")
    console.print("  [cyan]1,3,5[/cyan]  Solo esas  ·  [cyan]all[/cyan]  Todas  ·  [cyan]q[/cyan]  Cancelar")
    console.print()
    console.print("  [bold]Preview antes de enviar[/bold]  [dim](sin --auto ni --dry)[/dim]")
    console.print("  Tras generar CV y email: [cyan]s[/cyan] enviar · [cyan]x[/cyan] saltar · [cyan]e[/cyan] editar asunto · [cyan]a[/cyan] enviar todos")
    console.print()

    # Examples
    console.print("  [bold]Ejemplos[/bold]")
    console.print("  [dim]$ jobhunter --test mi@email.com[/dim]")
    console.print("  [dim]$ jobhunter run --time week[/dim]")
    console.print("  [dim]$ jobhunter run --auto[/dim]")
    console.print("  [dim]$ jobhunter run --time month --auto[/dim]")
    console.print("  [dim]$ jobhunter run --dry --time week[/dim]")
    console.print("  [dim]$ jobhunter optimize[/dim]")
    console.print('  [dim]$ jobhunter optimize "no encuentro ofertas remotas"[/dim]')
    console.print()


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
