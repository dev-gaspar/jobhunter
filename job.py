#!/usr/bin/env python3
"""
JobHunter AI v1.0
Automated LinkedIn Job Search + AI CV Generation + Auto Apply

Usage:
    jobhunter                       First run = setup wizard, then search
    jobhunter --test <email>        Test mode (sends to your email)
    jobhunter run                   Production mode (sends to recruiters)
    jobhunter login                 Re-login to LinkedIn
    jobhunter status                View config and stats
    jobhunter setup                 Re-run setup wizard
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
        print(f"Instalando: {', '.join(needed)}...")
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
sys.path.insert(0, BASE_DIR)
from src.cv_builder import generate_cv_pdf, get_cv_filename

console = Console()
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SESSION_DIR = os.path.join(BASE_DIR, ".session")
KB_PATH = os.path.join(BASE_DIR, "knowledge.json")  # Knowledge base

BANNER = """
[bold cyan]
       ██╗ ██████╗ ██████╗ ██╗  ██╗██╗   ██╗███╗   ██╗████████╗███████╗██████╗
       ██║██╔═══██╗██╔══██╗██║  ██║██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗
       ██║██║   ██║██████╔╝███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝
  ██   ██║██║   ██║██╔══██╗██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗
  ╚█████╔╝╚██████╔╝██████╔╝██║  ██║╚██████╔╝██║ ╚████║   ██║   ███████╗██║  ██║
   ╚════╝  ╚═════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
[/bold cyan]
[dim]  AI-Powered Job Search & Auto Apply  |  Playwright + Gemini + Gmail[/dim]
"""


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

def was_already_applied(kb, company, job_title, cooldown_days=30):
    """Check if we already sent an application for the same job title + company.
    Returns True if a matching application exists within the cooldown period.
    Different job titles at the same company are allowed."""
    cutoff = datetime.now() - timedelta(days=cooldown_days)
    norm = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())
    nc, nj = norm(company), norm(job_title)
    for app in kb.get("applications", []):
        ac, aj = norm(app.get("company", "")), norm(app.get("job_title", ""))
        if nc == ac and nj == aj:
            try:
                app_date = datetime.fromisoformat(app["date"])
                if app_date > cutoff:
                    return True
            except:
                return True  # If date is unparseable, assume recent
    return False


# ══════════════════════════════════════════════
# GEMINI
# ══════════════════════════════════════════════
def gemini_url(cfg):
    return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={cfg['gemini_api_key']}"

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

def extract_emails(text):
    return list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)))

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
def cmd_setup():
    console.print(BANNER)
    console.print(Rule("[bold]Setup Wizard[/bold]"))
    console.print()

    cfg = load_config()

    # 1. Gemini
    console.print("[bold cyan]1.[/bold cyan] [bold]API Key de Gemini[/bold]")
    console.print("   [dim]Obtienla gratis en https://aistudio.google.com/apikey[/dim]")
    while True:
        key = Prompt.ask("   API Key", default=cfg.get("gemini_api_key", ""))
        if not key:
            console.print("   [red]La API key es obligatoria.[/red]")
            continue
        with console.status("   Verificando..."):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
                requests.post(url, json={"contents":[{"parts":[{"text":"test"}]}]}, timeout=10).raise_for_status()
                console.print("   [green]Valida[/green]")
                cfg["gemini_api_key"] = key
                break
            except:
                console.print("   [red]API key invalida. Intentalo de nuevo.[/red]")

    # 2. Gmail
    console.print(f"\n[bold cyan]2.[/bold cyan] [bold]Correo Gmail + App Password[/bold]")
    console.print("   [dim]Necesitas un App Password: Google Account > Security > App Passwords[/dim]")
    while True:
        email = Prompt.ask("   Gmail", default=cfg.get("smtp_email", ""))
        if not re.match(r'^[^@]+@gmail\.com$', email):
            console.print("   [red]Debe ser una cuenta @gmail.com[/red]")
            continue
        pwd = Prompt.ask("   App Password", default=cfg.get("smtp_password",""), password=True)
        if not pwd or len(pwd) < 10:
            console.print("   [red]El App Password debe tener al menos 16 caracteres (sin espacios)[/red]")
            continue
        with console.status("   Verificando SMTP..."):
            try:
                with smtplib.SMTP("smtp.gmail.com", 587) as s:
                    s.starttls(); s.login(email, pwd)
                console.print("   [green]SMTP funciona[/green]")
                cfg["smtp_email"] = email
                cfg["smtp_password"] = pwd
                break
            except Exception as e:
                console.print(f"   [red]Error: {e}[/red]")
                console.print("   [yellow]Verifica el App Password e intenta de nuevo.[/yellow]")

    # 3. CV
    console.print(f"\n[bold cyan]3.[/bold cyan] [bold]Tu CV actual[/bold]")
    console.print("   [dim]Ruta al archivo PDF de tu CV[/dim]")
    profile = cfg.get("profile", {})
    while True:
        cv = Prompt.ask("   Ruta del CV (.pdf)", default=cfg.get("cv_path", ""))
        if not cv:
            console.print("   [yellow]Sin CV. Puedes agregarlo despues con 'jobhunter setup'[/yellow]")
            break
        if not os.path.exists(cv):
            console.print(f"   [red]Archivo no encontrado: {cv}[/red]")
            continue
        cfg["cv_path"] = cv
        with console.status("   Leyendo CV con Gemini AI..."):
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
                console.print(f"   [green]CV leido! Nombre: {profile.get('name', '?')}[/green]")
                console.print(f"   [dim]Skills: {', '.join(profile.get('skills',{}).get('backend',[])[:5])}...[/dim]")
                break
            except Exception as e:
                console.print(f"   [red]Error leyendo CV: {e}[/red]")
                console.print("   [yellow]Puedes continuar sin CV automatico.[/yellow]")
                break

    # 4. Portfolio
    console.print(f"\n[bold cyan]4.[/bold cyan] [bold]Portfolio / Web personal[/bold] [dim](opcional)[/dim]")
    portfolio = Prompt.ask("   URL", default=profile.get("portfolio", ""))
    profile["portfolio"] = portfolio

    # 5. LinkedIn
    console.print(f"\n[bold cyan]5.[/bold cyan] [bold]Perfil de LinkedIn[/bold]")
    linkedin = Prompt.ask("   URL", default=profile.get("linkedin", ""))
    if linkedin and "linkedin.com" not in linkedin:
        console.print("   [yellow]Eso no parece un URL de LinkedIn[/yellow]")
    profile["linkedin"] = linkedin

    cfg["profile"] = profile

    # 6. Job preferences
    console.print(f"\n[bold cyan]6.[/bold cyan] [bold]Que tipo de empleo buscas?[/bold]")

    if profile.get("skills"):
        with console.status("   Generando sugerencias de tu CV..."):
            try:
                s = json.dumps(profile.get("skills",{}))
                e = json.dumps(profile.get("experience",[])[:3])
                result = call_gemini(cfg, f"Basado en skills: {s} y experiencia: {e}, sugiere 6 tipos de empleo. JSON array: [\"tipo1\",\"tipo2\"]")
                suggestions = json.loads(result)
                console.print("   [dim]Sugerencias basadas en tu CV:[/dim]")
                for i, sg in enumerate(suggestions, 1):
                    console.print(f"   [cyan]{i}.[/cyan] {sg}")
                console.print()
            except:
                pass

    console.print("   [dim]Escribe los tipos de empleo separados por coma[/dim]")
    job_types = Prompt.ask("   Tipos de empleo", default=cfg.get("job_types_raw", ""))
    if not job_types:
        console.print("   [red]Debes especificar al menos un tipo de empleo.[/red]")
        job_types = Prompt.ask("   Tipos de empleo", default="backend developer")
    cfg["job_types_raw"] = job_types

    queries = []
    for jt in [j.strip() for j in job_types.split(",") if j.strip()]:
        queries.extend([
            f"enviar CV {jt}", f"busco {jt} remoto", f"hiring {jt} remote",
            f"contratando {jt}", f"vacante {jt} remoto",
        ])
    cfg["search_queries"] = queries
    save_config(cfg)

    console.print()
    console.print(Panel(
        f"[bold green]Setup completo![/bold green]\n\n"
        f"  Nombre:     {profile.get('name', '?')}\n"
        f"  Gmail:      {cfg['smtp_email']}\n"
        f"  CV:         {cfg.get('cv_path', 'no configurado')}\n"
        f"  Portfolio:  {profile.get('portfolio', '-')}\n"
        f"  LinkedIn:   {profile.get('linkedin', '-')}\n"
        f"  Busquedas:  {len(queries)} queries generadas\n\n"
        f"[bold]Siguiente paso:[/bold] [cyan]jobhunter login[/cyan]",
        border_style="green", title="JobHunter AI"
    ))


# ══════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════
def cmd_login():
    console.print(BANNER)
    kill_playwright_zombies()
    os.makedirs(SESSION_DIR, exist_ok=True)
    chrome = find_chrome()

    console.print(Panel(
        "[bold]Iniciar sesion en LinkedIn[/bold]\n\n"
        "Se abrira Chrome. Inicia sesion con [bold]email y password[/bold]\n"
        "[red]NO uses el boton de Google[/red] (lo bloquea en navegadores automatizados)\n\n"
        "Cuando estes dentro de LinkedIn, [bold]cierra el navegador[/bold].",
        border_style="cyan"
    ))

    input("  Presiona Enter para abrir el navegador...")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR, headless=False,
            viewport={"width":1300,"height":850}, executable_path=chrome,
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://www.linkedin.com/login")
        console.print("\n  [yellow]Esperando que inicies sesion y cierres el navegador...[/yellow]")
        try:
            while True:
                time.sleep(1)
                try: _ = page.title()
                except: break
        except: pass

    console.print("  [green]Sesion de LinkedIn guardada![/green]")
    console.print(f"\n  Ahora puedes buscar empleo:")
    console.print(f"  [cyan]jobhunter --test tu@email.com[/cyan]  (modo prueba)")
    console.print(f"  [cyan]jobhunter run[/cyan]                   (enviar a reclutadores)")


# ══════════════════════════════════════════════
# STATUS
# ══════════════════════════════════════════════
def cmd_status():
    console.print(BANNER)
    cfg = load_config()
    kb = load_kb()

    table = Table(border_style="cyan", title="Estado de JobHunter AI")
    table.add_column("", style="bold", width=20)
    table.add_column("")

    table.add_row("Gemini API", "[green]OK[/green]" if cfg.get("gemini_api_key") else "[red]No configurada[/red]")
    table.add_row("Gmail", cfg.get("smtp_email", "[red]No configurado[/red]"))
    table.add_row("SMTP", "[green]OK[/green]" if cfg.get("smtp_password") else "[red]No configurado[/red]")
    table.add_row("CV", cfg.get("cv_path") or "[yellow]No configurado[/yellow]")
    table.add_row("Nombre", cfg.get("profile",{}).get("name", "[yellow]?[/yellow]"))
    table.add_row("Busqueda", cfg.get("job_types_raw", "[yellow]No configurado[/yellow]"))
    table.add_row("Queries", str(len(cfg.get("search_queries",[]))))
    table.add_row("LinkedIn", "[green]Sesion guardada[/green]" if os.path.exists(SESSION_DIR) else "[red]No[/red]")
    table.add_row("Ejecuciones", str(len(kb.get("runs",[]))))
    table.add_row("Aplicaciones", str(len(kb.get("applications",[]))))

    console.print(table)


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

    return page.evaluate(r"""() => {
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

    prompt = f"""ROLE: Eres un agente especializado en filtrar ofertas de trabajo de LinkedIn.
Tu unico trabajo es analizar publicaciones y determinar si contienen ofertas REALES y RELEVANTES para este candidato.

PERFIL DEL CANDIDATO:
- Busca empleo como: {job_types}
- Resumen: {profile_summary[:300]}
- Habilidades: {json.dumps(profile_skills) if isinstance(profile_skills, dict) else str(profile_skills)[:500]}

PUBLICACION:
{text[:4000]}

EMAILS ENCONTRADOS EN EL TEXTO: {', '.join(emails) if emails else 'ninguno'}

REGLAS DE FILTRADO:
- Solo ofertas de TRABAJO reales (no cursos, certificaciones, logros personales, contenido general, publicidad)
- Relevante si el puesto tiene relacion con lo que busca el candidato: {job_types}
- Extraer SIEMPRE el email si existe en el texto
- Extraer empresa, titulo, descripcion COMPLETA con todos los detalles
- Extraer requisitos especificos (habilidades, herramientas, anos de experiencia, idiomas, etc.)
- Si la publicacion tiene multiples ofertas, toma la mas relevante para el candidato

JSON:
{{"is_job": true/false, "job_title": "titulo exacto del puesto", "company": "empresa", "description": "descripcion DETALLADA incluyendo responsabilidades y lo que se espera del candidato", "requirements": "TODOS los requisitos mencionados", "contact_email": "email@empresa.com o null", "contact_name": "nombre de quien publica", "location": "ubicacion", "salary": "salario o null", "is_relevant": true/false, "relevance_reason": "razon concreta"}}

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

    prompt = f"""ROLE: Eres un agente experto en redaccion de CVs profesionales.
Tu trabajo es tomar el perfil del candidato y REESCRIBIRLO para que encaje perfectamente con una oferta especifica.
Esto funciona para CUALQUIER tipo de trabajo: tecnologia, marketing, ventas, diseno, administracion, salud, educacion, etc.

REGLAS CRITICAS:
- ESPAÑOL NEUTRO LATINOAMERICANO (sin jerga regional)
- Usa la MISMA TERMINOLOGIA de la oferta. Si la oferta dice "Community Manager", el CV dice "Community Manager". Si dice "Backend Developer", dice "Backend Developer".
- NO traduzcas terminos que en la industria se usan en su idioma original
- Adapta TODO el CV al sector y lenguaje de la oferta

CANDIDATO:
{json.dumps(p, indent=2)}

OFERTA:
- Titulo: {title}
- Empresa: {company}
- Descripcion: {desc}
- Requisitos: {reqs}

INSTRUCCIONES PARA CADA SECCION:

1. SUMMARY (sobre mi): Reescribe completamente para que suene como si el candidato fuera la persona IDEAL para este puesto especifico. Menciona las habilidades y experiencia que pide la oferta. 2-3 oraciones.

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
    ]
}}
SOLO JSON valido."""

    return json.loads(call_gemini(cfg, prompt))


# ── AGENT 3: EMAIL WRITER (genera emails de aplicacion) ──
def agent_email(cfg, job):
    """Agent specialized in writing personalized application emails."""
    p = cfg["profile"]
    portfolio_line = f"\n- Portfolio: {p['portfolio']}" if p.get('portfolio') else ""
    linkedin_line = f"\n- LinkedIn: {p['linkedin']}" if p.get('linkedin') else ""

    # Build signature lines dynamically
    sig_parts = [p.get('name', '')]
    if p.get('portfolio'): sig_parts.append(p['portfolio'])
    if p.get('linkedin'): sig_parts.append(p['linkedin'])

    prompt = f"""ROLE: Eres un agente especializado en escribir emails de aplicacion a ofertas de trabajo.
Tu objetivo: escribir un email que suene 100% humano, personal, y que haga que el reclutador quiera responder.
Esto funciona para CUALQUIER sector: tecnologia, marketing, ventas, diseno, salud, educacion, finanzas, etc.

CANDIDATO:
- Nombre: {p.get('name', '')}{portfolio_line}{linkedin_line}
- Busca empleo como: {cfg.get('job_types_raw', '')}

OFERTA:
- Puesto: {job.get('job_title', '')}
- Empresa: {job.get('company', '')}
- Descripcion: {job.get('description', '')}
- Contacto: {job.get('contact_name', 'equipo de seleccion')}

REGLAS ESTRICTAS:
1. ESPAÑOL NEUTRO LATINOAMERICANO. PROHIBIDO: "flipa", "mola", "tio", "chevere", "bacano", "pana"
2. TEXTO PLANO UNICAMENTE. PROHIBIDO: markdown, corchetes [], asteriscos **, formato [texto](url), HTML
3. Las URLs van tal cual, sin formato alrededor
4. MAXIMO 100 palabras en el cuerpo
5. Debe sonar como si {p.get('name', 'el candidato')} lo escribiera personalmente
6. PROHIBIDO frases de plantilla: "me emociona", "me apasiona profundamente", "me encantaria unirme"
7. NO propongas agendar llamadas ni reuniones. Cierra con "quedo atento" o "me encantaria conversar sobre la posicion"
8. Menciona 1-2 logros CONCRETOS con numeros que sean relevantes para ESTA oferta
9. El asunto debe ser corto y directo (max 8 palabras)
10. Firma simple en texto plano: {', '.join(sig_parts)}

JSON (sin markdown, sin bloques de codigo):
{{"subject": "asunto corto", "body": "cuerpo completo con saludo y despedida"}}"""

    return json.loads(call_gemini(cfg, prompt))


# ══════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════
def cmd_run(test_email=None, time_filter="24h"):
    cfg = load_config()
    kb = load_kb()

    if not is_configured():
        console.print("[red]Falta configuracion. Ejecuta:[/red] [cyan]jobhunter setup[/cyan]")
        return
    if not os.path.exists(SESSION_DIR):
        console.print("[red]No hay sesion LinkedIn. Ejecuta:[/red] [cyan]jobhunter login[/cyan]")
        return

    console.print(BANNER)
    mode = "TEST" if test_email else "PRODUCCION"
    mode_color = "cyan" if test_email else "green"

    time_labels = {"24h": "Ultimas 24 horas", "week": "Esta semana", "month": "Este mes"}
    console.print(Panel(
        f"  Modo:    [bold {mode_color}]{mode}[/bold {mode_color}]\n"
        f"  Nombre:  {cfg['profile'].get('name','?')}\n"
        f"  Destino: {test_email or 'Reclutadores reales'}\n"
        f"  Tiempo:  {time_labels.get(time_filter, time_filter)}\n"
        f"  Queries: {len(cfg.get('search_queries',[]))}",
        border_style=mode_color, title="JobHunter AI"
    ))

    if not test_email:
        if not Confirm.ask("\n  [yellow]PRODUCCION: Se enviaran emails a reclutadores. Continuar?[/yellow]"):
            return

    kill_playwright_zombies()
    queries = cfg.get("search_queries", ["enviar CV backend developer"])

    # ── Phase 1: Scrape ──
    console.print(Rule("[bold]Fase 1: Buscando en LinkedIn[/bold]"))
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
            console.print("  [red]Sesion expirada. Ejecuta:[/red] [cyan]jobhunter login[/cyan]")
            browser.close(); return

        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
            BarColumn(), TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(), console=console
        ) as prog:
            task = prog.add_task("Buscando publicaciones...", total=len(queries))
            for query in queries:
                posts = scrape_posts(page, query, time_filter=time_filter)
                for pi in posts:
                    key = pi["text"][:150]
                    if key not in seen:
                        seen.add(key)
                        all_posts.append(pi)
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

    console.print(f"  [cyan]Posts unicos: {len(all_posts)} | Emails en texto: {sum(len(p.get('emails_found',[])) for p in all_posts)}[/cyan]")

    if not all_posts:
        console.print("  [yellow]No se encontraron posts. Intenta con otros terminos de busqueda.[/yellow]")
        return

    # ── Phase 2: Analyze ──
    console.print(Rule("[bold]Fase 2: Analizando con Gemini AI[/bold]"))
    offers = []

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), TextColumn("{task.completed}/{task.total}"),
                  TimeElapsedColumn(), console=console) as prog:
        task = prog.add_task("Analizando posts...", total=len(all_posts))
        for post in all_posts:
            if len(post.get("text","")) < 50:
                prog.advance(task); continue
            ss = post.get("screenshots",[None])[0] if post.get("screenshots") else None
            a = agent_filter(cfg, post["text"], ss)
            if a.get("is_job") and a.get("is_relevant", True):
                a["job_title"] = a.get("job_title") or "Software Developer"
                a["company"] = a.get("company") or "Empresa"
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

    console.print(f"  [cyan]Ofertas totales: {len(offers)} | Con email valido: {len(offers_with_email)} | Sin email: {len(offers_no_email)}[/cyan]\n")

    if offers_with_email:
        table = Table(border_style="cyan", title="Ofertas con email de reclutador")
        table.add_column("#", width=3)
        table.add_column("Puesto", max_width=35)
        table.add_column("Empresa", max_width=20)
        table.add_column("Email", max_width=30)
        for i, o in enumerate(offers_with_email, 1):
            table.add_row(str(i), o["job_title"][:35], o["company"][:20], o["contact_email"])
        console.print(table)

    if not offers_with_email:
        console.print("  [yellow]No se encontraron ofertas con email de reclutador.[/yellow]")
        return

    # Filter duplicates: skip if same job_title + company was already applied within 30 days
    before_dedup = len(offers_with_email)
    offers_with_email = [
        o for o in offers_with_email
        if not was_already_applied(kb, o.get("company", ""), o.get("job_title", ""))
    ]
    skipped = before_dedup - len(offers_with_email)
    if skipped:
        console.print(f"  [yellow]Omitidas {skipped} ofertas ya enviadas anteriormente (mismo cargo + empresa)[/yellow]")

    if not offers_with_email:
        console.print("  [yellow]Todas las ofertas ya fueron enviadas anteriormente.[/yellow]")
        return

    # Use only offers with valid email for Phase 3
    offers = offers_with_email

    # ── Phase 3: Generate & Send ──
    console.print(Rule("[bold]Fase 3: Generando CVs y enviando[/bold]"))
    sent = 0
    errors = 0
    results = []

    total = len(offers)
    for i, job in enumerate(offers, 1):
        title = (job.get("job_title") or "Posicion")[:80]
        company = (job.get("company") or "Empresa")[:40]
        rec_email = job.get("contact_email")

        console.print(f"\n  [bold][{i}/{total}][/bold] {title} [dim]en {company}[/dim]")

        # Generate CV (with retry)
        cv_path = None
        for retry in range(3):
            with console.status(f"    Generando CV...{' (reintento)' if retry > 0 else ''}"):
                try:
                    cv_data = agent_cv(cfg, job)
                    cv_fn = get_cv_filename(company, title)
                    cv_path = os.path.join(BASE_DIR, "output", "cvs", cv_fn)
                    os.makedirs(os.path.dirname(cv_path), exist_ok=True)
                    generate_cv_pdf(cv_data, cfg["profile"], cv_path, title, company)
                    console.print(f"    [green]CV generado[/green]")
                    break
                except Exception as e:
                    if retry == 2:
                        console.print(f"    [red]Error CV (3 intentos): {e}[/red]")
                        errors += 1
                    else:
                        time.sleep(5)
        if not cv_path:
            continue
        time.sleep(1)

        # Generate email (with retry)
        edata = None
        for retry in range(3):
            with console.status(f"    Generando email...{' (reintento)' if retry > 0 else ''}"):
                try:
                    edata = agent_email(cfg, job)
                    console.print(f"    [green]Email: {edata['subject'][:50]}[/green]")
                    break
                except Exception as e:
                    if retry == 2:
                        console.print(f"    [red]Error email (3 intentos): {e}[/red]")
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
            console.print(f"    [green]Enviado a {to}[/green]")
            kb["applications"].append({
                "date": datetime.now().isoformat(), "job_title": title,
                "company": company, "recruiter_email": rec_email,
                "sent_to": to, "mode": mode,
            })
        except Exception as e:
            console.print(f"    [red]Error envio: {e}[/red]")
            errors += 1

        results.append({
            "job_title": title, "company": company,
            "recruiter_email": rec_email, "sent_to": to, "cv_path": cv_path,
        })
        time.sleep(2)

    kb["runs"].append({"date": datetime.now().isoformat(), "mode": mode, "posts": len(all_posts), "offers": len(offers), "sent": sent})
    save_kb(kb)

    # Summary
    console.print()
    console.print(Panel(
        f"  Posts analizados:    {len(all_posts)}\n"
        f"  Ofertas con email:   {len(offers)}\n"
        f"  Emails enviados:     [bold green]{sent}[/bold green]\n"
        f"  Errores:             {errors}\n"
        f"  Modo:                {mode}",
        border_style="green", title="Resumen"
    ))

    log = os.path.join(BASE_DIR, "output", "logs", f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════
def cmd_help():
    console.print(BANNER)
    console.print(Panel(
        "[bold]Comandos disponibles:[/bold]\n\n"
        "  [cyan]jobhunter setup[/cyan]\n"
        "    Configuracion inicial: API key, Gmail, CV, preferencias.\n"
        "    Ejecuta esto la primera vez o para cambiar tu configuracion.\n\n"
        "  [cyan]jobhunter login[/cyan]\n"
        "    Abre Chrome para iniciar sesion en LinkedIn.\n"
        "    La sesion se guarda y no necesitas volver a hacerlo.\n\n"
        "  [cyan]jobhunter --test email@test.com[/cyan]\n"
        "    Modo prueba. Busca ofertas y envia todo a TU correo.\n"
        "    Incluye info del reclutador en cada email para referencia.\n\n"
        "  [cyan]jobhunter run[/cyan]\n"
        "    Modo produccion. Envia emails directamente a reclutadores.\n"
        "    Solo procesa ofertas que tengan email de contacto.\n\n"
        "  [cyan]jobhunter status[/cyan]\n"
        "    Muestra tu configuracion actual y estadisticas.\n\n"
        "  [cyan]jobhunter help[/cyan]\n"
        "    Muestra esta ayuda.\n\n"
        "[bold]Filtro de tiempo:[/bold]\n\n"
        "  Agrega [cyan]--time[/cyan] a cualquier comando de busqueda:\n\n"
        "  [cyan]--time 24h[/cyan]     Ultimas 24 horas [dim](por defecto)[/dim]\n"
        "  [cyan]--time week[/cyan]    Esta semana\n"
        "  [cyan]--time month[/cyan]   Este mes\n\n"
        "  Ejemplos:\n"
        "  [dim]jobhunter --test mi@email.com --time week[/dim]\n"
        "  [dim]jobhunter run --time month[/dim]\n",
        border_style="cyan", title="JobHunter AI - Ayuda"
    ))


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
                console.print(f"  [red]Filtro de tiempo invalido: {val}[/red]")
                console.print("  [dim]Opciones: 24h, week, month[/dim]")
                sys.exit(1)
    return "24h"


def main():
    if len(sys.argv) < 2:
        if not is_configured():
            cmd_setup()
        else:
            cmd_help()
        return

    cmd = sys.argv[1]
    tf = parse_time_filter(sys.argv)

    if cmd in ("setup",):
        cmd_setup()
    elif cmd in ("login",):
        cmd_login()
    elif cmd in ("status",):
        cmd_status()
    elif cmd in ("help", "--help", "-h"):
        cmd_help()
    elif cmd == "--test" and len(sys.argv) > 2:
        cmd_run(test_email=sys.argv[2], time_filter=tf)
    elif cmd in ("run",):
        cmd_run(time_filter=tf)
    else:
        console.print(BANNER)
        console.print(f"  [red]Comando desconocido: {cmd}[/red]")
        console.print("  [dim]Usa 'jobhunter help' para ver comandos disponibles[/dim]")


if __name__ == "__main__":
    main()
