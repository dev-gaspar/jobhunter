# Contribuir a JobHunter AI

Gracias por querer contribuir. Este documento resume como trabajar sobre el proyecto de forma ordenada.

## Estructura del proyecto

```
job.py                   entry point (shim, NO toques la firma)
jobhunter/               paquete modular
|-- constants.py         constantes, paths, banners
|-- config.py            carga/guarda config.json
|-- storage.py           knowledge.json
|-- ui.py                console singleton de Rich
|-- banner.py            banner ASCII
|-- updater.py           check_for_updates + cmd_update
|-- browser.py           find_chrome + kill zombies de Playwright
|-- scraper.py           scrape_posts + do_linkedin_login
|-- mailer.py            send_email via Gmail SMTP
|-- pipeline.py          cmd_run (orquestador)
|-- offers.py            dedup, extract_emails, cooldown
|-- ai/
|   |-- base.py          interfaz AIProvider (puerto)
|   |-- gemini.py        adaptador Gemini (unico provider actual)
|-- agents/
|   |-- filter.py        agent_filter
|   |-- cv.py            agent_cv (anti-invencion estricta)
|   |-- email.py         agent_email
|   |-- optimizer.py     optimize_queries
|-- cv/
|   |-- builder.py       router de plantillas PDF + ATS normalization
|   |-- templates/       4 plantillas: modern, minimal, classic, compact
|-- cli/
    |-- main.py          dispatcher + parse_time_filter
    |-- setup.py, status.py, history.py, blacklist.py, help.py,
    |   login.py, optimize.py    comandos individuales
tests/                   unittest, un test por modulo
.github/workflows/
|-- ci.yml               tests en matriz Python 3.10-3.13 + smoke
|-- deploy.yml           GitHub Pages
|-- release.yml          release al hacer tag v*
```

## Flujo de ramas

- **`main`** es la rama estable. Los releases se sacan de aqui.
- **`dev`** es la rama de integracion. Todas las features entran aqui.
- **`feature-xxx`** son ramas de features. Merge a `dev` via PR.
- **Nunca push directo a `main`.** Solo merges desde `dev` via PR con CI verde y una aprobacion.

```
feature-xxx --PR--> dev --PR--> main
```

## Como proponer un cambio

1. **Fork** el repo y clona tu fork.
2. **Crea una rama** desde `dev`:
   ```
   git checkout dev && git pull
   git checkout -b feature/tu-cambio
   ```
3. Haz tus cambios y **corre los tests locales**:
   ```
   python -c "import py_compile; py_compile.compile('job.py', doraise=True)"
   python -m unittest discover -s tests -p "test_*.py" -v
   python job.py --help          # smoke test rapido
   python job.py status          # smoke test rapido
   ```
4. **Commitea** con mensaje claro (ver convencion mas abajo).
5. **Push** y abre un **PR a `dev`** (no a `main`).
6. Espera a que la CI pase (matriz 3.10-3.13 + smoke). Si falla, revisa los logs y corrige.

## Pre-commit hooks (recomendado)

Instala los hooks una vez para que cada commit corra checks locales:

```
pip install pre-commit
pre-commit install              # pre-commit
pre-commit install -t pre-push  # para correr tests antes de push
```

Los hooks configurados en [.pre-commit-config.yaml](./.pre-commit-config.yaml):

- **Hygiene**: trailing whitespace, end-of-file, JSON/YAML validos, merge conflicts, no archivos >500KB, no `breakpoint()` olvidado
- **Ruff**: errores de sintaxis y imports no usados (sin reformatear)
- **Compile check**: `py_compile` de cada archivo Python cambiado
- **Unittests en pre-push**: corre la suite antes de cada `git push`

Para correr todos los hooks contra el repo completo:

```
pre-commit run --all-files
```

## Convenciones de codigo

### Python 3.10 compatibility (CRITICO)

El proyecto soporta Python 3.10+. La CI valida 3.10/3.11/3.12/3.13 en cada push.

**No uses f-strings con comillas anidadas** — rompe Python 3.10 y 3.11:

```python
# MAL: rompe en Py 3.10
f"""...{l['key']}..."""
f"...{f'nested {x}'}..."

# BIEN:
val = l["key"]
f"...{val}..."
```

### Estilo

- **CLI en espanol** (prompts, mensajes, errores). Los nombres de funciones/variables en ingles/neutro.
- **Sin emojis en la CLI.** Usa simbolos Unicode: `\u2713` (V), `\u2717` (X), `\u2726` (asterisco). Memoria del proyecto.
- **Sin comentarios innecesarios.** Nombres descriptivos > comentarios. Solo comenta el *por que* cuando no es obvio.
- **Strings largos (prompts de agentes):** OK usar f-strings multilinea, pero pre-computa valores con nested quotes.

### Commits

Formato: `type(scope): mensaje corto`

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `ci`, `chore`, `style`, `revert`.

Scopes comunes: numero de fase (`1.2`), modulo (`mailer`, `pipeline`), area (`setup`, `agents`).

Ejemplos reales del proyecto:

```
feat: censurar credenciales en setup y update interactivo con y/n
fix: preservar portfolio y linkedin ingresados manualmente al leer el CV
refactor(6): extraer cmd_run a jobhunter/pipeline.py
test(agents): cubrir optimize_queries con caso de division por cero
```

Una linea de titulo (< 72 chars). Si el cambio requiere explicacion, deja una linea en blanco y explica el "por que".

## Tests

**Cada modulo nuevo o modificado requiere sus tests.** La CI no merge sin tests verdes.

- Framework: `unittest` (stdlib, sin dependencias extra).
- Ubicacion: `tests/test_<modulo>.py`.
- Mocks: `unittest.mock.patch` para I/O, red, SMTP, subprocess, Playwright.
- Fixtures: `tests/fixtures/` (config_sample.json, kb_sample.json).

### Que se testea

| Tipo | Como testear |
|------|--------------|
| Puros (config, storage, offers) | Round-trip, edge cases, invariantes |
| Adapters (gemini, mailer, updater) | Mock de `requests.post`, `smtplib.SMTP`, `subprocess.run` |
| Agentes | Mock `call_gemini`, verificar prompts (que contienen campos), parseo JSON, manejo de errores |
| CLI commands | Mock `load_config`, `load_kb`, capturar `console.print` via mock |
| Pipeline | Guards (is_configured, sesion), orquestacion con todo mockeado |
| Setup wizard | Helpers puros (`_mask_secret`, `_ask`, `_ask_secret`); el flujo completo es smoke manual |

### Correr los tests

```
python -m unittest discover -s tests -p "test_*.py" -v
```

Para un solo modulo:

```
python -m unittest tests.test_agents_cv -v
```

## CI y proteccion de main

- `.github/workflows/ci.yml` corre en cada push a `dev` y cada PR a `main` o `dev`.
- Matriz Python 3.10/3.11/3.12/3.13 — los 4 deben pasar.
- Job extra `block-direct-push-to-main` falla si alguien empuja directo a `main`.
- La proteccion dura esta en GitHub Settings > Branches (requiere PR, CI verde, 1 aprobacion).

## Puntos de extension comunes

- **Cambiar proveedor de IA** (ej. usar Claude en vez de Gemini): implementa `AIProvider` en `jobhunter/ai/claude.py` siguiendo `jobhunter/ai/base.py`. Inyectalo en los agentes.
- **Agregar una plantilla de CV**: crea `jobhunter/cv/templates/tuplantilla.py` copiando el patron de `modern.py`, registrala en `jobhunter/cv/templates/__init__.py`.
- **Soportar otra red social (no LinkedIn)**: duplica `jobhunter/scraper.py` a `jobhunter/scrapers/indeed.py` con la misma firma `scrape_posts(page, query, time_filter)`. El pipeline no necesita cambios.
- **Agregar un comando nuevo**: crea `jobhunter/cli/tucomando.py` con `def cmd_tucomando(...)`, y registralo en el dispatcher de `jobhunter/cli/main.py`.

## Que NO hacer

- No mezcles refactor + feature en el mismo PR.
- No romper la firma de `job.py` (install.sh / install.ps1 dependen de ella).
- No metas secretos (config.json, knowledge.json, .session/) al repo. Ya estan en `.gitignore`.
- No uses `--no-verify` al commitear para saltarte hooks.
- No hagas force-push a `main` ni a `dev`.

## Reporte de bugs

Abre un issue en GitHub incluyendo:

- Sistema operativo + version Python (`python --version`).
- Comando exacto que ejecutaste.
- Output completo (sin credenciales).
- Contenido relevante de `output/logs/` si aplica.

## Dudas

Abre un issue con el tag `question` o inicia una discusion en Discussions. Las PRs pequenas y bien enfocadas siempre seran bienvenidas.
