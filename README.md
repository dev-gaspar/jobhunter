# JobHunter AI

Herramienta CLI que automatiza la busqueda de empleo en LinkedIn. Escanea publicaciones, identifica ofertas relevantes, genera CVs personalizados con IA, y envia emails de aplicacion a reclutadores.

Funciona para cualquier sector: tecnologia, marketing, ventas, diseno, administracion, salud, educacion, etc.

## Instalacion rapida

**macOS / Linux:**

```bash
curl -sSL https://raw.githubusercontent.com/dev-gaspar/jobhunter/main/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/dev-gaspar/jobhunter/main/install.ps1 | iex
```

Esto instala el comando `jobhunter` globalmente en tu terminal.

## Comandos

```
jobhunter setup                          Configuracion inicial
jobhunter login                          Iniciar sesion en LinkedIn
jobhunter --test email@test.com          Modo prueba (envia a tu correo)
jobhunter run                            Modo produccion (envia a reclutadores)
jobhunter status                         Ver configuracion y estadisticas
jobhunter update                         Actualizar a la ultima version
jobhunter help                           Ver ayuda completa
```

## Opciones

### Filtro de tiempo

```
jobhunter --test email@test.com --time 24h      Ultimas 24 horas (por defecto)
jobhunter --test email@test.com --time week      Esta semana
jobhunter run --time month                       Este mes
```

### Modo automatico

Por defecto, despues del analisis se muestra una tabla con las ofertas encontradas y puedes elegir a cuales aplicar:

```
Aplicar a: 1,3,5      Solo esas ofertas
Aplicar a: all         Todas las ofertas
Aplicar a: q           Cancelar
```

Para saltar la seleccion y enviar a todas automaticamente:

```
jobhunter run --auto
jobhunter --test mi@email.com --auto
```

### Modelos de Gemini

Durante `jobhunter setup` puedes elegir el modelo de IA:

| Modelo | Descripcion |
|--------|-------------|
| `gemini-2.5-flash` | Rapido y eficiente (por defecto) |
| `gemini-2.5-flash-lite` | Mas ligero, menor consumo de API |
| `gemini-2.5-pro` | Mayor calidad, mas lento |
| `gemini-3-flash-preview` | Ultima generacion, rapido |
| `gemini-3.1-pro-preview` | Ultima generacion, alta calidad |
| `gemini-3.1-flash-lite-preview` | Ultima generacion, ligero |

### Filtrado de duplicados

No envia el mismo cargo a la misma empresa si ya se envio en los ultimos 30 dias. Diferentes cargos a la misma empresa si se permiten.

## Como funciona (alto nivel)

1. **Setup**: Configuras tu API key de Gemini, eliges el modelo de IA, correo Gmail, subes tu CV, y defines que tipo de empleo buscas
2. **Login**: Inicias sesion en LinkedIn una vez (la sesion se guarda)
3. **Busqueda**: El sistema busca publicaciones en LinkedIn con tus terminos, expande el texto de cada post, y extrae emails de reclutadores
4. **Analisis**: Un agente de IA analiza cada publicacion para determinar si es una oferta real y relevante para tu perfil
5. **Seleccion**: Se muestra una tabla con las ofertas encontradas y puedes elegir a cuales aplicar (o usar `--auto` para todas)
6. **CV personalizado**: Otro agente de IA genera un CV en PDF adaptado a cada oferta especifica, reescribiendo tu experiencia y habilidades para que encajen con lo que piden
7. **Email personalizado**: Un tercer agente escribe un email de aplicacion corto, directo, y humano
8. **Envio**: Se envia el email con el CV adjunto al reclutador via Gmail SMTP

## Como esta hecho (bajo nivel)

### Arquitectura

El sistema es un script Python (`job.py`) que orquesta 4 componentes:

```
job.py
 ├── Playwright (scraping de LinkedIn)
 ├── Gemini API (3 agentes de IA, modelo configurable)
 ├── ReportLab (generacion de PDFs)
 └── SMTP (envio de emails)
```

### Scraping con Playwright

- Usa Playwright con **sesiones persistentes** en `.session/`. Inicias sesion una vez y queda guardada.
- Ejecuta Chrome real del sistema (no Chromium) para evitar bloqueos de Google Auth.
- Busca en `/search/results/content/` con parametros `datePosted` y `sortBy` para filtrar por fecha.
- Hace scroll para cargar posts y ejecuta `button[data-testid="expandable-text-button"].click()` via JavaScript para expandir el texto completo de cada publicacion.
- Extrae el contenido de cada post individualmente usando `span[data-testid="expandable-text-box"]`.
- Extrae emails con regex directamente del texto expandido.

### Sistema Multi-Agente (Gemini)

Tres agentes especializados, cada uno con su propio system prompt:

**Agente 1 - Filtrador**: Recibe el texto de un post y determina si es una oferta real, si es relevante para el perfil del usuario, y extrae toda la informacion estructurada (titulo, empresa, requisitos, email, salario, ubicacion).

**Agente 2 - CV Writer**: Toma el perfil del usuario y la oferta, y genera un CV completamente personalizado. Reescribe el resumen profesional, reordena skills, y reescribe cada bullet de experiencia para que conecte con lo que la oferta pide.

**Agente 3 - Email Writer**: Genera un email de aplicacion corto (max 100 palabras), en espanol neutro, texto plano, sin frases de plantilla, con 1-2 logros concretos con numeros.

Los tres agentes usan el modelo de Gemini seleccionado durante el setup via HTTP POST directo (sin SDK). Cada llamada tiene reintentos con backoff exponencial para manejar rate limits (429).

### Generacion de PDFs

`src/cv_builder.py` usa ReportLab para generar PDFs con formato profesional:
- Layout de una pagina con secciones: resumen, habilidades, experiencia, proyectos, educacion
- Tipografia Helvetica con jerarquia visual
- Los textos se escapan para evitar errores XML de ReportLab

### Envio de emails

- Gmail SMTP con TLS en puerto 587
- App Password de Google (no la contrasena normal)
- CV adjunto como PDF
- Reintentos en caso de fallo de conexion

### Almacenamiento

- `config.json`: Configuracion del usuario (API keys, modelo, perfil, queries de busqueda)
- `knowledge.json`: Historial de ejecuciones y aplicaciones enviadas
- `.session/`: Datos de sesion persistente de Playwright/Chrome
- `output/cvs/`: CVs generados en PDF
- `output/logs/`: Logs JSON de cada ejecucion

### Dependencias

- Python 3.10+
- playwright (scraping)
- requests (API de Gemini)
- reportlab (PDFs)
- rich (interfaz CLI)

Se instalan automaticamente la primera vez que ejecutas `jobhunter`.

## Landing page

Desplegada automaticamente en GitHub Pages: [https://dev-gaspar.github.io/jobhunter/](https://dev-gaspar.github.io/jobhunter/)
