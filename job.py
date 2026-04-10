#!/usr/bin/env python3
"""
JobHunter AI v1.0
Busqueda automatizada de empleo en LinkedIn + CVs con IA + Envio automatico

Uso:
    jobhunter                       Primera vez = asistente de config
    jobhunter --test <email>        Modo prueba (envia a tu correo)
    jobhunter run                   Buscar y enviar a reclutadores
    jobhunter login                 Iniciar sesion en LinkedIn
    jobhunter status                Ver configuracion y estadisticas
    jobhunter setup                 Configuracion inicial
"""
import json, os, sys, re, time, smtplib, subprocess, shutil, requests, base64
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
from rich.rule import Rule
from rich import print as rprint
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite-preview",
]
sys.path.insert(0, BASE_DIR)
from src.cv_builder import generate_cv_pdf, get_cv_filename
from src.offer_utils import (
    deduplicate_offers_by_title_company,
    extract_emails,
    was_already_applied,
)

console = Console()
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SESSION_DIR = os.path.join(BASE_DIR, ".session")
KB_PATH = os.path.join(BASE_DIR, "knowledge.json")  # Knowledge base

VERSION = "1.2.0"

BANNER_LARGE = """\
[bold cyan]
      ╦╔═╗╔╗  ╦ ╦╦ ╦╔╗╔╔╦╗╔═╗╦═╗
      ║║ ║╠╩╗ ╠═╣║ ║║║║ ║ ║╣ ╠╦╝
     ╚╝╚═╝╚═╝ ╩ ╩╚═╝╝╚╝ ╩ ╚═╝╩╚═ [white]AI[/white][/bold cyan]
[dim]  ──────────────────────────────────────
  Busqueda de empleo automatizada con IA
  Playwright + Gemini + Gmail  •  v{version}[/dim]
"""

BANNER_SMALL = """\
[bold cyan]  ╦╔═╗╔╗ ╦ ╦╦ ╦╔╗╔╔╦╗╔═╗╦═╗ [white]AI[/white]
  ║║ ║╠╩╗╠═╣║ ║║║║ ║ ║╣ ╠╦╝
 ╚╝╚═╝╚═╝╩ ╩╚═╝╝╚╝ ╩ ╚═╝╩╚═[/bold cyan]
[dim]  v{version}[/dim]
"""


def get_banner():
    width = shutil.get_terminal_size((80, 24)).columns
    b = BANNER_LARGE if width >= 76 else BANNER_SMALL
    return b.format(version=VERSION)


# ══════════════════════════════════════════════
# CONFIG & KNOWLEDGE BASE
# ══════════════════════════════════════════════
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def load_kb():
    if os.path.exists(KB_PATH):
        with open(KB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"runs": [], "applications": [], "rejected_companies": []}

def save_kb(kb):
    with open(KB_PATH, "w", encoding="utf-8") as f:
        json.dump(kb, f, indent=2, ensure_ascii=False)

def is_configured():
    cfg = load_config()
    return all(cfg.get(k) for k in ["gemini_api_key", "smtp_email", "smtp_password", "profile"])

# ══════════════════════════════════════════════
# GEMINI
# ══════════════════════════════════════════════
def gemini_url(cfg):
    model = cfg.get("gemini_model", "gemini-2.5-flash")
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={cfg['gemini_api_key']}"

def _gemini_request(url, payload, max_retries=3):
    """Make a Gemini API request with retry + exponential backoff for rate limits."""
    for attempt in range(max_retries):
        try:
            r = requests.post(url, json=payload, timeout=60)
            if r.status_code == 429:  # Rate limit
                wait = (attempt + 1) * 10  # 10s, 20s, 30s
                time.sleep(wait)
                continue
            if r.status_code >= 500:  # Server error
                time.sleep(5)
                continue
            r.raise_for_status()
            t = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if t.startswith("```"): t = t.split("\n",1)[1].rsplit("```",1)[0]
            return t
        except requests.exceptions.Timeout:
            time.sleep(5)
            continue
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(3)
    raise Exception("Gemini API: max retries exceeded")

def call_gemini(cfg, prompt):
    return _gemini_request(gemini_url(cfg), {"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.4}})

def call_gemini_vision(cfg, prompt, img_b64, mime="image/png"):
    return _gemini_request(gemini_url(cfg), {"contents":[{"parts":[{"text":prompt},{"inline_data":{"mime_type":mime,"data":img_b64}}]}],"generationConfig":{"temperature":0.3}})


# ══════════════════════════════════════════════
# EMAIL & UTILS
# ══════════════════════════════════════════════
def send_email(cfg, to, subject, body, cv_path=None, max_retries=3):
    """Send email with retry on failure."""
    msg = MIMEMultipart()
    msg["From"] = f"{cfg['profile']['name']} <{cfg['smtp_email']}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    if cv_path and os.path.exists(cv_path):
        with open(cv_path, "rb") as f:
            a = MIMEApplication(f.read(), _subtype="pdf")
            a.add_header("Content-Disposition", "attachment", filename=os.path.basename(cv_path))
            msg.attach(a)
    for attempt in range(max_retries):
        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as s:
                s.starttls(); s.login(cfg["smtp_email"], cfg["smtp_password"]); s.send_message(msg)
            return
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(3)

def find_chrome():
    for p in [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]:
        if os.path.exists(p): return p
    return shutil.which("chrome") or shutil.which("msedge")

def kill_playwright_zombies():
    """Kill only leftover Playwright-controlled Chrome instances (not the user's browser)."""
    # Only kill if .session/SingletonLock exists (means a previous Playwright crashed)
    lock = os.path.join(SESSION_DIR, "SingletonLock")
    if os.path.exists(lock):
        try: os.remove(lock)
        except: pass
        time.sleep(1)


# ══════════════════════════════════════════════
# SETUP WIZARD
# ══════════════════════════════════════════════
def _step_header(num, total, title, subtitle=None):
    """Print a styled step header."""
    console.print()
    progress_bar = "[cyan]" + "━" * num + "[/cyan]" + "[dim]" + "╌" * (total - num) + "[/dim]"
    console.print(f"  {progress_bar}  [dim]{num}/{total}[/dim]")
    console.print(f"  [bold]{title}[/bold]")
    if subtitle:
        console.print(f"  [dim]{subtitle}[/dim]")

def _phase_header(title):
    """Print a styled phase header for run command."""
    console.print()
    console.print(Rule(f"[bold]{title}[/bold]", style="cyan"))
    console.print()


def cmd_setup():
    console.print(get_banner())
    total_steps = 10

    cfg = load_config()

    # 1. Gemini
    _step_header(1, total_steps, "Clave API de Gemini", "Obtienla gratis en https://aistudio.google.com/apikey")
    while True:
        key = Prompt.ask("  Clave API", default=cfg.get("gemini_api_key", ""))
        if not key:
            console.print("  [red]La clave API es obligatoria.[/red]")
            continue
        with console.status("  [dim]Verificando...[/dim]"):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
                requests.post(url, json={"contents":[{"parts":[{"text":"test"}]}]}, timeout=10).raise_for_status()
                console.print("  [green]✓[/green] Clave valida")
                cfg["gemini_api_key"] = key
                break
            except:
                console.print("  [red]✗[/red] Clave API invalida. Intentalo de nuevo.")

    # 1b. Modelo de Gemini
    console.print()
    console.print(f"  [bold]Modelo de Gemini[/bold]")
    current_model = cfg.get("gemini_model", "gemini-2.5-flash")
    for i, m in enumerate(GEMINI_MODELS, 1):
        marker = " [green]◄ actual[/green]" if m == current_model else ""
        console.print(f"  [cyan]{i}.[/cyan] {m}{marker}")
    while True:
        choice = Prompt.ask("  Selecciona modelo", default=str(GEMINI_MODELS.index(current_model) + 1 if current_model in GEMINI_MODELS else 1))
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(GEMINI_MODELS):
                cfg["gemini_model"] = GEMINI_MODELS[idx]
                console.print(f"  [green]✓[/green] {GEMINI_MODELS[idx]}")
                break
        except ValueError:
            pass
        console.print(f"  [red]✗[/red] Selecciona un numero del 1 al {len(GEMINI_MODELS)}")

    # 2. Gmail
    _step_header(2, total_steps, "Correo Gmail + Contrasena de aplicacion", "Cuenta Google > Seguridad > Contrasenas de aplicacion")
    while True:
        email = Prompt.ask("  Gmail", default=cfg.get("smtp_email", ""))
        if not re.match(r'^[^@]+@gmail\.com$', email):
            console.print("  [red]✗[/red] Debe ser una cuenta @gmail.com")
            continue
        pwd = Prompt.ask("  Contrasena de app", default=cfg.get("smtp_password",""), password=True)
        if not pwd or len(pwd) < 10:
            console.print("  [red]✗[/red] La contrasena de aplicacion debe tener al menos 16 caracteres")
            continue
        with console.status("  [dim]Verificando SMTP...[/dim]"):
            try:
                with smtplib.SMTP("smtp.gmail.com", 587) as s:
                    s.starttls(); s.login(email, pwd)
                console.print("  [green]✓[/green] Conexion SMTP verificada")
                cfg["smtp_email"] = email
                cfg["smtp_password"] = pwd
                break
            except Exception as e:
                console.print(f"  [red]✗[/red] Error: {e}")
                console.print("  [yellow]  Verifica el App Password e intenta de nuevo.[/yellow]")

    # 3. CV
    _step_header(3, total_steps, "Tu CV actual", "Ruta al archivo PDF de tu CV")
    profile = cfg.get("profile", {})
    while True:
        cv = Prompt.ask("  Ruta del CV (.pdf)", default=cfg.get("cv_path", ""))
        if not cv:
            console.print("  [yellow]![/yellow] Sin CV. Puedes agregarlo despues con 'jobhunter setup'")
            break
        if not os.path.exists(cv):
            console.print(f"  [red]✗[/red] Archivo no encontrado: {cv}")
            continue
        cfg["cv_path"] = cv
        with console.status("  [dim]Leyendo CV con Gemini AI...[/dim]"):
            try:
                with open(cv, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                result = call_gemini_vision(cfg, """Lee este CV/resume y extrae TODA la informacion en JSON.
Adapta las categorias de skills al perfil real de la persona (no asumas que es tech).
{"name":"","title":"titulo profesional","email":"","phone":"","linkedin":"","portfolio":"","location":"",
"summary":"resumen profesional completo",
"skills": "objeto con categorias relevantes al perfil, ej: para tech {backend:[],frontend:[]}, para marketing {estrategia:[],herramientas:[]}, para diseno {tools:[],especialidades:[]}, etc.",
"experience":[{"company":"","role":"","period":"","description":"descripcion completa de logros y responsabilidades"}],
"education":[{"institution":"","degree":"","period":""}],
"projects":[{"name":"","description":"","tech":[]}],"achievements":[]}
SOLO JSON valido.""", b64, "application/pdf")
                profile = json.loads(result)
                console.print(f"  [green]✓[/green] CV leido — {profile.get('name', '?')}")
                skills_preview = ', '.join(list(profile.get('skills',{}).values())[0][:5]) if profile.get('skills') else '-'
                console.print(f"    [dim]{skills_preview}...[/dim]")
                break
            except Exception as e:
                console.print(f"  [red]✗[/red] Error leyendo CV: {e}")
                console.print("  [yellow]  Puedes continuar sin CV automatico.[/yellow]")
                break

    # 4. Portfolio
    _step_header(4, total_steps, "Portfolio / Web personal", "Opcional")
    portfolio = Prompt.ask("  URL", default=profile.get("portfolio", ""))
    profile["portfolio"] = portfolio

    # 5. LinkedIn
    _step_header(5, total_steps, "Perfil de LinkedIn")
    linkedin = Prompt.ask("  URL", default=profile.get("linkedin", ""))
    if linkedin and "linkedin.com" not in linkedin:
        console.print("  [yellow]![/yellow] Eso no parece un URL de LinkedIn")
    profile["linkedin"] = linkedin

    cfg["profile"] = profile

    # 6. Plantilla de CV
    _step_header(6, total_steps, "Plantilla de CV", "Estilo visual del PDF generado")
    from src.cv_templates import TEMPLATES, DEFAULT_TEMPLATE
    current_tmpl = cfg.get("cv_template", DEFAULT_TEMPLATE)
    tmpl_keys = list(TEMPLATES.keys())
    for i, key in enumerate(tmpl_keys, 1):
        t = TEMPLATES[key]
        marker = " [green]<< actual[/green]" if key == current_tmpl else ""
        console.print(f"  [cyan]{i}.[/cyan] {t['name']} — [dim]{t['description']}[/dim]{marker}")
    while True:
        tmpl_choice = Prompt.ask("  Selecciona", default=str(tmpl_keys.index(current_tmpl) + 1))
        try:
            idx = int(tmpl_choice) - 1
            if 0 <= idx < len(tmpl_keys):
                cfg["cv_template"] = tmpl_keys[idx]
                console.print(f"  [green]✓[/green] {TEMPLATES[tmpl_keys[idx]]['name']}")
                break
        except ValueError:
            pass
        console.print(f"  [red]![/red] Selecciona un numero del 1 al {len(tmpl_keys)}")

    # 7. Idiomas de busqueda
    _step_header(7, total_steps, "En que idiomas buscar ofertas?", "Las ofertas y CVs se generaran en el idioma de cada oferta")
    lang_options = {"1": "Espanol", "2": "Ingles", "3": "Espanol e Ingles"}
    for k, v in lang_options.items():
        console.print(f"  [cyan]{k}.[/cyan] {v}")
    lang_default = cfg.get("search_languages", "3")
    lang_choice = Prompt.ask("  Selecciona", default=lang_default)
    if lang_choice not in lang_options:
        lang_choice = "3"
    cfg["search_languages"] = lang_choice
    console.print(f"  [green]✓[/green] {lang_options[lang_choice]}")

    # 8. Idiomas que domina el usuario
    _step_header(8, total_steps, "Que idiomas manejas y a que nivel?", "Se usara para filtrar ofertas y para el CV. Ej: Espanol:Nativo, Ingles:B1")
    console.print("  [dim]Niveles: Nativo, Avanzado (C1-C2), Intermedio (B1-B2), Basico (A1-A2)[/dim]")
    existing_langs = cfg.get("user_languages", [])
    if existing_langs:
        console.print(f"  [dim]Actual: {', '.join(f'{l['language']}:{l['level']}' for l in existing_langs)}[/dim]")
    default_langs = ", ".join(f"{l['language']}:{l['level']}" for l in existing_langs) if existing_langs else ""
    langs_input = Prompt.ask("  Idiomas", default=default_langs)
    user_languages = []
    for part in langs_input.split(","):
        part = part.strip()
        if ":" in part:
            lang_name, level = part.split(":", 1)
            user_languages.append({"language": lang_name.strip(), "level": level.strip()})
        elif part:
            user_languages.append({"language": part.strip(), "level": "Nativo"})
    cfg["user_languages"] = user_languages
    if user_languages:
        for ul in user_languages:
            console.print(f"  [green]✓[/green] {ul['language']} — {ul['level']}")
    else:
        console.print("  [yellow]![/yellow] Sin idiomas configurados")

    # 9. Modalidad de trabajo
    _step_header(9, total_steps, "Que modalidad de trabajo buscas?")
    mode_options = {"1": "Remoto", "2": "Hibrido", "3": "Presencial", "4": "Cualquiera"}
    for k, v in mode_options.items():
        console.print(f"  [cyan]{k}.[/cyan] {v}")
    mode_default = cfg.get("work_mode", "4")
    mode_choice = Prompt.ask("  Selecciona", default=mode_default)
    if mode_choice not in mode_options:
        mode_choice = "4"
    cfg["work_mode"] = mode_choice
    cfg["work_mode_label"] = mode_options[mode_choice]
    console.print(f"  [green]✓[/green] {mode_options[mode_choice]}")

    # 9b. Ubicacion (si hibrido o presencial)
    if mode_choice in ("2", "3"):
        console.print()
        console.print(f"  [bold]Tu ubicacion[/bold]")
        console.print("  [dim]Ciudad y pais para filtrar ofertas cercanas[/dim]")
        location = Prompt.ask("  Ubicacion", default=cfg.get("user_location", profile.get("location", "")))
        cfg["user_location"] = location
    else:
        cfg["user_location"] = cfg.get("user_location", "")

    # 10. Preferencias de empleo
    _step_header(10, total_steps, "Que tipo de empleo buscas?")

    if profile.get("skills"):
        with console.status("  [dim]Generando sugerencias de tu CV...[/dim]"):
            try:
                s = json.dumps(profile.get("skills",{}))
                e = json.dumps(profile.get("experience",[])[:3])
                result = call_gemini(cfg, f"Basado en skills: {s} y experiencia: {e}, sugiere 6 tipos de empleo. JSON array: [\"tipo1\",\"tipo2\"]")
                suggestions = json.loads(result)
                console.print("  [dim]Sugerencias basadas en tu CV:[/dim]")
                for i, sg in enumerate(suggestions, 1):
                    console.print(f"  [cyan]{i}.[/cyan] {sg}")
                console.print()
            except:
                pass

    console.print("  [dim]Escribe los tipos de empleo separados por coma[/dim]")
    job_types = Prompt.ask("  Tipos de empleo", default=cfg.get("job_types_raw", ""))
    if not job_types:
        console.print("  [red]✗[/red] Debes especificar al menos un tipo de empleo.")
        job_types = Prompt.ask("  Tipos de empleo", default="backend developer")
    cfg["job_types_raw"] = job_types

    # Generar queries segun idioma y modalidad
    lang = cfg.get("search_languages", "3")
    work_mode = mode_options.get(mode_choice, "Cualquiera").lower()
    mode_terms_es = {"remoto": "remoto", "hibrido": "hibrido", "presencial": "presencial", "cualquiera": ""}
    mode_terms_en = {"remoto": "remote", "hibrido": "hybrid", "presencial": "onsite", "cualquiera": ""}
    mode_es = mode_terms_es.get(work_mode, "")
    mode_en = mode_terms_en.get(work_mode, "")

    queries = []
    for jt in [j.strip() for j in job_types.split(",") if j.strip()]:
        if lang in ("1", "3"):  # Espanol
            queries.extend([
                f"enviar CV {jt} {mode_es}".strip(),
                f"busco {jt} {mode_es}".strip(),
                f"contratando {jt} {mode_es}".strip(),
                f"vacante {jt} {mode_es}".strip(),
            ])
        if lang in ("2", "3"):  # Ingles
            queries.extend([
                f"hiring {jt} {mode_en}".strip(),
                f"looking for {jt} {mode_en}".strip(),
                f"send CV {jt} {mode_en}".strip(),
                f"job opening {jt} {mode_en}".strip(),
            ])
    cfg["search_queries"] = queries
    save_config(cfg)

    console.print()
    console.print(Panel(
        f"[bold green]✓ Configuracion completa[/bold green]\n\n"
        f"  [dim]Nombre[/dim]      {profile.get('name', '?')}\n"
        f"  [dim]Correo[/dim]      {cfg['smtp_email']}\n"
        f"  [dim]CV[/dim]          {cfg.get('cv_path', 'no configurado')}\n"
        f"  [dim]Portfolio[/dim]   {profile.get('portfolio', '-') or '-'}\n"
        f"  [dim]LinkedIn[/dim]    {profile.get('linkedin', '-') or '-'}\n"
        f"  [dim]Idiomas[/dim]     {lang_options[lang_choice]}\n"
        f"  [dim]Modalidad[/dim]   {mode_options[mode_choice]}\n"
        f"  [dim]Ubicacion[/dim]   {cfg.get('user_location', '-') or '-'}\n"
        f"  [dim]Busquedas[/dim]   {len(queries)} generadas\n\n"
        f"  Siguiente paso: [cyan]jobhunter login[/cyan]",
        border_style="green", title="[bold]Resumen[/bold]", subtitle="[dim]JobHunter AI[/dim]"
    ))


# ══════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════
def cmd_login():
    console.print(get_banner())
    kill_playwright_zombies()
    os.makedirs(SESSION_DIR, exist_ok=True)
    chrome = find_chrome()

    console.print(Panel(
        "[bold]Iniciar sesion en LinkedIn[/bold]\n\n"
        "  1. Se abrira Chrome\n"
        "  2. Inicia sesion con [bold]correo y contrasena[/bold]\n"
        "     [red]NO uses el boton de Google[/red] (bloqueado en automatizado)\n"
        "  3. Cuando estes dentro, [bold]cierra el navegador[/bold]",
        border_style="cyan", title="[bold]Login[/bold]"
    ))

    input("\n  Presiona Enter para abrir el navegador...")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR, headless=False,
            viewport={"width":1300,"height":850}, executable_path=chrome,
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://www.linkedin.com/login")
        console.print("  [dim]Esperando que inicies sesion y cierres el navegador...[/dim]")
        try:
            while True:
                time.sleep(1)
                try: _ = page.title()
                except: break
        except: pass

    console.print()
    console.print("  [green]✓[/green] Sesion de LinkedIn guardada")
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
def cmd_update():
    console.print(get_banner())

    with console.status("  [dim]Buscando actualizaciones...[/dim]"):
        try:
            result = subprocess.run(
                ["git", "-C", BASE_DIR, "pull", "--ff-only"],
                capture_output=True, text=True, timeout=30
            )
        except FileNotFoundError:
            console.print("  [red]✗[/red] git no esta instalado")
            return
        except subprocess.TimeoutExpired:
            console.print("  [red]✗[/red] Timeout al conectar con GitHub")
            return

    if result.returncode != 0:
        console.print(f"  [red]✗[/red] Error: {result.stderr.strip()}")
        return

    output = result.stdout.strip()
    if "Already up to date" in output or "Ya esta actualizado" in output:
        console.print("  [green]✓[/green] Ya tienes la ultima version")
    else:
        console.print("  [green]✓[/green] Actualizado correctamente")
        console.print(f"    [dim]{output}[/dim]")

    with console.status("  [dim]Verificando dependencias...[/dim]"):
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "rich", "requests", "playwright", "reportlab"],
            capture_output=True
        )

    console.print("  [green]✓[/green] Dependencias al dia")
    console.print()


# ══════════════════════════════════════════════
# SCRAPING (headless)
# ══════════════════════════════════════════════
# LinkedIn time filter URL params
TIME_FILTERS = {
    "24h": "past-24h",
    "week": "past-week",
    "month": "past-month",
}

def scrape_posts(page, query, max_scroll=4, time_filter="24h"):
    encoded = urllib.parse.quote(query)
    date_param = TIME_FILTERS.get(time_filter, "past-24h")
    try:
        page.goto(f"https://www.linkedin.com/search/results/content/?keywords={encoded}&datePosted=%5B%22{date_param}%22%5D&sortBy=%5B%22date_posted%22%5D", wait_until="domcontentloaded", timeout=60000)
    except Exception:
        return []  # Si timeout, saltar esta query y continuar con la siguiente
    page.wait_for_timeout(5000)
    for _ in range(max_scroll):
        page.evaluate("window.scrollBy(0, 800)")
        page.wait_for_timeout(2000)

    page.evaluate("""() => {
        document.querySelectorAll('button[data-testid="expandable-text-button"]').forEach(b => { try{b.click()}catch(e){} });
    }""")
    page.wait_for_timeout(2000)

    # Extract post URLs via 3-dot menu (contains activity URN in "Report" link)
    post_urls = {}
    try:
        listitems = page.locator('[role="listitem"]')
        for i in range(listitems.count()):
            try:
                menu_btn = listitems.nth(i).locator('button[aria-label*="controles"]').first
                if not menu_btn.is_visible(timeout=500):
                    continue
                menu_btn.click()
                page.wait_for_timeout(600)
                activity_id = page.evaluate(r"""() => {
                    const links = document.querySelectorAll('a[href*="entityUrn"]');
                    for (const l of links) {
                        const m = (l.getAttribute('href') || '').match(/activity%3A(\d+)/);
                        if (m) return m[1];
                    }
                    return null;
                }""")
                if activity_id:
                    post_urls[i] = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}"
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except Exception:
                try: page.keyboard.press("Escape")
                except: pass
    except Exception:
        pass

    posts = page.evaluate(r"""() => {
        const boxes = document.querySelectorAll('span[data-testid="expandable-text-box"]');
        const posts = []; const seen = new Set();
        boxes.forEach((box, idx) => {
            const text = box.innerText || '';
            if (text.length < 50) return;
            const key = text.substring(0, 100);
            if (seen.has(key)) return;
            seen.add(key);
            const emails = [...new Set((text.match(/[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g) || []))];
            posts.push({text: text.substring(0, 4000), emails_found: emails, index: idx});
        });
        return posts;
    }""")

    # Attach URLs to posts by matching index
    for post in posts:
        post["post_url"] = post_urls.get(post["index"])

    return posts


# ══════════════════════════════════════════════
# MULTI-AGENT SYSTEM
# ══════════════════════════════════════════════

# ── AGENT 1: FILTER (analiza posts, clasifica ofertas) ──
def agent_filter(cfg, text, ss=None):
    """Agent specialized in filtering job offers from LinkedIn posts."""
    emails = extract_emails(text)
    if ss:
        try:
            r = call_gemini_vision(cfg, "Extrae emails y detalles de este post LinkedIn. JSON: {\"email\":\"email o null\",\"details\":\"detalles\"}", ss)
            d = json.loads(r)
            if d.get("email") and d["email"] != "null": emails.append(d["email"])
            if d.get("details"): text += "\n" + d["details"]
        except: pass

    profile = cfg.get("profile", {})
    job_types = cfg.get("job_types_raw", "")
    profile_summary = profile.get("summary", "")
    profile_skills = profile.get("skills", {})
    work_mode_label = cfg.get("work_mode_label", "Cualquiera")
    user_location = cfg.get("user_location", "")
    user_languages = cfg.get("user_languages", [])

    work_mode_rule = ""
    if work_mode_label.lower() == "remoto":
        work_mode_rule = "- SOLO ofertas remotas o que permitan trabajo remoto. Descartar presenciales y hibridas."
    elif work_mode_label.lower() == "hibrido":
        work_mode_rule = f"- SOLO ofertas hibridas o remotas. Si es hibrida/presencial, debe ser compatible con la ubicacion del candidato: {user_location}"
    elif work_mode_label.lower() == "presencial":
        work_mode_rule = f"- SOLO ofertas presenciales o hibridas compatibles con la ubicacion del candidato: {user_location}"

    prompt = f"""ROLE: Eres un agente especializado en filtrar ofertas de trabajo de LinkedIn.
Tu unico trabajo es analizar publicaciones y determinar si contienen ofertas REALES y RELEVANTES para este candidato.

PERFIL DEL CANDIDATO:
- Busca empleo como: {job_types}
- Modalidad preferida: {work_mode_label}
{f'- Ubicacion del candidato: {user_location}' if user_location else ''}
- Idiomas del candidato: {', '.join(f"{l['language']} ({l['level']})" for l in user_languages) if user_languages else 'No especificados'}
- Resumen: {profile_summary[:300]}
- Habilidades: {json.dumps(profile_skills) if isinstance(profile_skills, dict) else str(profile_skills)[:500]}

PUBLICACION:
{text[:4000]}

EMAILS ENCONTRADOS EN EL TEXTO: {', '.join(emails) if emails else 'ninguno'}

REGLAS DE FILTRADO:
- Solo ofertas de TRABAJO reales (no cursos, certificaciones, logros personales, contenido general, publicidad)
- Relevante si el puesto tiene relacion con lo que busca el candidato: {job_types}
{work_mode_rule}
- Si la oferta REQUIERE un idioma con nivel avanzado o fluido que el candidato NO tiene a ese nivel, marcar is_relevant=false. Los idiomas del candidato son: {', '.join(f"{l['language']} ({l['level']})" for l in user_languages) if user_languages else 'No especificados'}
- Extraer SIEMPRE el email si existe en el texto
- Extraer empresa, titulo, descripcion COMPLETA con todos los detalles
- Extraer requisitos especificos (habilidades, herramientas, anos de experiencia, idiomas, etc.)
- Si la publicacion tiene multiples ofertas, toma la mas relevante para el candidato
- DETECTAR el idioma en que esta escrita la publicacion (es, en, pt, etc.)

JSON:
{{"is_job": true/false, "job_title": "titulo exacto del puesto", "company": "empresa", "description": "descripcion DETALLADA incluyendo responsabilidades y lo que se espera del candidato", "requirements": "TODOS los requisitos mencionados", "contact_email": "email@empresa.com o null", "contact_name": "nombre de quien publica", "location": "ubicacion", "work_mode": "remote/hybrid/onsite/unknown", "salary": "salario o null", "language": "es/en/pt/fr/etc", "is_relevant": true/false, "relevance_reason": "razon concreta"}}

Si NO es oferta: {{"is_job": false, "relevance_reason": "razon"}}
SOLO JSON valido."""

    try:
        a = json.loads(call_gemini(cfg, prompt))
        ce = a.get("contact_email", "")
        if not ce or str(ce).lower() in ("null", "none", "n/a"):
            a["contact_email"] = None
        if emails and not a.get("contact_email"):
            a["contact_email"] = emails[0]
        return a
    except Exception as e:
        return {"is_job": False, "relevance_reason": str(e)}


# ── AGENT 2: CV WRITER (genera CVs personalizados) ──
def agent_cv(cfg, job):
    """Agent specialized in generating personalized CVs tailored to each job."""
    p = cfg["profile"]
    title = job.get("job_title", "Profesional")
    company = job.get("company", "Empresa")
    desc = job.get("description", "")
    reqs = job.get("requirements", "")
    lang = job.get("language", "es")

    lang_names = {"es": "ESPAÑOL", "en": "INGLES", "pt": "PORTUGUES", "fr": "FRANCES", "de": "ALEMAN"}
    lang_name = lang_names.get(lang, "ESPAÑOL")

    prompt = f"""ROLE: Eres un agente experto en redaccion de CVs profesionales.
Tu trabajo es tomar el perfil del candidato y REESCRIBIRLO para que encaje perfectamente con una oferta especifica.
Esto funciona para CUALQUIER tipo de trabajo: tecnologia, marketing, ventas, diseno, administracion, salud, educacion, etc.

REGLAS CRITICAS:
- ESCRIBE TODO EL CV EN {lang_name}. La oferta esta en {lang_name} y el CV debe estar en el MISMO idioma.
- TEXTO PLANO UNICAMENTE. PROHIBIDO usar markdown: nada de **negritas**, *italicas*, `codigo`, # encabezados, ni ningun formato. Solo texto limpio.
- Usa la MISMA TERMINOLOGIA de la oferta. Si la oferta dice "Community Manager", el CV dice "Community Manager". Si dice "Backend Developer", dice "Backend Developer".
- NO traduzcas terminos que en la industria se usan en su idioma original
- Adapta TODO el CV al sector y lenguaje de la oferta
- PROHIBIDO INVENTAR. No agregues habilidades, tecnologias, idiomas, certificaciones, logros o experiencias que NO esten en el perfil del candidato. Solo puedes REORDENAR, REFORMULAR y DESTACAR lo que YA existe. Si la oferta pide algo que el candidato no tiene, simplemente no lo menciones.
- IDIOMAS: Solo incluye los idiomas que el candidato realmente maneja. Los idiomas del candidato son: {', '.join(f"{l['language']} ({l['level']})" for l in cfg.get('user_languages', [])) if cfg.get('user_languages') else 'No especificados'}. NO inventes niveles de idioma ni agregues idiomas que no esten en esta lista.

CANDIDATO:
{json.dumps(p, indent=2)}

OFERTA:
- Titulo: {title}
- Empresa: {company}
- Descripcion: {desc}
- Requisitos: {reqs}

INSTRUCCIONES PARA CADA SECCION:

1. SUMMARY (sobre mi): Reescribe completamente en PRIMERA PERSONA (yo tengo, yo desarrollo, mi experiencia) para que suene como si el candidato fuera la persona IDEAL para este puesto especifico. PROHIBIDO tercera persona (Jose es, Jose tiene). Menciona las habilidades y experiencia que pide la oferta. 2-3 oraciones.

2. TITLE: Usa el mismo titulo o terminologia de la oferta.

3. SKILLS: Reordena poniendo PRIMERO las que pide la oferta. Solo incluye skills relevantes para ESTE puesto.

4. EXPERIENCE: Esta es la parte MAS IMPORTANTE.
   - Para CADA experiencia laboral, reescribe los bullets para que DESTAQUEN habilidades relevantes a ESTA oferta.
   - Conecta lo que el candidato hizo con lo que la oferta necesita.
   - Usa numeros y metricas siempre que sea posible.
   - Cada bullet debe sonar como si el candidato hizo exactamente lo que esta oferta necesita.

5. PROJECTS: Selecciona solo los proyectos mas relevantes para esta oferta. Si no hay proyectos relevantes, omite esta seccion con un array vacio.

6. EDUCATION: Mantener tal cual.

JSON:
{{
    "summary": "resumen personalizado para ESTA oferta (2-3 oraciones)",
    "title": "titulo usando terminos de la oferta",
    "skills_highlighted": ["skill1", "skill2", "skill3", ...],
    "experience": [
        {{
            "company": "empresa",
            "role": "titulo del rol",
            "period": "periodo",
            "bullets": [
                "logro reescrito enfocado a esta oferta con numeros",
                "logro reescrito enfocado a esta oferta con numeros",
                "logro reescrito enfocado a esta oferta con numeros"
            ]
        }}
    ],
    "projects": [
        {{"name": "proyecto relevante", "description": "enfocado a la oferta", "tech": ["herramienta1", "herramienta2"]}}
    ],
    "education": [
        {{"institution": "institucion", "degree": "titulo", "period": "periodo"}}
    ],
    "languages": [
        {{"language": "idioma", "level": "nivel real del candidato"}}
    ]
}}
SOLO JSON valido."""

    return json.loads(call_gemini(cfg, prompt))


# ── AGENT 3: EMAIL WRITER (genera emails de aplicacion) ──
def agent_email(cfg, job, cv_data=None):
    """Agent specialized in writing personalized application emails."""
    p = cfg["profile"]
    portfolio_line = f"\n- Portfolio: {p['portfolio']}" if p.get('portfolio') else ""
    linkedin_line = f"\n- LinkedIn: {p['linkedin']}" if p.get('linkedin') else ""
    lang = job.get("language", "es")

    lang_names = {"es": "ESPAÑOL", "en": "INGLES", "pt": "PORTUGUES", "fr": "FRANCES", "de": "ALEMAN"}
    lang_name = lang_names.get(lang, "ESPAÑOL")

    # Build signature lines dynamically
    sig_parts = [p.get('name', '')]
    if p.get('portfolio'): sig_parts.append(p['portfolio'])
    if p.get('linkedin'): sig_parts.append(p['linkedin'])

    lang_rules = {
        "es": '1. ESPAÑOL NEUTRO LATINOAMERICANO. PROHIBIDO: "flipa", "mola", "tio", "chevere", "bacano", "pana"',
        "en": "1. ENGLISH. Write in professional, natural English. No overly formal or robotic language.",
        "pt": "1. PORTUGUES. Escreva em portugues profissional e natural.",
    }
    lang_rule = lang_rules.get(lang, f"1. Escribe en {lang_name}. Lenguaje profesional y natural.")

    prompt = f"""ROLE: Eres un agente especializado en escribir emails de aplicacion a ofertas de trabajo.
Tu objetivo: escribir un email que suene 100% humano, personal, y que haga que el reclutador quiera responder.
Esto funciona para CUALQUIER sector: tecnologia, marketing, ventas, diseno, salud, educacion, finanzas, etc.

IDIOMA: Escribe TODO el email en {lang_name}. La oferta esta en {lang_name}.

CANDIDATO:
- Nombre: {p.get('name', '')}{portfolio_line}{linkedin_line}
- Busca empleo como: {cfg.get('job_types_raw', '')}
{f"""
CV GENERADO PARA ESTA OFERTA (usa estos datos para que el email sea coherente con el CV adjunto):
- Titulo: {cv_data.get('title', '')}
- Resumen: {cv_data.get('summary', '')}
- Skills destacadas: {', '.join(cv_data.get('skills_highlighted', [])[:8])}
""" if cv_data else ''}
OFERTA:
- Puesto: {job.get('job_title', '')}
- Empresa: {job.get('company', '')}
- Descripcion: {job.get('description', '')}
- Contacto: {job.get('contact_name', 'equipo de seleccion')}

REGLAS ESTRICTAS:
{lang_rule}
2. TEXTO PLANO UNICAMENTE. PROHIBIDO: markdown, corchetes [], asteriscos **, formato [texto](url), HTML
3. Las URLs van tal cual, sin formato alrededor
4. MAXIMO 100 palabras en el cuerpo
5. Debe sonar como si {p.get('name', 'el candidato')} lo escribiera personalmente
6. PROHIBIDO frases de plantilla: "me emociona", "me apasiona profundamente", "me encantaria unirme", "I am excited", "I am passionate"
7. NO propongas agendar llamadas ni reuniones
8. Menciona 1-2 logros CONCRETOS con numeros que sean relevantes para ESTA oferta. PROHIBIDO inventar logros, cifras o habilidades que no esten en el perfil del candidato{' o en el CV generado' if cv_data else ''}.
9. El asunto debe ser corto y directo (max 8 palabras)
10. Firma simple en texto plano: {', '.join(sig_parts)}

JSON (sin markdown, sin bloques de codigo):
{{"subject": "asunto corto", "body": "cuerpo completo con saludo y despedida"}}"""

    return json.loads(call_gemini(cfg, prompt))


# ══════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════
def cmd_run(test_email=None, time_filter="24h", auto_apply=False):
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
    console.print(Panel(
        f"  [dim]Perfil[/dim]     {cfg['profile'].get('name','?')}\n"
        f"  [dim]Destino[/dim]    {mode_label}\n"
        f"  [dim]Periodo[/dim]    {time_labels.get(time_filter, time_filter)}\n"
        f"  [dim]Queries[/dim]    {len(cfg.get('search_queries',[]))}",
        border_style="cyan", title="[bold]Sesion[/bold]"
    ))

    kill_playwright_zombies()
    queries = cfg.get("search_queries", ["enviar CV backend developer"])

    # ── Phase 1: Scrape ──
    _phase_header("Fase 1 — Buscando en LinkedIn")
    all_posts = []
    seen = set()

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
            console.print("  [red]✗[/red] Sesion expirada. Ejecuta: [cyan]jobhunter login[/cyan]")
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
                time.sleep(3)

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

    posts_with_emails = [p for p in all_posts if p.get("emails_found")]
    posts_no_emails = len(all_posts) - len(posts_with_emails)
    console.print(f"  [bold]{len(all_posts)}[/bold] posts  ·  [bold]{len(posts_with_emails)}[/bold] con email  ·  [dim]{posts_no_emails} sin email (omitidos)[/dim]")

    if not posts_with_emails:
        console.print()
        console.print("  [yellow]![/yellow] No se encontraron posts con email. Intenta un periodo mas amplio.")
        console.print("    [dim]Ej: jobhunter run --time week[/dim]")
        return

    # ── Phase 2: Analyze (only posts with emails to save tokens) ──
    _phase_header("Fase 2 — Analizando con Gemini AI")
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

    console.print(
        f"  [bold]{len(offers)}[/bold] ofertas  ·  "
        f"[green]{len(offers_with_email)}[/green] con email  ·  "
        f"[dim]{batch_dupes} duplicadas  ·  {len(offers_no_email)} sin email"
        f"{f'  ·  {blacklisted} bloqueadas' if blacklisted else ''}[/dim]"
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
    _phase_header("Fase 3 — Generando CVs y enviando")
    sent = 0
    errors = 0
    results = []

    total = len(offers)
    for i, job in enumerate(offers, 1):
        title = (job.get("job_title") or "Posicion")[:80]
        company = (job.get("company") or "Empresa")[:40]
        rec_email = job.get("contact_email")

        console.print(f"  [bold cyan]{i}[/bold cyan][dim]/{total}[/dim]  [bold]{title}[/bold] [dim]→ {company}[/dim]")

        # Generate CV (with retry)
        cv_path = None
        for retry in range(3):
            with console.status(f"       [dim]Generando CV...{' (reintento)' if retry > 0 else ''}[/dim]"):
                try:
                    cv_data = agent_cv(cfg, job)
                    cv_fn = get_cv_filename(company, title)
                    cv_path = os.path.join(BASE_DIR, "output", "cvs", cv_fn)
                    os.makedirs(os.path.dirname(cv_path), exist_ok=True)
                    generate_cv_pdf(cv_data, cfg["profile"], cv_path, title, company, language=job.get("language", "es"), template=cfg.get("cv_template", "modern"))
                    console.print(f"       [green]✓[/green] CV generado")
                    break
                except Exception as e:
                    if retry == 2:
                        console.print(f"       [red]✗[/red] CV fallido: {e}")
                        errors += 1
                    else:
                        time.sleep(5)
        if not cv_path:
            continue
        time.sleep(1)

        # Generate email (with retry)
        edata = None
        for retry in range(3):
            with console.status(f"       [dim]Generando email...{' (reintento)' if retry > 0 else ''}[/dim]"):
                try:
                    edata = agent_email(cfg, job, cv_data=cv_data)
                    console.print(f"       [green]✓[/green] Email: {edata['subject'][:50]}")
                    break
                except Exception as e:
                    if retry == 2:
                        console.print(f"       [red]✗[/red] Email fallido: {e}")
                        errors += 1
                    else:
                        time.sleep(5)
        if not edata:
            continue
        time.sleep(1)

        # Send
        to = test_email or rec_email
        body = edata["body"]
        if test_email:
            body = f"--- RECLUTADOR: {job.get('contact_name','?')} | EMAIL: {rec_email or '?'} | {company} ---\n\n" + body

        try:
            send_email(cfg, to, edata["subject"], body, cv_path)
            sent += 1
            console.print(f"       [green]✓[/green] Enviado → {to}")
            kb["applications"].append({
                "date": datetime.now().isoformat(), "job_title": title,
                "company": company, "recruiter_email": rec_email,
                "sent_to": to, "mode": mode,
                "post_url": job.get("post_url"),
            })
        except Exception as e:
            console.print(f"       [red]✗[/red] Error envio: {e}")
            errors += 1

        results.append({
            "job_title": title, "company": company,
            "recruiter_email": rec_email, "sent_to": to, "cv_path": cv_path,
        })
        console.print()
        time.sleep(2)

    kb["runs"].append({"date": datetime.now().isoformat(), "mode": mode, "posts": len(all_posts), "offers": len(offers), "sent": sent})
    save_kb(kb)

    # Summary
    err_str = f"[red]{errors}[/red]" if errors else "[dim]0[/dim]"
    console.print(Panel(
        f"  [dim]Posts scraped[/dim]       {len(all_posts)}\n"
        f"  [dim]Analizados[/dim]          {len(posts_with_emails)}  [dim](con email)[/dim]\n"
        f"  [dim]Ofertas[/dim]             {len(offers)}\n"
        f"  [dim]Enviados[/dim]            [bold green]{sent}[/bold green]\n"
        f"  [dim]Errores[/dim]             {err_str}",
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
    cfg = load_config()
    kb = load_kb()

    if not cfg.get("gemini_api_key"):
        console.print("  [red]✗[/red] Falta configuracion. Ejecuta: [cyan]jobhunter setup[/cyan]")
        return

    console.print(get_banner())
    _phase_header("Optimizando queries de busqueda")

    profile = cfg.get("profile", {})
    current_queries = cfg.get("search_queries", [])
    job_types = cfg.get("job_types_raw", "")
    lang = cfg.get("search_languages", "3")
    work_mode = cfg.get("work_mode_label", "Cualquiera")
    location = cfg.get("user_location", "")

    lang_labels = {"1": "Espanol", "2": "Ingles", "3": "Espanol e Ingles"}
    lang_label = lang_labels.get(lang, "Espanol e Ingles")

    # Build context from knowledge base
    runs = kb.get("runs", [])
    apps = kb.get("applications", [])
    run_stats = ""
    if runs:
        total_posts = sum(r.get("posts", 0) for r in runs)
        total_offers = sum(r.get("offers", 0) for r in runs)
        total_sent = sum(r.get("sent", 0) for r in runs)
        run_stats = f"""
HISTORIAL DE EJECUCIONES ({len(runs)} ejecuciones):
- Posts scrapeados en total: {total_posts}
- Ofertas encontradas en total: {total_offers}
- Emails enviados en total: {total_sent}
- Tasa de conversion posts→ofertas: {(total_offers/total_posts*100):.1f}% (idealmente >15%)
- Tasa de conversion posts→enviados: {(total_sent/total_posts*100):.1f}%"""

    applied_titles = ""
    if apps:
        titles = list(set(a.get("job_title", "") for a in apps[-30:]))
        applied_titles = f"\nPUESTOS A LOS QUE YA APLICO (ultimos 30): {', '.join(titles[:15])}"

    user_context = ""
    if user_prompt:
        user_context = f"""
FEEDBACK DEL USUARIO (prioridad maxima, atender esto):
"{user_prompt}"
"""

    prompt = f"""ROLE: Eres un agente experto en busqueda de empleo en LinkedIn. Tu trabajo es optimizar las queries de busqueda para maximizar la cantidad de ofertas REALES con email de reclutador encontradas.

CONTEXTO DEL CANDIDATO:
- Nombre: {profile.get('name', '?')}
- Titulo: {profile.get('title', '?')}
- Busca empleo como: {job_types}
- Habilidades: {json.dumps(profile.get('skills', {})) if isinstance(profile.get('skills'), dict) else str(profile.get('skills', ''))[:500]}
- Experiencia reciente: {json.dumps(profile.get('experience', [])[:2]) if profile.get('experience') else 'N/A'}
- Idiomas de busqueda: {lang_label}
- Modalidad: {work_mode}
{f'- Ubicacion: {location}' if location else ''}

QUERIES ACTUALES ({len(current_queries)}):
{json.dumps(current_queries, indent=2)}
{run_stats}
{applied_titles}
{user_context}

INSTRUCCIONES:
1. Analiza las queries actuales y determina por que pueden estar dando pocos resultados
2. Genera queries OPTIMIZADAS que:
   - Usen terminos que los reclutadores REALMENTE usan en LinkedIn cuando publican ofertas
   - Incluyan variaciones naturales (abreviaciones, sinonimos, terminos de la industria)
   - Cubran tanto posts de reclutadores como de hiring managers
   - Sean especificas al perfil pero no tan nicho que no encuentren nada
   - Incluyan frases que impliquen que hay email de contacto ("enviar CV a", "send resume to", "apply via email")
   - Consideren la modalidad de trabajo ({work_mode})
   {'- SOLO en espanol' if lang == '1' else '- SOLO en ingles' if lang == '2' else '- En espanol Y en ingles'}
3. NO repitas las mismas queries con minimas variaciones
4. Apunta a 15-25 queries totales (suficientes para cubrir variaciones, no tantas que sea lento)
5. Cada query debe ser de 3-6 palabras (asi funciona mejor en LinkedIn search)

JSON (sin markdown, sin bloques de codigo):
{{"analysis": "analisis breve de por que las queries actuales pueden ser suboptimas", "queries": ["query1", "query2", ...], "changes_summary": "resumen de 2-3 lineas de que cambio y por que"}}"""

    with console.status("  [dim]Analizando y generando queries optimizadas...[/dim]"):
        try:
            result = json.loads(call_gemini(cfg, prompt))
        except Exception as e:
            console.print(f"  [red]✗[/red] Error al generar queries: {e}")
            return

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
        mode = app.get("mode", "RUN")
        mode_style = "[yellow]TEST[/yellow]" if mode == "TEST" else "[green]RUN[/green]"
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

    # Examples
    console.print("  [bold]Ejemplos[/bold]")
    console.print("  [dim]$ jobhunter --test mi@email.com[/dim]")
    console.print("  [dim]$ jobhunter run --time week[/dim]")
    console.print("  [dim]$ jobhunter run --auto[/dim]")
    console.print("  [dim]$ jobhunter run --time month --auto[/dim]")
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


def check_for_updates():
    """Quick non-blocking check for new commits on remote."""
    try:
        result = subprocess.run(
            ["git", "-C", BASE_DIR, "fetch", "--dry-run"],
            capture_output=True, text=True, timeout=5
        )
        if result.stderr.strip():
            console.print("  [yellow]![/yellow] Nueva version disponible → [cyan]jobhunter update[/cyan]\n")
    except Exception:
        pass


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
        cmd_run(test_email=sys.argv[2], time_filter=tf, auto_apply=auto)
    elif cmd in ("run",):
        cmd_run(time_filter=tf, auto_apply=auto)
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
