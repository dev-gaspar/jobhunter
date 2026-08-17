# JobHunter Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** App de escritorio Windows (pywebview) + instalador Inno Setup para JobHunter, con onboarding gráfico, búsqueda/aplicación e historial, publicada en GitHub Releases.

**Architecture:** Se extrae una fachada `jobhunter/service.py` (funciones puras con eventos) de `pipeline.py`/`applying.py`; el CLI se reescribe encima sin cambio de comportamiento; `desktop/` (api.py puente + ui/ HTML/CSS/JS con el design system de la landing) consume la misma fachada; PyInstaller congela todo y Inno Setup lo empaqueta per-user.

**Tech Stack:** Python 3.12 (runtime congelado), pywebview 6 (WebView2), PyInstaller 6.20, Inno Setup 6, HTML/CSS/JS vanilla, unittest + mock.

**Spec:** `docs/superpowers/specs/2026-08-16-desktop-app-design.md`

## Global Constraints

- Python 3.10+ para todo `jobhunter/` (CI compila en 3.10): PROHIBIDO f-strings con comillas anidadas del mismo tipo y f-strings triple-quoted con quotes internos (ver CLAUDE.md).
- Todo texto de usuario (UI, instalador, errores) en español.
- El CLI no cambia de comportamiento: los tests existentes (29 archivos test_*.py) pasan sin modificarlos, salvo que un test dependa de detalles internos refactorizados (documentar si ocurre).
- `desktop/api.py` NUNCA importa `webview` (para testear sin GUI); solo `desktop/app.py` lo importa.
- Datos siempre en: repo (dev) o `%USERPROFILE%\.jobhunter` (frozen) — vía `JOBHUNTER_HOME`.
- Design system exacto de la landing: tokens `--bg:#000000 --bg-secondary:#0a0a0a --bg-card:#111111 --border:rgba(255,255,255,0.08) --border-hover:rgba(255,255,255,0.15) --text:#fafafa --text-secondary:#a1a1a1 --text-muted:#666666`; acentos `#22c55e` (ok) `#60a5fa` (info) `#a78bfa` (accent) `#fbbf24` (warn) + rojo error `#ef4444`; fuentes Outfit (títulos), Plus Jakarta Sans (texto), JetBrains Mono (datos); easing `cubic-bezier(0.16, 1, 0.3, 1)`; grain overlay.
- Commits frecuentes en `feature/desktop-app`; mensajes estilo repo (`feat:`, `fix:`, `docs:`, `build:`).

---

### Task 1: Rutas de datos overridables (`JOBHUNTER_HOME` + frozen)

**Files:**
- Modify: `jobhunter/constants.py:1-10`
- Test: `tests/test_constants_home.py` (nuevo)

**Interfaces:**
- Produces: `constants.BASE_DIR` ahora respeta `JOBHUNTER_HOME` env var; si `sys.frozen` y sin env var → `os.path.join(os.path.expanduser("~"), ".jobhunter")` (creado con makedirs). Sin cambios para CLI normal.

- [ ] **Step 1: Test que falla**

```python
# tests/test_constants_home.py
# -*- coding: utf-8 -*-
"""BASE_DIR debe respetar JOBHUNTER_HOME y modo frozen."""
import importlib
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


class TestConstantsHome(unittest.TestCase):
    def _reload(self):
        import jobhunter.constants as c
        return importlib.reload(c)

    def tearDown(self):
        os.environ.pop("JOBHUNTER_HOME", None)
        if hasattr(sys, "frozen"):
            del sys.frozen
        self._reload()

    def test_default_base_dir_is_repo_root(self):
        c = self._reload()
        self.assertTrue(os.path.exists(os.path.join(c.BASE_DIR, "jobhunter")))

    def test_env_var_overrides(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["JOBHUNTER_HOME"] = td
            c = self._reload()
            self.assertEqual(c.BASE_DIR, td)
            self.assertEqual(c.CONFIG_PATH, os.path.join(td, "config.json"))
            self.assertEqual(c.SESSION_DIR, os.path.join(td, ".session"))
            self.assertEqual(c.KB_PATH, os.path.join(td, "knowledge.json"))

    def test_frozen_uses_home_dotjobhunter(self):
        sys.frozen = True
        c = self._reload()
        expected = os.path.join(os.path.expanduser("~"), ".jobhunter")
        self.assertEqual(c.BASE_DIR, expected)
```

- [ ] **Step 2: Correr y ver fallo** — `python -m unittest tests.test_constants_home -v` → FAIL (env var ignorada).
- [ ] **Step 3: Implementar** en `constants.py`:

```python
import os
import sys

def _resolve_base_dir():
    env = os.environ.get("JOBHUNTER_HOME")
    if env:
        return env
    if getattr(sys, "frozen", False):
        d = os.path.join(os.path.expanduser("~"), ".jobhunter")
        os.makedirs(d, exist_ok=True)
        return d
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = _resolve_base_dir()
```

- [ ] **Step 4: Suite completa** — `python -m unittest discover -s tests -p "test_*.py"` → todo verde.
- [ ] **Step 5: Commit** — `feat(core): BASE_DIR overridable via JOBHUNTER_HOME y modo frozen`

### Task 2: Fachada `service.py` — búsqueda con eventos

**Files:**
- Create: `jobhunter/service.py`
- Modify: `jobhunter/pipeline.py` (cmd_run usa la fachada; misma UX terminal)
- Test: `tests/test_service_search.py` (nuevo); `tests/` existentes intactos

**Interfaces:**
- Produces:
  - `search_offers(cfg, kb, time_filter="24h", on_event=None) -> dict` con shape `{"offers": [job_dict], "stats": {...}, "decisions": [...], "error": None | {"kind": str, "message": str}}`. `error.kind` ∈ `("not_configured", "no_session", "session_expired", "no_posts", "scrape_failed")`.
  - Eventos emitidos (on_event(name: str, payload: dict)): `("phase", {"phase": "scrape"|"analyze"|"dedupe", "status": "start"|"done", "detail": str})`, `("progress", {"phase": str, "current": int, "total": int, "msg": str})`, `("decision", filter_decision_dict)`.
  - `record_run(kb, mode, posts, offers, sent, generated=None)` — appendea run entry (mismo shape actual) y `save_kb`.
  - `write_run_log(mode, stats, decisions, results)` — JSON a `output/logs/run_*.json` (shape actual).
  - job_dict conserva el shape actual del pipeline (is_job, job_title, company, contact_email, work_mode, salary, language, post_url, query, author_url, author_name, ...).
- Reglas de paridad: dedupe posts por `text[:150]`, dedupe ofertas por título+empresa, blacklist lowercase, cooldown 30 días `was_already_applied`, screenshots al filtro, sleeps entre queries/posts (parametrizables `pace=True` para poder apagarlos en tests).

- [ ] **Step 1: Tests que fallan** — `tests/test_service_search.py` con mocks de `sync_playwright`, `scrape_posts`, `agent_filter` (estilo test_applying.py: patch en el módulo consumidor `jobhunter.service`). Casos mínimos:

```python
# tests/test_service_search.py (esqueleto de casos, código completo al implementar)
# 1) no configurado -> error kind not_configured, sin eventos phase
# 2) sin SESSION_DIR -> error kind no_session
# 3) feed redirige a login -> session_expired
# 4) happy path 2 queries, 3 posts (1 sin email, 1 irrelevante, 1 oferta) ->
#    offers==1, eventos en orden: phase scrape start, progress x queries,
#    phase scrape done, phase analyze start, decision x2, phase analyze done,
#    phase dedupe start/done; stats correctos
# 5) oferta de empresa en blacklist se excluye
# 6) oferta ya aplicada (cooldown) se excluye
# 7) agent_filter lanza excepcion -> decision con is_job False y sigue
```

Cada caso es un `unittest.TestCase` con asserts sobre la lista `events` capturada por `on_event=lambda n, p: events.append((n, p))`.

- [ ] **Step 2: Ver fallar** — `python -m unittest tests.test_service_search -v`.
- [ ] **Step 3: Implementar `service.py`** moviendo el cuerpo de las fases 0-2 de `cmd_run` (líneas de guards, scrape loop, analyze loop, limpieza contact_email, dedupe, blacklist, history filter) SIN ningún `console.*`/`Prompt` — todo reporte via `on_event`. Firmas exactas de arriba. `pace: bool = True` para los `time.sleep`.
- [ ] **Step 4: Reescribir `pipeline.cmd_run`** para consumir `search_offers`: los paneles/banner/tabla/spinners/Prompt.ask de selección quedan en pipeline.py alimentados por eventos (un on_event que actualiza Rich Progress y imprime decisiones inline con el mismo formato actual). Export CSV/JSON, selección, loop de `apply_to_offer`, `record_run`, `write_run_log` — misma semántica.
- [ ] **Step 5: Suite completa verde** — incluye los 29 tests previos.
- [ ] **Step 6: Commit** — `feat(core): fachada service.search_offers con eventos; cmd_run la consume`

### Task 3: Fachada — preparar/enviar aplicación

**Files:**
- Create: (en `jobhunter/service.py`) `prepare_application`, `send_application`, `check_recipient`
- Modify: `jobhunter/applying.py` (apply_to_offer usa la fachada, misma firma/retornos)
- Test: `tests/test_service_apply.py` (nuevo); `tests/test_applying.py` sigue pasando sin cambios

**Interfaces:**
- Produces:
  - `prepare_application(cfg, job, test_email=None, on_event=None, pace=True) -> {"ok": bool, "cv_data": dict, "cv_path": str, "subject": str, "body": str, "error": str|None}` — 3 reintentos con sleep(5) (si pace) para agent_cv+PDF y para agent_email; con `test_email` el body YA incluye el banner `--- RECLUTADOR: ... ---`. Eventos: `("apply_progress", {"stage": "cv"|"email", "job_title": str, "company": str})`.
  - `check_recipient(email) -> True|False|None` — wrapper de `domain_accepts_mail`.
  - `send_application(cfg, kb, job, prepared, to, mode="run") -> {"status": "sent"|"error", "record": dict, "error": str|None}` — usa `prepared["subject"]/["body"]/["cv_path"]`; en éxito appendea a `kb["applications"]` el registro con shape actual (date, job_title[:80], company[:40], recruiter_email, sent_to, mode, post_url, subject, query, author_url, author_name). NO llama save_kb.
- `applying.apply_to_offer` conserva firma y retornos exactos; internamente: prepare → preview interactivo (igual) → check_recipient → send.

- [ ] **Step 1: Tests fallan** — casos: prepare happy (subject/body/cv_path correctos, banner test), prepare agotamiento de retries → ok False + error, send happy (kb append + status sent), send excepción SMTP → error, check_recipient passthrough.
- [ ] **Step 2: Ver fallar.**
- [ ] **Step 3: Implementar + refactor `applying.py`.**
- [ ] **Step 4: Suite completa verde (incluye test_applying.py intacto).**
- [ ] **Step 5: Commit** — `feat(core): prepare/send_application en fachada; applying delega`

### Task 4: Fachada — onboarding y sesión

**Files:**
- Create: (en `jobhunter/service.py`) `validate_gemini_key`, `verify_smtp`, `extract_profile_from_cv`, `linkedin_login`, `has_linkedin_session`, `regenerate_queries`
- Modify: `jobhunter/scraper.py` — `do_linkedin_login(interactive=True)`: el `input()` solo si interactive
- Modify: `jobhunter/cli/setup.py` — usa las funciones de fachada para validar key/smtp/cv (misma UX)
- Test: `tests/test_service_onboarding.py`

**Interfaces:**
- Produces:
  - `validate_gemini_key(key) -> {"ok": bool, "error": str|None}` — mismo POST de prueba del setup actual (gemini-2.5-flash generateContent, timeout 10).
  - `verify_smtp(email, password) -> {"ok": bool, "error": str|None}` — SMTP starttls+login como setup; valida regex `@gmail.com` y longitud >= 10 antes.
  - `extract_profile_from_cv(cfg, pdf_b64) -> {"ok": bool, "profile": dict|None, "error": str|None}` — mismo prompt vision del setup (copiar literal); valida `profile["name"]` truthy.
  - `linkedin_login() -> bool` — llama `do_linkedin_login(interactive=False)`.
  - `has_linkedin_session() -> bool` — `os.path.exists(SESSION_DIR)` con contenido.
  - `regenerate_queries(cfg) -> {"queries": [str], "from_ai": bool}` — wrapper `generate_queries` + guarda en cfg y `save_config`.

- [ ] **Step 1: Tests fallan** (requests/smtplib/call_gemini_vision mockeados).
- [ ] **Step 2-4: TDD igual que arriba; setup.py delega sin cambiar UX; suite verde.**
- [ ] **Step 5: Commit** — `feat(core): fachada de onboarding (key, smtp, cv, linkedin, queries)`

### Task 5: `desktop/api.py` — puente sin webview + `desktop/app.py`

**Files:**
- Create: `desktop/__init__.py`, `desktop/api.py`, `desktop/app.py`, `desktop/updates.py`
- Test: `tests/test_desktop_api.py`

**Interfaces:**
- Produces: clase `Bridge(emit)` donde `emit(name: str, payload: dict)` es inyectado (app.py pasa un closure sobre `window.evaluate_js`; tests pasan una lista). TODOS los métodos retornan `{"ok": bool, "data": ..., "error": str|None}` y capturan excepciones. Métodos:
  - Estado: `get_state()` → `{configured, version, has_session, profile_name, smtp_email_masked, gemini_key_masked, model, cv_template, templates, models, job_types, search_languages, user_languages, work_mode, user_location, links, onboarding}`.
  - Onboarding: `validate_gemini_key(key)`, `save_model(model)`, `pick_cv_file()` (app.py inyecta `open_file_dialog` callable; en tests un fake), `extract_cv(pdf_b64)`, `save_profile(profile)`, `save_links(portfolio, linkedin)`, `suggest_job_types()`, `save_job_types(raw)`, `save_languages(search_languages, user_languages)`, `save_work_mode(mode, location)`, `save_template(name)`, `verify_smtp(email, password)`, `linkedin_login_start()` (thread → evento `linkedin_done {ok}`), `finish_onboarding()` (thread: regenerate_queries → evento `onboarding_done {queries, from_ai}`).
  - Run: `start_search(time_filter, test_email=None)` (thread; lock `_busy`; eventos de service reenviados + `search_done {offers: [{id, ...campos]}`), `prepare_offer(offer_id)` (thread → `preview_ready {id, subject, body, cv_path}` o `prepare_error`), `send_offer(offer_id, subject=None, alt_email=None)` (MX check dentro: si `check_recipient` is False y sin alt_email → `{"ok": False, "error": "mx", "data": {"recruiter_email": ...}}` para que la UI pida alternativo), `skip_offer(offer_id)`, `finish_run()` (record_run + write_run_log + save_kb → `run_summary`), `open_cv(path)` (os.startfile solo bajo `output/cvs`), `open_url(url)` (webbrowser.open, solo http/https).
  - Historial: `get_history(last=50, company=None)` — lee kb, orden desc por date, shape del CLI history.
  - Ajustes/updates: `check_updates()` → delega `desktop/updates.py: get_latest(VERSION)` → `{update_available, latest, url}`; `download_update()` (descarga asset a %TEMP%, `os.startfile`, evento `update_launched`, cierra app).
- `desktop/updates.py`: `get_latest(current_version) -> dict` usando `https://api.github.com/repos/dev-gaspar/jobhunter/releases/latest`, compara tuplas semver, tolera red caída (`update_available: False`).
- `desktop/app.py`: crea `webview.create_window("JobHunter", url=ui/index.html, width=1140, height=760, min_size=(980, 640), background_color="#000000", js_api=bridge)`; `emit` hace `window.evaluate_js("window.bus && window.bus._recv(" + json.dumps(name) + "," + json.dumps(payload) + ")")`; flag `--selftest` (importa todo, resuelve paths, escribe `selftest_ok` y exit 0). `webview.start(gui="edgechromium")`.

- [ ] **Step 1: Tests fallan** — `Bridge` con emit fake y service mockeado: get_state sin config, start_search reenvía eventos y guarda ofertas con id, send con mx False pide alternativo, busy lock rechaza segunda operación, get_history ordena.
- [ ] **Step 2-4: TDD; suite verde.**
- [ ] **Step 5: Commit** — `feat(desktop): puente api + app pywebview + updates check`

### Task 6: UI — shell, design system, bus

**Files:**
- Create: `desktop/ui/index.html`, `desktop/ui/css/app.css`, `desktop/ui/js/bus.js`, `desktop/ui/js/util.js`, `desktop/ui/js/app.js`, `desktop/ui/fonts/{Outfit,PlusJakartaSans,JetBrainsMono}.ttf`, `desktop/ui/img/logo.svg`

**Interfaces:**
- Produces: `window.bus` con `on(name, fn)` / `_recv(name, payload)`; `api(method, ...args)` → Promise sobre `window.pywebview.api`; `app.css` con los tokens del design system (Global Constraints) + `@font-face` locales + grain overlay + clases `.btn-primary .btn-outline .badge .card .grid-cards .step-num .terminal` portadas de la landing; layout: sidebar izquierda (logo, nav: Buscar / Historial / Ajustes, versión abajo) + main content; router simple por `data-view`.
- `index.html` carga todo local (CSP-safe, cero CDNs), body `#000`, arranca en `#loading` → `api('get_state')` → onboarding o main.

- [ ] **Step 1: Maquetar shell + tokens + fuentes locales.**
- [ ] **Step 2: Verificación visual** — servir `desktop/ui/` estático con un stub `window.pywebview.api` de mock (archivo `desktop/ui/js/devmock.js` cargado solo si `!window.pywebview`) y revisar en browser (Claude Browser): fondo negro, fuentes, sidebar, grain.
- [ ] **Step 3: Commit** — `feat(desktop): shell de UI con design system de la landing`

### Task 7: UI — onboarding (10 pasos)

**Files:**
- Create: `desktop/ui/js/onboarding.js`, `desktop/ui/css/onboarding.css` (+ secciones en index.html)

**Interfaces:**
- Consumes: métodos Bridge de Task 5. Produces: wizard fullscreen con barra de progreso (% como el CLI), Atrás/Continuar, pasos: 1 Bienvenida (3 requisitos con iconos) · 2 API key (link externo `open_url` a aistudio, input con validación en vivo → `validate_gemini_key`, select de modelo) · 3 CV (dropzone: click → `pick_cv_file`, drag → FileReader base64 → `extract_cv`; luego tarjetas editables del perfil → `save_profile`) · 4 Links · 5 Tipos de empleo (chips `suggest_job_types` + input) · 6 Idiomas (selects niveles) · 7 Modalidad (+ ubicación condicional) · 8 Plantilla (4 miniaturas CSS estilizadas: modern/minimal/classic/compact) · 9 Gmail (guía visual App Password: pasos numerados con estilo `.step-num`, botón a `myaccount.google.com/apppasswords`, inputs con `verify_smtp`) · 10 LinkedIn (botón Conectar → `linkedin_login_start` → espera evento; skip si `has_session`). Final: `finish_onboarding` → spinner "Generando búsquedas con IA" → aviso si `from_ai` false → main.
- Reanudable: cada paso guarda al continuar; `get_state().onboarding` indica primer paso incompleto.

- [ ] **Step 1: Implementar wizard completo contra devmock.**
- [ ] **Step 2: Verificación visual en browser con devmock (los 10 pasos).**
- [ ] **Step 3: Commit** — `feat(desktop): onboarding grafico de 10 pasos`

### Task 8: UI — Buscar, Historial, Ajustes

**Files:**
- Create: `desktop/ui/js/run.js`, `desktop/ui/js/history.js`, `desktop/ui/js/settings.js`, `desktop/ui/css/views.css`

**Interfaces:**
- Consumes: Bridge Task 5 + eventos (`phase`, `progress`, `decision`, `search_done`, `preview_ready`, `prepare_error`, `sent`, `run_summary`, `linkedin_done`, `update_*`).
- Buscar: selector periodo (3 segmented buttons), toggle "Modo prueba" (input email propio), botón grande Buscar; timeline de fases estilo landing (step-num + línea de progreso) con contadores en vivo y feed de decisiones (scroll, iconos ✓/○/✗); tabla resultados con checkboxes + Aplicar; modal preview por oferta (Para/Asunto editable/cuerpo/chip CV → `open_cv`; botones Enviar/Saltar/Enviar todo); si error mx → prompt inline email alternativo; resumen final (enviadas/saltadas/errores) → `finish_run`.
- Historial: tabla (fecha, puesto, empresa, destinatario, modo TEST/RUN badge, link post → `open_url`), filtro por empresa (input) y botón "Ver todas".
- Ajustes: tarjetas por sección con los mismos formularios del onboarding reutilizados (editar individual + guardar); estado conexiones (Gemini/Gmail/LinkedIn con re-verificar / re-login); zona "Acerca de": versión, botón "Buscar actualizaciones" → banner con `download_update`.

- [ ] **Step 1: Implementar las 3 vistas contra devmock (con datos de ejemplo realistas).**
- [ ] **Step 2: Verificación visual en browser: flujo búsqueda completo simulado, historial, ajustes.**
- [ ] **Step 3: Commit** — `feat(desktop): vistas buscar/historial/ajustes`

### Task 9: Integración real end-to-end local (sin congelar)

**Files:**
- Modify: lo que surja (bugs de integración)

- [ ] **Step 1:** `python -m desktop.app` con `JOBHUNTER_HOME` apuntando a un dir temporal: onboarding real completo (API key real del config actual, CV real, SMTP real, LinkedIn ya con sesión → copiar `.session` al home temporal para no re-login).
- [ ] **Step 2:** Búsqueda en modo prueba (test_email propio) con envío real de 1 oferta a correo propio. Verificar historial y knowledge.json.
- [ ] **Step 3:** Commit de fixes — `fix(desktop): ajustes de integracion e2e`

### Task 10: Empaquetado PyInstaller

**Files:**
- Create: `desktop/packaging/jobhunter.spec`, `desktop/packaging/version_info.txt`, `desktop/packaging/gen_assets.py` (icono .ico + BMPs instalador con Pillow), `desktop/packaging/build.ps1`

**Interfaces:**
- Produces: `dist/JobHunter/JobHunter.exe` (onedir, console=False, icon, version info 2.0.0). El spec: entry `desktop/app.py`; `datas`: `desktop/ui` → `ui`; hiddenimports/collect: `collect_all("playwright")` (driver node incluido), `jobhunter` completo (+ `jobhunter/assets`), `collect_all("webview")`; excludes de tkinter. `app.py` resuelve `ui/` via `sys._MEIPASS`-style (`os.path.join(os.path.dirname(sys.executable), "_internal", "ui")` en onedir de PyInstaller 6, con fallback a ruta fuente en dev).
- `build.ps1`: `python desktop/packaging/gen_assets.py && pyinstaller --noconfirm desktop/packaging/jobhunter.spec && dist\JobHunter\JobHunter.exe --selftest` (exit code 0 = ok).

- [ ] **Step 1:** Escribir spec + assets + build; correr build.ps1.
- [ ] **Step 2:** Smoke: `--selftest` exit 0; lanzar exe y completar un get_state real (ventana abre, onboarding o main visible).
- [ ] **Step 3:** Commit — `build(desktop): empaquetado pyinstaller onedir con selftest`

### Task 11: Instalador Inno Setup

**Files:**
- Create: `desktop/packaging/installer.iss`
- Modify: `desktop/packaging/build.ps1` (paso iscc + descarga WebView2 bootstrapper)

**Interfaces:**
- Produces: `dist/JobHunterSetup-x64.exe`. `installer.iss`: AppId `{{8B1F3D7A-6E1C-4C29-9C7D-JOBHUNTER01}` fijo; AppName JobHunter; AppVersion desde constants (build.ps1 lo extrae y pasa por `/D`); `PrivilegesRequired=lowest`; `DefaultDirName={localappdata}\Programs\JobHunter`; `WizardStyle=modern`; `Languages: Spanish.isl`; WizardImageFile/WizardSmallImageFile de gen_assets (dark brand); Tasks: desktopicon (checked); `[Files]` dist\JobHunter\* recursivo + `MicrosoftEdgeWebView2Setup.exe`; `[Run]` postinstall launch (unchecked opcional `runascurrentuser`) + WebView2 bootstrapper silencioso solo si falta (Check: función Pascal que lee registro `SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` HKLM/HKCU); `CloseApplications=yes`; el desinstalador NO toca `%USERPROFILE%\.jobhunter`.

- [ ] **Step 1:** Escribir .iss; build completo; instalar en la máquina real.
- [ ] **Step 2:** Verificar: app instalada arranca desde el acceso directo, datos van a `~/.jobhunter` (comparte config existente), desinstalar deja `~/.jobhunter` intacto, reinstalar funciona.
- [ ] **Step 3:** Commit — `build(desktop): instalador inno setup per-user en espanol`

### Task 12: CI release + landing + docs

**Files:**
- Modify: `.github/workflows/release.yml` (job `windows-installer` en windows-latest: setup-python 3.12, pip install -r requirements.txt + pywebview pyinstaller pillow, `choco install innosetup -y`, descarga bootstrapper WebView2 (`https://go.microsoft.com/fwlink/p/?LinkId=2124703`), gen_assets, pyinstaller, ISCC, sube `JobHunterSetup-x64.exe` al release junto a install.sh/ps1; body del release con sección Windows).
- Modify: `.github/workflows/ci.yml` (compileall también `desktop/`; los tests nuevos ya entran por discover).
- Modify: `web/index.html` (hero + sección install: botón "Descargar para Windows" → `https://github.com/dev-gaspar/jobhunter/releases/latest/download/JobHunterSetup-x64.exe`, nota SmartScreen con detalle "Más información → Ejecutar de todas formas"; tabs de instalación por consola se conservan debajo).
- Modify: `README.md` (sección "App de escritorio (Windows)" arriba de instalación CLI) y `CLAUDE.md` (breve: desktop/ + service.py en key files).
- Modify: `jobhunter/constants.py` → `VERSION = "2.0.0"`.

- [ ] **Step 1:** Implementar todo; `python -m unittest discover` verde; commit — `feat(release): installer windows en CI, landing con descarga, v2.0.0`
- [ ] **Step 2:** Push `feature/desktop-app`, PR a `main`, verificar CI del PR en verde (los jobs de test corren en PR a main).
- [ ] **Step 3:** Merge del PR (squash no — merge normal como los PRs previos), tag `v2.0.0` en main, push tag.
- [ ] **Step 4:** Monitorear el workflow de release hasta que el asset `JobHunterSetup-x64.exe` esté publicado; descargar y smoke-test local del instalador del release.

### Task 13: Verificación final

- [ ] Checklist E2E sobre el artefacto del release: instalar → abrir → estado correcto → (con datos ya configurados) búsqueda modo prueba OK → historial muestra el envío → Ajustes muestra conexiones ✓ → desinstalar conserva datos.
- [ ] Actualizar spec/plan con desviaciones si las hubo; commit final.

## Self-Review (hecho al escribir)

- Cobertura del spec: rutas de datos (T1), fachada (T2-4), GUI completa (T5-8), integración (T9), PyInstaller (T10), Inno (T11), updates+CI+landing (T12, updates en T5 `desktop/updates.py`), SmartScreen documentado (T12 landing), testing (T1-5 unit, T10 selftest, T13 checklist). Sin huecos.
- Sin placeholders TBD; los pasos de UI especifican archivos, métodos consumidos, eventos y comportamiento exacto.
- Consistencia de firmas revisada entre T2/T3/T5 (search_offers/prepare_application/send_application/check_recipient usados por Bridge).
