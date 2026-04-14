# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

JobHunter AI — Spanish-language Python CLI that automates job searching on LinkedIn. It scrapes LinkedIn posts, uses multi-agent AI (Google Gemini) to filter offers and generate personalized CVs/emails, then sends applications via Gmail SMTP.

## Commands

```bash
jobhunter setup                      # Interactive 7-step setup wizard
jobhunter login                      # One-time LinkedIn auth (persistent Chrome session)
jobhunter run                        # Full pipeline: scrape → filter → generate → send
jobhunter run --auto                 # Skip interactive selection, apply to all
jobhunter run --time 24h|week|month  # Date filter for LinkedIn searches
jobhunter --test email@test.com      # Test mode (sends to your email, not recruiters)
jobhunter optimize                   # AI-powered search query optimization
jobhunter optimize "feedback"        # Optimization with custom context
jobhunter history                    # Application history (--last N, --company, --since, --all)
jobhunter blacklist                  # View/add/remove blocked companies
jobhunter status                     # Config & stats dashboard
jobhunter update                     # Git pull latest version
```

Unit tests: `python -m unittest discover -s tests -p "test_*.py"`. Manual E2E: `jobhunter --test your@email.com`.

## Architecture

**Monolithic CLI** — everything orchestrated from `job.py` (~1400 lines). Entry point is `main()` at the bottom.

### Multi-Agent System (4 Gemini Agents)

1. **Filter Agent** — analyzes scraped LinkedIn posts, determines if they're real job offers relevant to user profile. Filters by language requirements vs user proficiency.
2. **CV Writer Agent** — generates personalized CVs (PDF via ReportLab) adapted to each offer's requirements and language. Cannot invent skills/languages/achievements not in profile.
3. **Email Writer Agent** — creates short, human-sounding application emails (~100 words) with concrete achievements. Receives CV data for coherence.
4. **Optimizer Agent** — analyzes profile + history to suggest better search queries

All agents call Gemini via direct HTTP POST (`call_gemini()` / `call_gemini_vision()`), not SDK. Retry logic with exponential backoff handles 429/5xx errors.

### Pipeline (6 Phases)

1. **Scrape** — `scrape_posts()`: LinkedIn search, scroll, expand text, extract emails
2. **Analyze** — `agent_filter()`: Gemini filters for real, relevant offers
3. **Deduplicate** — normalized title comparison + 30-day cooldown per job+company
4. **Select** — interactive user picks or `--auto`
5. **Generate** — `agent_cv()` + `agent_email()` per selected offer
6. **Send** — SMTP with retries, logs to knowledge.json

### Key Files

- `job.py` — entry point shim (~45 lineas): ensure_deps + delega a jobhunter.cli.main
- `jobhunter/` — paquete modular con toda la logica
  - `constants.py`, `ui.py`, `banner.py`, `config.py`, `storage.py` — hojas
  - `ai/base.py` + `ai/gemini.py` — puerto AIProvider + adaptador Gemini
  - `mailer.py`, `browser.py`, `updater.py`, `scraper.py` — infraestructura
  - `agents/filter.py`, `agents/cv.py`, `agents/email.py`, `agents/optimizer.py` — 4 agentes
  - `pipeline.py` — cmd_run (orquestacion de las 3 fases del run)
  - `cli/main.py` — dispatcher + parse_time_filter
  - `cli/setup.py` + los demas `cli/*.py` — comandos CLI individuales
  - `cv/builder.py` + `cv/templates/` — generacion de CV PDF
  - `offers.py` — deduplicacion, extract_emails, cooldown
- `config.json` — user config (API keys, SMTP credentials, profile, search queries) — **git-ignored**
- `knowledge.json` — execution history and application log — **git-ignored**
- `.session/` — Playwright persistent Chrome session — **git-ignored**
- `output/cvs/` — generated CV PDFs, `output/logs/` — execution logs — **git-ignored**
- `install.sh` / `install.ps1` — platform installers (macOS+Linux / Windows)
- `web/index.html` — GitHub Pages landing page

### Dependencies

Auto-installed by job.py at startup: `rich`, `requests`, `playwright`, `reportlab`.
External: Python 3.10+, Chrome/Edge browser, Git, Gemini API key, Gmail App Password.

## Python Compatibility

**Minimum version: Python 3.10.** Must work on 3.10, 3.11, 3.12, and 3.13.

**CRITICAL: Do NOT use f-strings with nested quotes.** Python 3.10 and 3.11 do not support quotes inside f-string expressions that match the outer quote type. This WILL crash on Ubuntu 22.04 and other systems with Python 3.10.

```python
# WRONG — breaks on Python 3.10:
f"...{l['key']}..."           # single quotes inside single-quoted f-string: OK
f"...{d['a']['b']}..."        # nested dict access: OK
f"""...{l['key']}..."""        # single quotes inside triple-quoted f-string: BREAKS
f"...{f'nested {x}'}..."      # nested f-string: BREAKS
{f"""...""" if cond else ''}   # f-string with triple quotes inside another f-string: BREAKS

# CORRECT — works on all versions:
val = d["key"]                 # pre-compute
f"...{val}..."                 # use variable
"prefix: " + d["key"]         # concatenation
", ".join(x["k"] for x in l)  # generator with concatenation
```

Always test changes with `docker run --rm -v ./job.py:/t.py:ro python:3.10-slim python3 -c "import py_compile; py_compile.compile('/t.py', doraise=True)"` before pushing.

## Language & Localization

All CLI output, prompts, and user-facing text is in **Spanish**. Agent prompts and generated content support ES/EN/PT/FR/DE — auto-detected from offer language.

## CI/CD

- `.github/workflows/deploy.yml` — pushes `web/` to GitHub Pages on changes to `web/` only
- `.github/workflows/release.yml` — on tag push (v*), validates installers, creates GitHub release
