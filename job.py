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
BACK = "<"

def _setup_screen(current, total, title, subtitle=None):
    """Clear screen and show setup step with percentage bar."""
    if console.is_terminal:
        console.clear()
    console.print(get_banner())
    pct = int((current / total) * 100)
    filled = int(pct / 5)
    bar = "[cyan]" + "█" * filled + "[/cyan]" + "[dim]" + "░" * (20 - filled) + "[/dim]"
    console.print(f"  {bar}  [bold]{pct}%[/bold]")
    console.print()
    console.print(f"  [bold]{title}[/bold]")
    if subtitle:
        console.print(f"  [dim]{subtitle}[/dim]")
    if current > 0:
        console.print(f"  [dim]Escribe '<' para volver[/dim]")
    console.print()

def _ask(label, **kwargs):
    """Prompt wrapper that detects '<' for go-back navigation and cleans input."""
    val = Prompt.ask(label, **kwargs)
    val = val.strip().strip('"').strip("'")
    if val == BACK:
        return None
    return val


def _mask_secret(value):
    """Return a masked preview of a secret, showing only the first chars."""
    if not value:
        return ""
    v = str(value)
    if len(v) <= 4:
        return "***"
    return v[:4] + "***"


def _ask_secret(label, current, password=False):
    """Ask for a secret. Muestra el valor enmascarado en la misma linea del prompt.
    Enter mantiene el valor actual. Devuelve None si '<' (volver)."""
    if current:
        shown_label = f"{label} [dim]({_mask_secret(current)})[/dim]"
        val = Prompt.ask(shown_label, password=password, default=current, show_default=False)
    else:
        val = Prompt.ask(label, password=password, default="")
    val = (val or "").strip().strip('"').strip("'")
    if val == BACK:
        return None
    return val


def cmd_setup():
    cfg = load_config()
    profile = cfg.get("profile", {})
    from src.cv_templates import TEMPLATES, DEFAULT_TEMPLATE

    lang_options = {"1": "Espanol", "2": "Ingles", "3": "Espanol e Ingles"}
    mode_options = {"1": "Remoto", "2": "Hibrido", "3": "Presencial", "4": "Cualquiera"}

    TOTAL = 10
    # ── Step functions: return "back" to go back, anything else continues ──

    def step_links():
        _setup_screen(0, TOTAL, "Links profesionales", "Opcional, Enter para saltar")
        portfolio = _ask("  Portfolio / web personal", default=profile.get("portfolio", ""))
        if portfolio is None: return "back"
        profile["portfolio"] = portfolio
        console.print()
        linkedin = _ask("  Perfil de LinkedIn", default=profile.get("linkedin", ""))
        if linkedin is None: return "back"
        profile["linkedin"] = linkedin

    def step_job_types():
        _setup_screen(1, TOTAL, "Que tipo de empleo buscas?")
        if cfg.get("gemini_api_key") and profile.get("skills"):
            with console.status("  [dim]Generando sugerencias...[/dim]"):
                try:
                    s = json.dumps(profile.get("skills",{}))
                    e = json.dumps(profile.get("experience",[])[:3])
                    result = call_gemini(cfg, f"Basado en skills: {s} y experiencia: {e}, sugiere 6 tipos de empleo. JSON array: [\"tipo1\",\"tipo2\"]")
                    for i, sg in enumerate(json.loads(result), 1):
                        console.print(f"  [cyan]{i}.[/cyan] {sg}")
                    console.print()
                except: pass
        console.print("  [dim]Separados por coma[/dim]")
        val = _ask("  Tipos de empleo", default=cfg.get("job_types_raw", ""))
        if val is None: return "back"
        if not val: val = "software developer"
        cfg["job_types_raw"] = val

    def step_search_langs():
        _setup_screen(2, TOTAL, "Idiomas de busqueda", "En que idiomas buscar ofertas en LinkedIn")
        for k, v in lang_options.items():
            console.print(f"  [cyan]{k}.[/cyan] {v}")
        choice = _ask("  Selecciona", default=cfg.get("search_languages", "3"))
        if choice is None: return "back"
        cfg["search_languages"] = choice if choice in lang_options else "3"

    def step_user_langs():
        _setup_screen(3, TOTAL, "Tus idiomas y nivel", "Se usa para filtrar ofertas y para el CV")
        console.print("  [dim]Ej: Espanol:Nativo, Ingles:B1[/dim]")
        console.print("  [dim]Niveles: Nativo, Avanzado (C1-C2), Intermedio (B1-B2), Basico (A1-A2)[/dim]")
        existing = cfg.get("user_languages", [])
        default = ", ".join(lang["language"] + ":" + lang["level"] for lang in existing) if existing else ""
        val = _ask("  Idiomas", default=default)
        if val is None: return "back"
        langs = []
        for part in val.split(","):
            part = part.strip()
            if ":" in part:
                n, lv = part.split(":", 1)
                langs.append({"language": n.strip(), "level": lv.strip()})
            elif part:
                langs.append({"language": part, "level": "Nativo"})
        cfg["user_languages"] = langs

    def step_work_mode():
        _setup_screen(4, TOTAL, "Modalidad de trabajo")
        for k, v in mode_options.items():
            console.print(f"  [cyan]{k}.[/cyan] {v}")
        choice = _ask("  Selecciona", default=cfg.get("work_mode", "4"))
        if choice is None: return "back"
        if choice not in mode_options: choice = "4"
        cfg["work_mode"] = choice
        cfg["work_mode_label"] = mode_options[choice]
        if choice in ("2", "3"):
            console.print()
            loc = _ask("  Tu ubicacion (ciudad, pais)", default=cfg.get("user_location", profile.get("location", "")))
            if loc is None: return "back"
            cfg["user_location"] = loc
        else:
            cfg["user_location"] = cfg.get("user_location", "")

    def step_cv_template():
        _setup_screen(5, TOTAL, "Plantilla de CV", "Estilo visual del PDF generado")
        current_tmpl = cfg.get("cv_template", DEFAULT_TEMPLATE)
        tmpl_keys = list(TEMPLATES.keys())
        for i, key in enumerate(tmpl_keys, 1):
            t = TEMPLATES[key]
            marker = " [green]<< actual[/green]" if key == current_tmpl else ""
            console.print(f"  [cyan]{i}.[/cyan] {t['name']} — [dim]{t['description']}[/dim]{marker}")
        choice = _ask("  Selecciona", default=str(tmpl_keys.index(current_tmpl) + 1))
        if choice is None: return "back"
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(tmpl_keys): cfg["cv_template"] = tmpl_keys[idx]
        except ValueError: pass

    def step_gemini():
        _setup_screen(6, TOTAL, "Gemini AI", "Obtiene la clave gratis en https://aistudio.google.com/apikey")
        while True:
            key = _ask_secret("  Clave API", cfg.get("gemini_api_key", ""))
            if key is None: return "back"
            if not key: console.print("  [red]Obligatoria.[/red]"); continue
            key = key.replace(" ", "")
            with console.status("  [dim]Verificando...[/dim]"):
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
                    requests.post(url, json={"contents":[{"parts":[{"text":"test"}]}]}, timeout=10).raise_for_status()
                    cfg["gemini_api_key"] = key
                    console.print("  [green]>[/green] Clave valida")
                    break
                except:
                    console.print("  [red]![/red] Clave invalida. Intenta de nuevo.")
        # Model selection inline
        console.print()
        current = cfg.get("gemini_model", "gemini-2.5-flash")
        console.print(f"  [bold]Modelo[/bold] [dim](Enter para mantener {current})[/dim]")
        for i, m in enumerate(GEMINI_MODELS, 1):
            marker = " [green]<< actual[/green]" if m == current else ""
            console.print(f"  [cyan]{i}.[/cyan] {m}{marker}")
        choice = _ask("  Selecciona", default=str(GEMINI_MODELS.index(current) + 1 if current in GEMINI_MODELS else 1))
        if choice is None: return "back"
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(GEMINI_MODELS): cfg["gemini_model"] = GEMINI_MODELS[idx]
        except ValueError: pass

    def step_gmail():
        _setup_screen(7, TOTAL, "Gmail + Contrasena de aplicacion", "Cuenta Google > Seguridad > Contrasenas de aplicacion")
        while True:
            email = _ask("  Gmail", default=cfg.get("smtp_email", ""))
            if email is None: return "back"
            if not re.match(r'^[^@]+@gmail\.com$', email):
                console.print("  [red]![/red] Debe ser @gmail.com"); continue
            pwd = _ask_secret("  Contrasena de app", cfg.get("smtp_password", ""), password=True)
            if pwd is None: return "back"
            pwd = pwd.replace(" ", "")
            if not pwd or len(pwd) < 10:
                console.print("  [red]![/red] Minimo 16 caracteres"); continue
            with console.status("  [dim]Verificando SMTP...[/dim]"):
                try:
                    with smtplib.SMTP("smtp.gmail.com", 587) as s:
                        s.starttls(); s.login(email, pwd)
                    cfg["smtp_email"] = email; cfg["smtp_password"] = pwd
                    console.print("  [green]>[/green] SMTP verificado")
                    return
                except Exception as e:
                    console.print(f"  [red]![/red] {e}")

    def step_cv():
        _setup_screen(8, TOTAL, "Tu CV actual", "Ruta al archivo PDF — OBLIGATORIO")
        console.print("  [dim]El CV se lee con IA para extraer tu experiencia real. Sin CV no se puede continuar.[/dim]")
        while True:
            cv = _ask("  Ruta del CV (.pdf)", default=cfg.get("cv_path", ""))
            if cv is None: return "back"
            if not cv:
                console.print("  [red]![/red] El CV es obligatorio. La IA lo usa para adaptar tu experiencia REAL a cada oferta.")
                continue
            if not os.path.exists(cv):
                console.print(f"  [red]![/red] No encontrado: {cv}"); continue
            # Verificar que se puede leer (permisos)
            try:
                with open(cv, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
            except PermissionError:
                console.print(f"  [red]![/red] Sin permisos para leer: {cv}")
                console.print("  [dim]Copia el archivo a otra ubicacion o ajusta los permisos e intenta de nuevo.[/dim]")
                continue
            except Exception as e:
                console.print(f"  [red]![/red] No se pudo leer el archivo: {e}")
                continue
            # Leer con Gemini
            with console.status("  [dim]Leyendo CV con Gemini AI...[/dim]"):
                try:
                    result = call_gemini_vision(cfg, """Lee este CV/resume y extrae TODA la informacion en JSON.
Adapta las categorias de skills al perfil real de la persona (no asumas que es tech).
{"name":"","title":"titulo profesional","email":"","phone":"","linkedin":"","portfolio":"","location":"",
"summary":"resumen profesional completo",
"skills": "objeto con categorias relevantes al perfil, ej: para tech {backend:[],frontend:[]}, para marketing {estrategia:[],herramientas:[]}, para diseno {tools:[],especialidades:[]}, etc.",
"experience":[{"company":"","role":"","period":"","description":"descripcion completa de logros y responsabilidades"}],
"education":[{"institution":"","degree":"","period":""}],
"projects":[{"name":"","description":"","tech":[]}],"achievements":[]}
SOLO JSON valido.""", b64, "application/pdf")
                    nonlocal profile
                    parsed = json.loads(result)
                    if not parsed.get("name"):
                        console.print(f"  [red]![/red] El CV parece invalido o la IA no pudo extraer datos. Verifica el PDF.")
                        continue
                    # Preservar lo que el usuario ingreso manualmente en step_links (portfolio/linkedin)
                    # Solo usar lo extraido del CV si el usuario no lo ingreso
                    user_portfolio = profile.get("portfolio", "")
                    user_linkedin = profile.get("linkedin", "")
                    profile = parsed
                    if user_portfolio:
                        profile["portfolio"] = user_portfolio
                    if user_linkedin:
                        profile["linkedin"] = user_linkedin
                    cfg["cv_path"] = cv
                    console.print(f"  [green]>[/green] CV leido — {profile.get('name', '?')}")
                    return
                except Exception as e:
                    console.print(f"  [red]![/red] Error al procesar con IA: {e}")
                    console.print("  [dim]Intenta con otro PDF o revisa que la clave de Gemini sea valida.[/dim]")
                    continue

    def step_linkedin_login():
        _setup_screen(9, TOTAL, "Login en LinkedIn", "Se abrira Chrome para iniciar sesion")
        if os.path.exists(SESSION_DIR):
            console.print("  [green]>[/green] Sesion existente detectada")
            skip = _ask("  Saltar login? (s/n)", default="s")
            if skip is None: return "back"
            if skip.lower() in ("s", "si", "y", "yes"):
                return
        _do_linkedin_login()

    # ── State machine (ordered easy → hard) ──
    steps = [step_links, step_job_types, step_search_langs, step_user_langs,
             step_work_mode, step_cv_template, step_gemini, step_gmail,
             step_cv, step_linkedin_login]
    idx = 0
    while idx < len(steps):
        result = steps[idx]()
        if result == "back":
            idx = max(0, idx - 1)
        else:
            idx += 1

    # Save profile + generate queries with AI
    cfg["profile"] = profile
    lang = cfg.get("search_languages", "3")
    lang_label = {"1": "espanol", "2": "ingles", "3": "espanol e ingles"}.get(lang, "espanol e ingles")
    wm_label = cfg.get("work_mode_label", "Cualquiera")
    job_types = cfg.get("job_types_raw", "software developer")
    location = cfg.get("user_location", "")

    queries = []
    location_line = "- Ubicacion: " + location if location else ""
    with console.status("  [dim]Generando queries de busqueda con IA...[/dim]"):
        try:
            prompt = f"""Eres un experto en reclutamiento y busqueda de empleo en LinkedIn.
Tu trabajo es generar queries de busqueda que encuentren PUBLICACIONES de reclutadores que estan buscando candidatos activamente en LinkedIn.

IMPORTANTE: Estas queries se usan en la barra de busqueda de LinkedIn, seccion "Contenido" (posts), NO en la seccion de empleos.
Deben encontrar posts donde reclutadores publican ofertas con email de contacto para recibir CVs.

PERFIL DEL CANDIDATO:
- Busca empleo como: {job_types}
- Modalidad: {wm_label}
{location_line}
- Idiomas de busqueda: {lang_label}

REGLAS:
- Genera EXACTAMENTE 20 queries variadas
- Usa terminos que los reclutadores REALMENTE usan al publicar en LinkedIn (no terminos de buscador de empleo)
- Incluye variaciones: "enviar CV", "buscamos", "contratando", "vacante", "hiring", "looking for", "send resume", "we are hiring", "join our team"
- Mezcla el titulo exacto con variaciones del sector (ej: si busca "Backend Developer", incluir "desarrollador backend", "backend engineer", "ingeniero backend")
- Si idioma es espanol: queries en espanol
- Si idioma es ingles: queries en ingles
- Si es ambos: mezcla queries en ambos idiomas
- Si modalidad no es "Cualquiera", incluirla en algunas queries pero no en todas
- Queries cortas (3-6 palabras), como alguien escribiria en la barra de busqueda
- NO repitas queries similares con solo cambio de orden de palabras

JSON array: ["query1", "query2", ...]
SOLO el JSON array, nada mas."""
            result = call_gemini(cfg, prompt)
            queries = json.loads(result)
            if not isinstance(queries, list) or len(queries) < 5:
                raise ValueError("Pocas queries generadas")
        except Exception:
            pass

    # Fallback: templates basicos si la IA falla
    if not queries:
        wm = wm_label.lower()
        mode_terms_es = {"remoto": "remoto", "hibrido": "hibrido", "presencial": "presencial", "cualquiera": ""}
        mode_terms_en = {"remoto": "remote", "hibrido": "hybrid", "presencial": "onsite", "cualquiera": ""}
        for jt in [j.strip() for j in job_types.split(",") if j.strip()]:
            if lang in ("1", "3"):
                queries.extend([f"enviar CV {jt} {mode_terms_es.get(wm,'')}".strip(), f"busco {jt} {mode_terms_es.get(wm,'')}".strip(),
                                f"contratando {jt} {mode_terms_es.get(wm,'')}".strip(), f"vacante {jt} {mode_terms_es.get(wm,'')}".strip()])
            if lang in ("2", "3"):
                queries.extend([f"hiring {jt} {mode_terms_en.get(wm,'')}".strip(), f"looking for {jt} {mode_terms_en.get(wm,'')}".strip(),
                                f"send CV {jt} {mode_terms_en.get(wm,'')}".strip(), f"job opening {jt} {mode_terms_en.get(wm,'')}".strip()])

    cfg["search_queries"] = queries
    save_config(cfg)

    # Summary
    if console.is_terminal: console.clear()
    console.print(get_banner())
    console.print(Panel(
        f"[bold green]> Configuracion completa[/bold green]\n\n"
        f"  [dim]Nombre[/dim]      {profile.get('name', '?')}\n"
        f"  [dim]Correo[/dim]      {cfg.get('smtp_email', '?')}\n"
        f"  [dim]CV[/dim]          {cfg.get('cv_path', '-')}\n"
        f"  [dim]Modelo[/dim]      {cfg.get('gemini_model', '?')}\n"
        f"  [dim]Plantilla[/dim]   {cfg.get('cv_template', 'modern')}\n"
        f"  [dim]Busquedas[/dim]   {len(queries)} generadas\n\n"
        f"  Siguiente paso: [cyan]jobhunter run[/cyan]",
        border_style="green", title="[bold]Resumen[/bold]"
    ))


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
def cmd_run(
    test_email=None,
    time_filter="24h",
    auto_apply=False,
    dry_run=False,
    export_fmt=None,
    export_path=None,
):
    cfg = load_config()
    kb = load_kb()

    if not is_configured():
        console.print("  [red]✗[/red] Falta configuracion. Ejecuta: [cyan]jobhunter setup[/cyan]")
        return
    if not os.path.exists(SESSION_DIR):
        console.print("  [red]✗[/red] Sin sesion LinkedIn. Ejecuta: [cyan]jobhunter login[/cyan]")
        return

    console.print(get_banner())
    mode = "test" if test_email else "run"

    time_labels = {"24h": "Ultimas 24h", "week": "Esta semana", "month": "Este mes"}
    mode_label = f"[yellow]TEST → {test_email}[/yellow]" if test_email else "[green]Reclutadores[/green]"
    dry_line = "\n  [dim]Dry-run[/dim]   [yellow]Si — sin enviar emails[/yellow]" if dry_run else ""
    console.print(Panel(
        f"  [dim]Perfil[/dim]     {cfg['profile'].get('name','?')}\n"
        f"  [dim]Destino[/dim]    {mode_label}\n"
        f"  [dim]Periodo[/dim]    {time_labels.get(time_filter, time_filter)}\n"
        f"  [dim]Queries[/dim]    {len(cfg.get('search_queries',[]))}{dry_line}",
        border_style="cyan", title="[bold]Sesion[/bold]"
    ))

    kill_playwright_zombies()
    queries = cfg.get("search_queries", ["enviar CV backend developer"])

    # ── Phase 1: Scrape ──
    console.print()
    console.print("  [bold dim]Buscando en LinkedIn...[/bold dim]")
    all_posts = []
    seen = set()

    try:
        with sync_playwright() as p:
            chrome = find_chrome()
            browser = p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR, headless=True,
                viewport={"width":1300,"height":850}, executable_path=chrome,
            )
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            if "login" in page.url or "signin" in page.url:
                console.print("  [red]![/red] Sesion expirada. Ejecuta: [cyan]jobhunter login[/cyan]")
                browser.close(); return

            total_q = len(queries)
            total_emails_found = 0
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=30),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                console=console,
            ) as prog:
                task = prog.add_task("Buscando...", total=total_q)
                for qi, query in enumerate(queries, 1):
                    prog.update(task, description=f"[dim]{query[:45]}[/dim]")
                    posts = scrape_posts(page, query, time_filter=time_filter)
                    for pi in posts:
                        key = pi["text"][:150]
                        if key not in seen:
                            seen.add(key)
                            all_posts.append(pi)
                    total_emails_found = sum(len(p.get("emails_found",[])) for p in all_posts)
                    prog.advance(task)
                    time.sleep(random.uniform(2, 5))

            # Screenshots (optional, quick)
            text_boxes = page.query_selector_all('span[data-testid="expandable-text-box"]')
            for post in all_posts:
                post["screenshots"] = []
                try:
                    if post["index"] < len(text_boxes):
                        ss = text_boxes[post["index"]].screenshot()
                        post["screenshots"].append(base64.b64encode(ss).decode())
                except: pass

            browser.close()
    except KeyboardInterrupt:
        console.print("\n  [dim]Cancelado.[/dim]")
        return
    except Exception:
        pass

    posts_with_emails = [p for p in all_posts if p.get("emails_found")]
    posts_no_emails = len(all_posts) - len(posts_with_emails)
    console.print(f"  [bold]{len(all_posts)}[/bold] posts  ·  [bold]{len(posts_with_emails)}[/bold] con email  ·  [dim]{posts_no_emails} sin email (omitidos)[/dim]")

    if not posts_with_emails:
        console.print()
        console.print("  [yellow]![/yellow] No se encontraron posts con email. Intenta un periodo mas amplio.")
        console.print("    [dim]Ej: jobhunter run --time week[/dim]")
        return

    # ── Phase 2: Analyze (only posts with emails to save tokens) ──
    console.print()
    console.print("  [bold dim]Analizando ofertas...[/bold dim]")
    offers = []

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), TextColumn("{task.completed}/{task.total}"),
                  TimeElapsedColumn(), console=console) as prog:
        task = prog.add_task("Analizando...", total=len(posts_with_emails))
        for post in posts_with_emails:
            if len(post.get("text","")) < 50:
                prog.advance(task); continue
            ss = post.get("screenshots",[None])[0] if post.get("screenshots") else None
            a = agent_filter(cfg, post["text"], ss)
            if a.get("is_job") and a.get("is_relevant", True):
                a["job_title"] = a.get("job_title") or "Software Developer"
                a["company"] = a.get("company") or "Empresa"
                a["post_url"] = post.get("post_url")
                offers.append(a)
            prog.advance(task)
            time.sleep(1.5)

    # Clean emails: remove "null", "none", empty strings
    for o in offers:
        email = o.get("contact_email", "")
        if not email or email.lower() in ("null", "none", "n/a", "no encontrado"):
            o["contact_email"] = None

    # Only keep offers with valid email
    offers_with_email = [o for o in offers if o.get("contact_email")]
    offers_no_email = [o for o in offers if not o.get("contact_email")]

    # Deduplicate within this batch: same normalized title + company
    deduped = deduplicate_offers_by_title_company(offers_with_email)
    batch_dupes = len(offers_with_email) - len(deduped)
    offers_with_email = deduped

    # Filter blacklisted companies
    rejected = [r.lower() for r in kb.get("rejected_companies", [])]
    before_bl = len(offers_with_email)
    offers_with_email = [o for o in offers_with_email if (o.get("company") or "").lower() not in rejected]
    blacklisted = before_bl - len(offers_with_email)
    blacklist_info = "  ·  " + str(blacklisted) + " bloqueadas" if blacklisted else ""

    console.print(
        f"  [bold]{len(offers)}[/bold] ofertas  ·  "
        f"[green]{len(offers_with_email)}[/green] con email  ·  "
        f"[dim]{batch_dupes} duplicadas  ·  {len(offers_no_email)} sin email{blacklist_info}[/dim]"
    )
    console.print()

    if offers_with_email:
        tw = shutil.get_terminal_size((80, 24)).columns
        wide = tw >= 100
        extra_wide = tw >= 130
        table = Table(border_style="cyan", title="[bold]Ofertas encontradas[/bold]", expand=False, show_lines=False, padding=(0, 1))
        table.add_column("#", style="dim", width=3, justify="right")
        table.add_column("Puesto", max_width=28 if wide else 20, style="bold")
        table.add_column("Empresa", max_width=16 if wide else 12)
        table.add_column("Modo", width=10)
        if wide:
            table.add_column("Ubicacion", max_width=18, style="dim")
            table.add_column("Lang", width=4, style="dim")
        if extra_wide:
            table.add_column("Salario", max_width=18, style="green")
        table.add_column("Email", max_width=26 if wide else 22, style="cyan")
        table.add_column("Post", width=6, justify="center")
        mode_icons = {"remote": "[green]Remoto[/green]", "hybrid": "[yellow]Hibrido[/yellow]", "onsite": "[red]Onsite[/red]", "unknown": "[dim]—[/dim]"}
        for i, o in enumerate(offers_with_email, 1):
            wm = mode_icons.get(o.get("work_mode", "unknown"), "[dim]—[/dim]")
            loc = o.get("location") or "—"
            if loc.lower() in ("null", "none", "n/a", "no especificado", "no mencionado"):
                loc = "—"
            la = (o.get("language", "?"))[:4].upper()
            salary = o.get("salary") or "—"
            if str(salary).lower() in ("null", "none", "n/a", "no mencionado", "no especificado"):
                salary = "—"
            post_link = f"[link={o['post_url']}]Ver[/link]" if o.get("post_url") else "[dim]—[/dim]"
            if extra_wide:
                table.add_row(str(i), o["job_title"][:28], o["company"][:16], wm, loc[:18], la, str(salary)[:18], o["contact_email"], post_link)
            elif wide:
                table.add_row(str(i), o["job_title"][:28], o["company"][:16], wm, loc[:18], la, o["contact_email"], post_link)
            else:
                table.add_row(str(i), o["job_title"][:20], o["company"][:12], wm, o["contact_email"], post_link)
        console.print(table)

    if not offers_with_email:
        console.print("  [yellow]![/yellow] No se encontraron ofertas con email de reclutador.")
        return

    # Filter duplicates: skip if same job_title + company was already applied within 30 days
    before_dedup = len(offers_with_email)
    offers_with_email = [
        o for o in offers_with_email
        if not was_already_applied(kb.get("applications", []), o.get("company", ""), o.get("job_title", ""))
    ]
    skipped = before_dedup - len(offers_with_email)
    if skipped:
        console.print(f"  [yellow]![/yellow] {skipped} omitidas (ya enviadas en los ultimos 30 dias)")

    if not offers_with_email:
        console.print("  [yellow]![/yellow] Todas las ofertas ya fueron enviadas anteriormente.")
        return

    # Export offers if requested
    if export_fmt and export_path and offers_with_email:
        os.makedirs(os.path.dirname(os.path.abspath(export_path)) or ".", exist_ok=True)
        export_fields = ["job_title", "company", "contact_email", "work_mode", "location", "salary", "language", "post_url"]
        if export_fmt == "csv":
            import csv
            with open(export_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=export_fields, extrasaction="ignore")
                w.writeheader()
                w.writerows(offers_with_email)
            console.print(f"  [green]>[/green] Exportado: {export_path}")
        elif export_fmt == "json":
            export_data = [{k: o.get(k) for k in export_fields} for o in offers_with_email]
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            console.print(f"  [green]>[/green] Exportado: {export_path}")

    # Use only offers with valid email for Phase 3
    offers = offers_with_email

    # ── Seleccion de ofertas (si no es modo auto) ──
    if not auto_apply:
        console.print()
        console.print("  [bold]Selecciona ofertas:[/bold]  [dim]numeros separados por coma, 'all' para todas, 'q' cancelar[/dim]")
        while True:
            choice = Prompt.ask("  Aplicar a")
            if choice.strip().lower() == 'q':
                console.print("  [yellow]Cancelado.[/yellow]")
                return
            if choice.strip().lower() in ('all', 'todas', '*'):
                console.print(f"  [green]✓[/green] Todas ({len(offers)})")
                break
            try:
                indices = [int(x.strip()) - 1 for x in choice.split(",")]
                selected = [offers[i] for i in indices if 0 <= i < len(offers)]
                if selected:
                    offers = selected
                    console.print(f"  [green]✓[/green] {len(offers)} seleccionadas")
                    break
                else:
                    console.print(f"  [red]✗[/red] Ningun numero valido (rango: 1-{len(offers)})")
            except (ValueError, IndexError):
                console.print(f"  [red]✗[/red] Formato invalido. Ej: 1,3,5 o 'all'")

    # ── Phase 3: Generate & Send ──
    console.print()
    phase3_label = "Generando CVs (dry-run, sin enviar)..." if dry_run else "Generando y enviando..."
    console.print(f"  [bold dim]{phase3_label}[/bold dim]")
    console.print()
    sent = 0
    generated = 0
    errors = 0
    results = []
    preview_send_all = False

    total = len(offers)
    for i, job in enumerate(offers, 1):
        title = (job.get("job_title") or "Posicion")[:80]
        company = (job.get("company") or "Empresa")[:40]
        rec_email = job.get("contact_email")
        to = test_email or rec_email
        label = f"  [cyan]{i}[/cyan][dim]/{total}[/dim] {title} [dim]→[/dim] {company}"

        cv_path = None
        edata = None
        cv_data = None
        try:
            with console.status(f"{label}  [dim]CV...[/dim]") as status:
                for retry in range(3):
                    try:
                        cv_data = agent_cv(cfg, job)
                        cv_fn = get_cv_filename(company, title)
                        cv_path = os.path.join(BASE_DIR, "output", "cvs", cv_fn)
                        os.makedirs(os.path.dirname(cv_path), exist_ok=True)
                        generate_cv_pdf(
                            cv_data,
                            cfg["profile"],
                            cv_path,
                            title,
                            company,
                            language=job.get("language", "es"),
                            template=cfg.get("cv_template", "modern"),
                        )
                        break
                    except Exception as e:
                        if retry == 2:
                            raise
                        time.sleep(5)

                status.update(f"{label}  [dim]Email...[/dim]")
                for retry in range(3):
                    try:
                        edata = agent_email(cfg, job, cv_data=cv_data)
                        break
                    except Exception as e:
                        if retry == 2:
                            raise
                        time.sleep(5)
        except Exception as e:
            console.print(f"{label}  [red]! {e}[/red]")
            errors += 1
            results.append({
                "job_title": title,
                "company": company,
                "recruiter_email": rec_email,
                "sent_to": to,
                "cv_path": cv_path,
            })
            time.sleep(2)
            continue

        body = edata["body"]
        if test_email:
            body = f"--- RECLUTADOR: {job.get('contact_name','?')} | EMAIL: {rec_email or '?'} | {company} ---\n\n" + body

        cv_name = os.path.basename(cv_path) if cv_path else ""

        if dry_run:
            generated += 1
            preview_text = (
                f"Para: {to}\n"
                f"Asunto: {edata['subject']}\n"
                f"CV adjunto: {cv_name or '—'}\n\n"
                f"{body}"
            )
            console.print(Panel(preview_text, border_style="dim", title="[dim]Dry run[/dim]"))
            console.print("       [yellow]·[/yellow] Dry-run: no se envia email (no se guarda en historial)")
            results.append({
                "job_title": title,
                "company": company,
                "recruiter_email": rec_email,
                "sent_to": to,
                "cv_path": cv_path,
                "dry_run": True,
            })
            console.print()
            time.sleep(2)
            continue

        do_send = False
        if auto_apply or preview_send_all:
            do_send = True
        else:
            while True:
                preview_text = (
                    f"Para: {to}\n"
                    f"Asunto: {edata['subject']}\n"
                    f"CV adjunto: {cv_name or '—'}\n\n"
                    f"{body}"
                )
                console.print(Panel(preview_text, border_style="cyan", title="[bold]Preview[/bold]"))
                choice = Prompt.ask(
                    "  (s) Enviar  (x) Saltar  (e) Editar asunto  (a) Enviar todos sin preguntar",
                    default="s",
                ).strip().lower()
                if choice in ("s", "send", ""):
                    do_send = True
                    break
                if choice in ("x", "skip"):
                    do_send = False
                    console.print("       [yellow]·[/yellow] Omitido")
                    break
                if choice in ("e", "edit"):
                    edata["subject"] = Prompt.ask("  Asunto", default=edata["subject"])
                    continue
                if choice in ("a", "all"):
                    preview_send_all = True
                    do_send = True
                    break
                console.print("  [red]✗[/red] Opcion invalida (s/x/e/a)")

        if not do_send:
            results.append({
                "job_title": title,
                "company": company,
                "recruiter_email": rec_email,
                "sent_to": to,
                "cv_path": cv_path,
                "skipped": True,
            })
            console.print()
            time.sleep(1)
            continue

        try:
            send_email(cfg, to, edata["subject"], body, cv_path)
            sent += 1
            console.print(f"{label}  [green]> Enviado[/green] [dim]→ {to}[/dim]")
            kb["applications"].append({
                "date": datetime.now().isoformat(),
                "job_title": title,
                "company": company,
                "recruiter_email": rec_email,
                "sent_to": to,
                "mode": mode,
                "post_url": job.get("post_url"),
            })
        except Exception as e:
            console.print(f"{label}  [red]! {e}[/red]")
            errors += 1

        results.append({
            "job_title": title,
            "company": company,
            "recruiter_email": rec_email,
            "sent_to": to,
            "cv_path": cv_path,
        })
        time.sleep(2)

    run_entry = {
        "date": datetime.now().isoformat(),
        "mode": "dry-run" if dry_run else mode,
        "posts": len(all_posts),
        "offers": len(offers),
        "sent": 0 if dry_run else sent,
    }
    if dry_run:
        run_entry["generated"] = generated
    kb["runs"].append(run_entry)
    save_kb(kb)

    # Summary
    err_str = f"[red]{errors}[/red]" if errors else "[dim]0[/dim]"
    if dry_run:
        summary_body = (
            f"  [dim]Posts scraped[/dim]       {len(all_posts)}\n"
            f"  [dim]Analizados[/dim]          {len(posts_with_emails)}  [dim](con email)[/dim]\n"
            f"  [dim]Ofertas[/dim]             {len(offers)}\n"
            f"  [dim]Generados[/dim]           [bold]{generated}[/bold]  [dim](CV + email)[/dim]\n"
            f"  [dim]Enviados[/dim]            [bold]0[/bold]  [dim](dry-run)[/dim]\n"
            f"  [dim]Errores[/dim]             {err_str}"
        )
    else:
        summary_body = (
            f"  [dim]Posts scraped[/dim]       {len(all_posts)}\n"
            f"  [dim]Analizados[/dim]          {len(posts_with_emails)}  [dim](con email)[/dim]\n"
            f"  [dim]Ofertas[/dim]             {len(offers)}\n"
            f"  [dim]Enviados[/dim]            [bold green]{sent}[/bold green]\n"
            f"  [dim]Errores[/dim]             {err_str}"
        )
    console.print(Panel(
        summary_body,
        border_style="green" if errors == 0 else "yellow", title="[bold]Resumen[/bold]"
    ))

    log = os.path.join(BASE_DIR, "output", "logs", f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


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
