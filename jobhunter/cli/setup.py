# -*- coding: utf-8 -*-
"""Setup wizard interactivo. Helpers _ask/_ask_secret y state machine de pasos."""
import base64
import json
import os
import re
import smtplib

import requests
from rich.panel import Panel
from rich.prompt import Prompt

from jobhunter.ai.gemini import call_gemini, call_gemini_vision
from jobhunter.banner import get_banner
from jobhunter.config import load_config, save_config
from jobhunter.constants import BACK, GEMINI_MODELS, SESSION_DIR
from jobhunter.scraper import do_linkedin_login
from jobhunter.ui import console

CV_PICKER = "p"
QUIT = "q"
MAX_RECENT_CV_PATHS = 5


def _setup_screen(current, total, title, subtitle=None):
    """Limpia pantalla y muestra paso con barra de progreso."""
    if console.is_terminal:
        console.clear()
    console.print(get_banner())
    pct = int((current / total) * 100)
    filled = int(pct / 5)
    bar = "[cyan]" + "\u2588" * filled + "[/cyan]" + "[dim]" + "\u2591" * (20 - filled) + "[/dim]"
    console.print(f"  {bar}  [bold]{pct}%[/bold]")
    console.print()
    console.print(f"  [bold]{title}[/bold]")
    if subtitle:
        console.print(f"  [dim]{subtitle}[/dim]")
    if current > 0:
        console.print("  [dim]Atajos: (<) volver, (q) salir[/dim]")
    else:
        console.print("  [dim]Atajo: (q) salir[/dim]")
    console.print()


def _ask(label, **kwargs):
    """Prompt wrapper con atajos de navegacion y salida."""
    val = Prompt.ask(label, **kwargs)
    val = val.strip().strip('"').strip("'")
    if val.lower() == QUIT:
        raise KeyboardInterrupt
    if val == BACK:
        return None
    return val


def _mask_secret(value):
    """Retorna preview enmascarado: primeros 4 chars + ***."""
    if not value:
        return ""
    v = str(value)
    if len(v) <= 4:
        return "***"
    return v[:4] + "***"


def _ask_secret(label, current, password=False):
    """Pregunta por un secreto con preview enmascarado inline.

    Enter mantiene el valor actual. Devuelve None si se escribio '<'.
    """
    if current:
        shown_label = f"{label} [dim]({_mask_secret(current)})[/dim]"
        val = Prompt.ask(shown_label, password=password, default=current, show_default=False)
    else:
        val = Prompt.ask(label, password=password, default="")
    val = (val or "").strip().strip('"').strip("'")
    if val.lower() == QUIT:
        raise KeyboardInterrupt
    if val == BACK:
        return None
    return val


def _pick_pdf_file(initial_path=""):
    """Abre selector nativo de archivos PDF y retorna ruta o cadena vacia."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return ""

    initialdir = ""
    if initial_path:
        initialdir = initial_path if os.path.isdir(initial_path) else os.path.dirname(initial_path)
    if not initialdir:
        initialdir = os.path.expanduser("~")

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    try:
        selected = filedialog.askopenfilename(
            title="Selecciona tu CV en PDF",
            initialdir=initialdir,
            filetypes=[("Archivos PDF", "*.pdf"), ("Todos los archivos", "*.*")],
        )
    finally:
        root.destroy()
    return (selected or "").strip()


def _remember_cv_path(cfg, cv_path):
    """Guarda ruta de CV en historico reciente, sin duplicados."""
    if not cv_path:
        return
    normalized = os.path.normpath(cv_path)
    existing = [os.path.normpath(path) for path in cfg.get("cv_recent_paths", []) if path]
    deduped = [path for path in existing if path != normalized]
    cfg["cv_recent_paths"] = [normalized] + deduped[: MAX_RECENT_CV_PATHS - 1]


def cmd_setup():
    cfg = load_config()
    profile = cfg.get("profile", {})
    from jobhunter.cv.templates import TEMPLATES, DEFAULT_TEMPLATE

    lang_options = {"1": "Espanol", "2": "Ingles", "3": "Espanol e Ingles"}
    mode_options = {"1": "Remoto", "2": "Hibrido", "3": "Presencial", "4": "Cualquiera"}

    TOTAL = 10

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
                    s = json.dumps(profile.get("skills", {}))
                    e = json.dumps(profile.get("experience", [])[:3])
                    result = call_gemini(cfg, f"Basado en skills: {s} y experiencia: {e}, sugiere 6 tipos de empleo. JSON array: [\"tipo1\",\"tipo2\"]")
                    for i, sg in enumerate(json.loads(result), 1):
                        console.print(f"  [cyan]{i}.[/cyan] {sg}")
                    console.print()
                except Exception:
                    pass
        console.print("  [dim]Separados por coma[/dim]")
        val = _ask("  Tipos de empleo", default=cfg.get("job_types_raw", ""))
        if val is None: return "back"
        if not val:
            val = "software developer"
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
        if choice not in mode_options:
            choice = "4"
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
            console.print(f"  [cyan]{i}.[/cyan] {t['name']} \u2014 [dim]{t['description']}[/dim]{marker}")
        choice = _ask("  Selecciona", default=str(tmpl_keys.index(current_tmpl) + 1))
        if choice is None: return "back"
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(tmpl_keys):
                cfg["cv_template"] = tmpl_keys[idx]
        except ValueError:
            pass

    def step_gemini():
        _setup_screen(6, TOTAL, "Gemini AI", "Obtiene la clave gratis en https://aistudio.google.com/apikey")
        while True:
            key = _ask_secret("  Clave API", cfg.get("gemini_api_key", ""))
            if key is None: return "back"
            if not key:
                console.print("  [red]Obligatoria.[/red]")
                continue
            key = key.replace(" ", "")
            with console.status("  [dim]Verificando...[/dim]"):
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
                    requests.post(url, json={"contents": [{"parts": [{"text": "test"}]}]}, timeout=10).raise_for_status()
                    cfg["gemini_api_key"] = key
                    console.print("  [green]>[/green] Clave valida")
                    break
                except Exception:
                    console.print("  [red]![/red] Clave invalida. Intenta de nuevo.")
        console.print()
        current = cfg.get("gemini_model", "gemini-2.5-flash")
        console.print(f"  [bold]Modelo[/bold] [dim](Enter para mantener {current})[/dim]")
        for i, m in enumerate(GEMINI_MODELS, 1):
            marker = " [green]<< actual[/green]" if m == current else ""
            console.print(f"  [cyan]{i}.[/cyan] {m}{marker}")
        default_idx = str(GEMINI_MODELS.index(current) + 1 if current in GEMINI_MODELS else 1)
        choice = _ask("  Selecciona", default=default_idx)
        if choice is None: return "back"
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(GEMINI_MODELS):
                cfg["gemini_model"] = GEMINI_MODELS[idx]
        except ValueError:
            pass

    def step_gmail():
        _setup_screen(7, TOTAL, "Gmail + Contrasena de aplicacion", "Cuenta Google > Seguridad > Contrasenas de aplicacion")
        while True:
            email = _ask("  Gmail", default=cfg.get("smtp_email", ""))
            if email is None: return "back"
            if not re.match(r'^[^@]+@gmail\.com$', email):
                console.print("  [red]![/red] Debe ser @gmail.com")
                continue
            pwd = _ask_secret("  Contrasena de app", cfg.get("smtp_password", ""), password=True)
            if pwd is None: return "back"
            pwd = pwd.replace(" ", "")
            if not pwd or len(pwd) < 10:
                console.print("  [red]![/red] Minimo 16 caracteres")
                continue
            with console.status("  [dim]Verificando SMTP...[/dim]"):
                try:
                    with smtplib.SMTP("smtp.gmail.com", 587) as s:
                        s.starttls()
                        s.login(email, pwd)
                    cfg["smtp_email"] = email
                    cfg["smtp_password"] = pwd
                    console.print("  [green]>[/green] SMTP verificado")
                    return
                except Exception as e:
                    console.print(f"  [red]![/red] {e}")

    def step_cv():
        _setup_screen(8, TOTAL, "Tu CV actual", "Ruta al archivo PDF \u2014 OBLIGATORIO")
        console.print("  [dim]El CV se lee con IA para extraer tu experiencia real. Sin CV no se puede continuar.[/dim]")
        recent_paths = cfg.get("cv_recent_paths", [])
        if recent_paths:
            console.print("  [dim]Rutas recientes:[/dim]")
            for index, path in enumerate(recent_paths, 1):
                console.print(f"  [cyan]{index}.[/cyan] {path}")
            console.print()
        while True:
            cv = _ask(
                "  Ruta del CV (.pdf) [dim](Enter=manual, p=selector PDF)[/dim]",
                default=cfg.get("cv_path", ""),
            )
            if cv is None: return "back"
            if cv.lower() == CV_PICKER:
                picked = _pick_pdf_file(cfg.get("cv_path", ""))
                if not picked:
                    console.print("  [yellow]![/yellow] No se selecciono ningun archivo.")
                    continue
                cv = picked
            if not cv:
                console.print("  [red]![/red] El CV es obligatorio. La IA lo usa para adaptar tu experiencia REAL a cada oferta.")
                continue
            if not os.path.exists(cv):
                console.print(f"  [red]![/red] No encontrado: {cv}")
                continue
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
                    user_portfolio = profile.get("portfolio", "")
                    user_linkedin = profile.get("linkedin", "")
                    profile = parsed
                    if user_portfolio:
                        profile["portfolio"] = user_portfolio
                    if user_linkedin:
                        profile["linkedin"] = user_linkedin
                    cfg["cv_path"] = cv
                    _remember_cv_path(cfg, cv)
                    console.print(f"  [green]>[/green] CV leido \u2014 {profile.get('name', '?')}")
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
        do_linkedin_login()

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

    cfg["profile"] = profile

    from jobhunter.agents.query_generator import generate_queries
    with console.status("  [dim]Generando queries de busqueda con IA...[/dim]"):
        queries, from_ai = generate_queries(cfg)

    if not from_ai:
        console.print(
            "  [yellow]![/yellow] No se pudo generar queries con IA (API de Gemini fallo o sin cuota). "
            "Se uso un fallback basico. Ejecuta [cyan]jobhunter optimize[/cyan] mas tarde para mejorarlas."
        )

    cfg["search_queries"] = queries
    save_config(cfg)

    if console.is_terminal:
        console.clear()
    console.print(get_banner())
    name = profile.get("name", "?")
    correo = cfg.get("smtp_email", "?")
    cv_path = cfg.get("cv_path", "-")
    model = cfg.get("gemini_model", "?")
    tmpl = cfg.get("cv_template", "modern")
    console.print(Panel(
        f"[bold green]> Configuracion completa[/bold green]\n\n"
        f"  [dim]Nombre[/dim]      {name}\n"
        f"  [dim]Correo[/dim]      {correo}\n"
        f"  [dim]CV[/dim]          {cv_path}\n"
        f"  [dim]Modelo[/dim]      {model}\n"
        f"  [dim]Plantilla[/dim]   {tmpl}\n"
        f"  [dim]Busquedas[/dim]   {len(queries)} generadas\n\n"
        f"  Siguiente paso: [cyan]jobhunter run[/cyan]",
        border_style="green", title="[bold]Resumen[/bold]",
    ))
