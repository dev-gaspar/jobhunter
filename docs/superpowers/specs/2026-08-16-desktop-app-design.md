# JobHunter Desktop — App de escritorio Windows + instalador

**Fecha:** 2026-08-16
**Estado:** Aprobado (diseño validado por secciones con Jose)
**Alcance:** v1 — app de escritorio completa para usuarios no técnicos

## Contexto y objetivo

JobHunter AI hoy es un CLI Python que requiere Python, Git y terminal — inaccesible
para usuarios no técnicos. Este proyecto crea:

1. Una **app de escritorio Windows** que es la interfaz principal para no técnicos:
   onboarding gráfico (CV, API key, Gmail, LinkedIn, preferencias), búsqueda y
   aplicación a ofertas, e historial.
2. Un **instalador moderno** (.exe) sin dependencias externas: todo empaquetado,
   sin pedir Python, Git ni admin.
3. Misma identidad visual que la landing de GitHub Pages (`web/index.html`).

El CLI sigue existiendo sin cambios de comportamiento para usuarios técnicos.

## Decisiones cerradas

| Decisión | Elección |
|---|---|
| Alcance | App de escritorio completa (GUI = interfaz principal) |
| Funciones v1 | Onboarding + búsqueda/aplicación (run) + historial |
| Stack | pywebview (WebView2) + PyInstaller onedir + Inno Setup |
| Distribución | GitHub Releases; aviso de update en la app con botón de descarga |
| Gmail | App Password con asistente visual (sin OAuth en v1) |
| Ubicación del código | Mismo repo, carpeta `desktop/` |
| Datos | Compartidos con el CLI en `%USERPROFILE%\.jobhunter\` |
| Idioma | Todo en español (UI, instalador, errores) |

## Arquitectura

```
jobhunter/            paquete existente (cambios mínimos)
  service.py          NUEVO: fachada con eventos, consumida por CLI y GUI
desktop/              proyecto nuevo, aislado
  app.py              entry point: ventana pywebview + registro del API
  api.py              puente JS↔Python (js_api de pywebview)
  ui/                 HTML/CSS/JS estático — sin frameworks, sin build step
  packaging/          jobhunter.spec (PyInstaller), installer.iss (Inno Setup),
                      build.ps1, assets del instalador
```

### Cambio 1 al core: rutas de datos (`constants.py`)

Hoy `CONFIG_PATH`, `SESSION_DIR`, `KB_PATH` y `output/` derivan de `BASE_DIR`
(raíz del repo). Cambio:

- Si `sys.frozen` (app empaquetada): la raíz de datos es `%USERPROFILE%\.jobhunter\`.
- Si no (CLI desde repo): comportamiento actual intacto.
- Overridable con env var `JOBHUNTER_HOME` (útil para tests y debugging).

Consecuencia: CLI y app instalada comparten config, historial, sesión de
LinkedIn y CVs generados. El desinstalador nunca toca esta carpeta.

### Cambio 2 al core: fachada `jobhunter/service.py`

`pipeline.py` y `applying.py` mezclan lógica con prompts interactivos de Rich.
Se extraen tres operaciones puras que emiten eventos y no conocen al frontend:

- `search_offers(cfg, time_filter, on_event) -> list[Offer]`
  Fases: scraping → análisis IA → deduplicación. Eventos de progreso por fase
  (fase, avance, mensaje humano).
- `prepare_application(cfg, offer, on_event) -> Prepared`
  Genera CV PDF + email. Retorna asunto, cuerpo, ruta del PDF.
- `send_application(cfg, offer, prepared, edits) -> Result`
  Envío SMTP + registro en knowledge.json. `edits` permite asunto modificado.

El CLI se reescribe encima de la fachada conservando su UX de terminal exacta
(tabla Rich, preview, enviar/saltar/auto). Un solo pipeline, dos frontends.
El modo test (`--test email`) es un parámetro de la fachada, no una rama aparte.

### Modelo de ejecución de la GUI

- Operaciones largas (búsqueda, generación, envío) corren en un hilo de fondo.
- Python → UI: `window.evaluate_js("bus.emit(evento, payload)")`.
- UI → Python: métodos del `js_api` de pywebview. Cortos: retorno síncrono
  `{ok, data|error}`. Largos: retornan de inmediato y el resultado llega por eventos.
- Una sola operación larga a la vez (lock); la UI deshabilita acciones mientras.

## Pantallas

Estilo: design system de la landing — fondo `#000`, tarjetas `#111`, bordes
`rgba(255,255,255,0.08)`, tipografías Outfit / Plus Jakarta Sans / JetBrains Mono,
grain overlay. Ventana única ~1140×760, tema oscuro fijo. Las fuentes se
empaquetan localmente (sin Google Fonts en runtime: la app debe funcionar offline
salvo para las operaciones que son online por naturaleza).

### Onboarding (primera ejecución, wizard con barra de progreso y Atrás/Continuar)

Orden optimizado — la API key va antes que el CV porque la extracción lo necesita:

1. **Bienvenida** — qué hace la herramienta; qué necesitas: API key gratis, Gmail, CV en PDF.
2. **Gemini API key** — botón que abre aistudio.google.com/apikey; validación en
   vivo (verificación HTTP actual); selección de modelo con descripciones simples.
3. **Tu CV** — drag & drop del PDF → extracción con Gemini → perfil extraído en
   tarjetas **editables** (nombre, título, experiencia, skills) para corregir a la IA.
4. **Links** — portfolio y LinkedIn (opcional).
5. **Tipo de empleo** — sugerencias IA como chips clicables + campo libre.
6. **Idiomas** — idiomas de búsqueda y niveles del usuario con selects (nada de
   texto libre con formato `Idioma:Nivel`).
7. **Modalidad** — remoto/híbrido/presencial/cualquiera; ubicación si aplica.
8. **Plantilla de CV** — las 4 plantillas con miniaturas visuales reales.
9. **Gmail** — asistente visual de App Password: aviso si falta 2FA, botón directo
   a la página de contraseñas de aplicación de Google, capturas del proceso,
   campo con validación y verificación SMTP automática.
10. **LinkedIn** — botón "Conectar LinkedIn" que lanza el Chrome de Playwright
    (flujo `do_linkedin_login` actual); la app detecta el login completado.

Al finalizar: generación de queries con IA (flujo actual) → pantalla principal.
Si el onboarding se interrumpe, al reabrir continúa donde quedó (config parcial).

### Buscar (pantalla principal)

- Selector de periodo (24h / semana / mes), toggle **modo prueba** (envía a tu
  propio correo — el `--test` actual) y botón grande "Buscar ofertas".
- Progreso en vivo: timeline de fases (buscando en LinkedIn → analizando con IA →
  filtrando duplicados) alimentado por los eventos de la fachada.
- Resultados: tabla con checkboxes — cargo, empresa, ubicación, salario, idioma.
  Seleccionar todas/ninguna. Botón "Aplicar a seleccionadas".
- Por oferta: modal de **preview** — asunto editable, cuerpo, enlace al PDF
  (abre con el visor del sistema). Botones: Enviar / Saltar / Enviar todo lo restante.
- Resumen final: enviadas, saltadas, errores.

### Historial

Tabla desde `knowledge.json`: fecha, cargo, empresa, destinatario, estado.
Filtros por empresa y fecha. Acceso al PDF enviado de cada aplicación.

### Ajustes

- Cada dato del onboarding editable individualmente (sin repetir el wizard).
- Estado de conexiones: Gemini ✓ / Gmail ✓ / LinkedIn ✓, con re-verificación y
  re-login de LinkedIn.
- Versión instalada + banner de actualización con botón "Actualizar".

## Empaquetado e instalador

### PyInstaller (onedir)

- Congela Python 3.12 + `pywebview`, `requests`, `playwright`, `reportlab`,
  `rich`, el paquete `jobhunter` y `desktop/ui/`. `console=False`, icono,
  metadata de versión.
- Playwright usa el **Chrome/Edge del sistema** (como hoy) — no se descargan
  navegadores. Edge está preinstalado en todo Windows soportado.
- La GUI no pasa por `job.py` (que hace pip install al arrancar): el bundle ya
  trae todas las dependencias.
- Tamaño instalado estimado: 150–200 MB.

### Inno Setup

- Español, `WizardStyle=modern`, imágenes custom a juego con la marca (oscuro).
- `PrivilegesRequired=lowest` → instala per-user en
  `%LOCALAPPDATA%\Programs\JobHunter`, sin UAC.
- Accesos directos: menú inicio + escritorio (opcional). "Ejecutar al terminar".
- Detecta app abierta antes de instalar/actualizar y pide cerrarla.
- El desinstalador **no borra** `%USERPROFILE%\.jobhunter\` (datos y sesión
  sobreviven reinstalaciones).
- Si falta WebView2 (Windows 10 antiguo): instala el Evergreen Bootstrapper
  oficial de Microsoft en silencio.

### Updates

- Al arrancar: `GET api.github.com/repos/dev-gaspar/jobhunter/releases/latest`,
  compara el tag semver con `VERSION`. Falla en silencio si no hay red.
- Si hay nueva versión: banner discreto + botón que descarga el
  `JobHunterSetup-x64.exe` del release y lo ejecuta; la app se cierra sola.
- Sin auto-update silencioso en v1.

### Release CI

- Se extiende `.github/workflows/release.yml`: al taggear `v*`, un job en
  `windows-latest` corre PyInstaller + Inno Setup (iscc) y adjunta
  `JobHunterSetup-x64.exe` al release.
- La landing gana un botón "Descargar para Windows" apuntando al último release,
  con una nota sobre el aviso de SmartScreen.

### Limitación conocida: SmartScreen

Sin firma de código, Windows muestra el aviso azul la primera vez
("Más información → Ejecutar de todas formas"). v1 lo documenta en la landing
con captura. Si el proyecto crece: Azure Trusted Signing (~10 USD/mes).

## Manejo de errores

- Toda llamada del `js_api` retorna `{ok: bool, data|error}`; errores con
  mensajes humanos en español.
- El hilo del pipeline captura excepciones y emite eventos de error por fase:
  - Sesión LinkedIn caducada → "Tu sesión de LinkedIn caducó — reconéctala en Ajustes".
  - Gemini 429/cuota → "Gemini sin cuota — espera unos minutos o cambia de modelo".
  - SMTP falla → guía para regenerar la App Password.
- Log de la app en `output/logs/desktop.log` (rotación simple) para soporte.

## Testing

- **Unit tests** de `service.py` con scraper/IA/SMTP mockeados: secuencia de
  eventos correcta, decisiones respetadas, modo test, edits de asunto.
- Los tests existentes siguen pasando sin cambios: el CLI conserva su
  comportamiento exacto sobre la nueva fachada.
- **Smoke test del build** en CI: la app congelada arranca y responde a un flag
  `--selftest` (verifica imports, rutas de datos, arranque del API).
- **Checklist manual E2E** en Windows Sandbox: instalar → onboarding completo con
  cuenta real → búsqueda en modo prueba → historial → simular update.

## Fuera de alcance v1 (explícito)

- OAuth de Google (la capa de credenciales queda tras la fachada; añadirlo en v2
  no toca la UI del resto).
- Auto-update silencioso.
- Firma de código.
- Cifrado DPAPI de secretos (`config.json` queda plano, igual que hoy).
- macOS / Linux.
- optimize / sync / network / blacklist / dashboard en GUI (v2; el dashboard
  HTML autocontenido existente es el candidato más fácil).

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Refactor de pipeline rompe el CLI | La fachada se extrae con tests de caracterización antes de mover código; los tests actuales deben pasar intactos |
| Falsos positivos de antivirus con PyInstaller | onedir (no onefile), metadata de versión completa, sin UPX; documentado; firma en el futuro |
| `rich`/`console` imprime en app sin consola | La GUI nunca importa los frontends CLI; `console.is_terminal` ya es False en frozen |
| dev desactualizado respecto a main (27 commits) | La rama `feature/desktop-app` sale de `main`; conciliar dev/main es tarea aparte |
| Extracción del CV falla con PDFs raros | Ya hay reintentos + validación de `name`; la UI permite editar el perfil extraído |
