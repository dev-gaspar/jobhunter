# apply + dashboard + sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three commands to the jobhunter CLI: `apply` (apply to a single pasted/linked posting), `dashboard` (local metrics web UI), `sync` (IMAP reconciliation of replies/bounces).

**Architecture:** Extract pipeline Phase 3 into a shared `applying.py` used by both `run` and the new `apply`. Dashboard is a stdlib `http.server` serving one self-contained HTML file plus a JSON endpoint computed by a pure `metrics.py`. Reconciliation is a pure matcher in `inbox.py` fed by two IMAP fetches, persisting statuses into `knowledge.json`.

**Tech Stack:** Python 3.10+ stdlib (imaplib, http.server, webbrowser, email), existing deps only (rich, playwright). No new dependencies.

## Global Constraints

- Repo root: `C:\Users\joseg\.jobhunter`. Run all commands from there.
- Python 3.10 compatible: NO f-strings with nested same-type quotes, NO triple-quoted f-strings, NO nested f-strings (see CLAUDE.md).
- All user-facing CLI text in Spanish, no emojis; use the repo's existing markers (`[green]✓[/green]`, `[red]✗[/red]`, `[yellow]![/yellow]`).
- Tests: `unittest`, run with `python -m unittest discover -s tests -p "test_*.py"`.
- Commits in Spanish, conventional-commit prefixes, on branch `feature/apply-dashboard-sync`.
- Every commit message ends with the Co-Authored-By/Claude-Session trailer used earlier on this branch.
- `knowledge.json` and `config.json` are live user data: tests must NEVER load or write the real files (always patch `load_kb`/`save_kb`/`load_config`).

---

### Task 1: Extract shared per-offer apply logic (`jobhunter/applying.py`)

**Files:**
- Create: `jobhunter/applying.py`
- Modify: `jobhunter/pipeline.py` (Phase 3 loop, lines ~349-501, and imports)
- Test: `tests/test_applying.py`

**Interfaces:**
- Produces: `apply_to_offer(cfg, kb, job, test_email=None, dry_run=False, interactive=True, preview_send_all=False, mode="run", label="") -> dict` with keys `status` (`"sent"|"dry"|"skipped"|"error"`), `record` (dict for results/log), `preview_send_all` (bool). On `"sent"` it appends to `kb["applications"]` a dict with keys `date, job_title, company, recruiter_email, sent_to, mode, post_url, subject`.
- Consumes: existing `agent_cv(cfg, job)`, `agent_email(cfg, job, cv_data=...)`, `generate_cv_pdf(...)`, `get_cv_filename(company, title)`, `send_email(cfg, to, subject, body, cv_path)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_applying.py`:

```python
# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch

from jobhunter.applying import apply_to_offer


def _cfg():
    return {"profile": {"name": "Jose Test"}, "cv_template": "modern"}


def _job():
    return {
        "job_title": "AI Engineer",
        "company": "Acme",
        "contact_email": "hr@acme.com",
        "language": "es",
        "post_url": "https://x.com/p/1",
    }


class ApplyToOfferTests(unittest.TestCase):
    @patch("jobhunter.applying.console")
    @patch("jobhunter.applying.send_email")
    @patch("jobhunter.applying.agent_email", return_value={"subject": "Asunto X", "body": "Cuerpo"})
    @patch("jobhunter.applying.generate_cv_pdf")
    @patch("jobhunter.applying.get_cv_filename", return_value="cv.pdf")
    @patch("jobhunter.applying.agent_cv", return_value={"title": "cv"})
    def test_sent_appends_to_kb_with_subject_and_mode(self, _cv, _fn, _pdf, _em, mock_send, _c):
        kb = {"applications": []}
        res = apply_to_offer(_cfg(), kb, _job(), interactive=False, mode="manual")
        self.assertEqual(res["status"], "sent")
        mock_send.assert_called_once()
        self.assertEqual(len(kb["applications"]), 1)
        app = kb["applications"][0]
        self.assertEqual(app["mode"], "manual")
        self.assertEqual(app["subject"], "Asunto X")
        self.assertEqual(app["recruiter_email"], "hr@acme.com")
        self.assertEqual(app["sent_to"], "hr@acme.com")

    @patch("jobhunter.applying.console")
    @patch("jobhunter.applying.send_email")
    @patch("jobhunter.applying.agent_email", return_value={"subject": "S", "body": "B"})
    @patch("jobhunter.applying.generate_cv_pdf")
    @patch("jobhunter.applying.get_cv_filename", return_value="cv.pdf")
    @patch("jobhunter.applying.agent_cv", return_value={})
    def test_dry_run_does_not_send_nor_persist(self, _cv, _fn, _pdf, _em, mock_send, _c):
        kb = {"applications": []}
        res = apply_to_offer(_cfg(), kb, _job(), dry_run=True, interactive=False)
        self.assertEqual(res["status"], "dry")
        mock_send.assert_not_called()
        self.assertEqual(kb["applications"], [])
        self.assertTrue(res["record"].get("dry_run"))

    @patch("jobhunter.applying.console")
    @patch("jobhunter.applying.time.sleep")
    @patch("jobhunter.applying.agent_cv", side_effect=RuntimeError("boom"))
    def test_generation_error_returns_error(self, _cv, _sleep, _c):
        kb = {"applications": []}
        res = apply_to_offer(_cfg(), kb, _job(), interactive=False)
        self.assertEqual(res["status"], "error")
        self.assertEqual(kb["applications"], [])

    @patch("jobhunter.applying.console")
    @patch("jobhunter.applying.send_email")
    @patch("jobhunter.applying.agent_email", return_value={"subject": "S", "body": "B"})
    @patch("jobhunter.applying.generate_cv_pdf")
    @patch("jobhunter.applying.get_cv_filename", return_value="cv.pdf")
    @patch("jobhunter.applying.agent_cv", return_value={})
    def test_test_email_overrides_recipient(self, _cv, _fn, _pdf, _em, mock_send, _c):
        kb = {"applications": []}
        res = apply_to_offer(_cfg(), kb, _job(), test_email="yo@test.com", interactive=False, mode="test")
        self.assertEqual(res["status"], "sent")
        args = mock_send.call_args.args
        self.assertEqual(args[1], "yo@test.com")
        self.assertEqual(kb["applications"][0]["sent_to"], "yo@test.com")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_applying -v`
Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'jobhunter.applying'`

- [ ] **Step 3: Create `jobhunter/applying.py`**

The bodies below are moved verbatim from `pipeline.py` Phase 3 (keep behavior identical; only the kb entry gains `"subject"`):

```python
# -*- coding: utf-8 -*-
"""Aplicacion por oferta: genera CV + email, muestra preview y envia.

Extraido de pipeline fase 3; lo comparten cmd_run y el comando apply.
"""
import os
import time
from datetime import datetime

from rich.panel import Panel
from rich.prompt import Prompt

from jobhunter.agents.cv import agent_cv
from jobhunter.agents.email import agent_email
from jobhunter.constants import BASE_DIR
from jobhunter.cv.builder import generate_cv_pdf, get_cv_filename
from jobhunter.mailer import send_email
from jobhunter.ui import console


def apply_to_offer(cfg, kb, job, test_email=None, dry_run=False,
                   interactive=True, preview_send_all=False, mode="run",
                   label=""):
    """Procesa una oferta: CV + email + preview + envio + registro en kb.

    Retorna {"status": "sent"|"dry"|"skipped"|"error", "record": dict,
    "preview_send_all": bool}.
    """
    title = (job.get("job_title") or "Posicion")[:80]
    company = (job.get("company") or "Empresa")[:40]
    rec_email = job.get("contact_email")
    to = test_email or rec_email
    if not label:
        label = f"  [cyan]1[/cyan][dim]/1[/dim] {title} [dim]→[/dim] {company}"

    record = {
        "job_title": title,
        "company": company,
        "recruiter_email": rec_email,
        "sent_to": to,
        "cv_path": None,
    }

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
                except Exception:
                    if retry == 2:
                        raise
                    time.sleep(5)
            record["cv_path"] = cv_path

            status.update(f"{label}  [dim]Email...[/dim]")
            for retry in range(3):
                try:
                    edata = agent_email(cfg, job, cv_data=cv_data)
                    break
                except Exception:
                    if retry == 2:
                        raise
                    time.sleep(5)
    except Exception as e:
        console.print(f"{label}  [red]! {e}[/red]")
        return {"status": "error", "record": record, "preview_send_all": preview_send_all}

    body = edata["body"]
    if test_email:
        body = f"--- RECLUTADOR: {job.get('contact_name','?')} | EMAIL: {rec_email or '?'} | {company} ---\n\n" + body

    cv_name = os.path.basename(cv_path) if cv_path else ""

    if dry_run:
        preview_text = (
            f"Para: {to}\n"
            f"Asunto: {edata['subject']}\n"
            f"CV adjunto: {cv_name or '—'}\n\n"
            f"{body}"
        )
        console.print(Panel(preview_text, border_style="dim", title="[dim]Dry run[/dim]"))
        console.print("       [yellow]·[/yellow] Dry-run: no se envia email (no se guarda en historial)")
        record["dry_run"] = True
        return {"status": "dry", "record": record, "preview_send_all": preview_send_all}

    do_send = False
    if not interactive or preview_send_all:
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
        record["skipped"] = True
        return {"status": "skipped", "record": record, "preview_send_all": preview_send_all}

    try:
        send_email(cfg, to, edata["subject"], body, cv_path)
        console.print(f"{label}  [green]> Enviado[/green] [dim]→ {to}[/dim]")
        kb["applications"].append({
            "date": datetime.now().isoformat(),
            "job_title": title,
            "company": company,
            "recruiter_email": rec_email,
            "sent_to": to,
            "mode": mode,
            "post_url": job.get("post_url"),
            "subject": edata["subject"],
        })
        return {"status": "sent", "record": record, "preview_send_all": preview_send_all}
    except Exception as e:
        console.print(f"{label}  [red]! {e}[/red]")
        return {"status": "error", "record": record, "preview_send_all": preview_send_all}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_applying -v`
Expected: 4 tests PASS

- [ ] **Step 5: Rewire `pipeline.py` Phase 3 to use it**

In `jobhunter/pipeline.py`:

1. Imports: REMOVE `from jobhunter.cv.builder import generate_cv_pdf, get_cv_filename`, `from jobhunter.agents.cv import agent_cv`, `from jobhunter.agents.email import agent_email`, `from jobhunter.mailer import send_email`. ADD `from jobhunter.applying import apply_to_offer`.
2. Replace the whole per-offer body of the `for i, job in enumerate(offers, 1):` loop (from `title = (job.get("job_title")...` down to and including the final `time.sleep(2)` before `run_entry = {`) with:

```python
    for i, job in enumerate(offers, 1):
        title = (job.get("job_title") or "Posicion")[:80]
        company = (job.get("company") or "Empresa")[:40]
        label = f"  [cyan]{i}[/cyan][dim]/{total}[/dim] {title} [dim]→[/dim] {company}"

        res = apply_to_offer(
            cfg, kb, job,
            test_email=test_email,
            dry_run=dry_run,
            interactive=not auto_apply,
            preview_send_all=preview_send_all,
            mode=mode,
            label=label,
        )
        preview_send_all = res["preview_send_all"]
        results.append(res["record"])
        if res["status"] == "sent":
            sent += 1
        elif res["status"] == "dry":
            generated += 1
        elif res["status"] == "error":
            errors += 1
        if res["status"] in ("dry", "skipped"):
            console.print()
        time.sleep(1 if res["status"] == "skipped" else 2)
```

- [ ] **Step 6: Run the FULL suite to verify no regression**

Run: `python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -5`
Expected: all tests PASS (same count as before plus the 4 new ones)

- [ ] **Step 7: Commit**

```bash
git add jobhunter/applying.py jobhunter/pipeline.py tests/test_applying.py
git commit -m "refactor(applying): extraer fase 3 por oferta a modulo compartido"
```

---

### Task 2: `jobhunter apply` — text flow, paste mode, dispatcher

**Files:**
- Create: `jobhunter/cli/apply.py`
- Modify: `jobhunter/cli/main.py` (dispatcher), `jobhunter/cli/help.py`
- Test: `tests/test_cli_apply.py`

**Interfaces:**
- Produces: `cmd_apply(arg=None, test_email=None, dry_run=False)`, `is_url(arg) -> bool`, `read_pasted_text() -> str`.
- Consumes: `apply_to_offer` (Task 1 signature), `agent_filter(cfg, text)`, `extract_emails(text)`, `was_already_applied(applications, company, job_title)`. Link scraping (`scrape_single_post`) arrives in Task 3 — the import is done lazily inside `cmd_apply`, so Task 2 works for text before Task 3 exists.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_apply.py`:

```python
# -*- coding: utf-8 -*-
import io
import unittest
from unittest.mock import MagicMock, patch

from jobhunter.cli.apply import cmd_apply, is_url, read_pasted_text

POST = "x" * 30 + " Buscamos dev. Enviar CV a maria@simon.com con asunto Vacante. " + "y" * 30


def _cfg():
    return {"profile": {"name": "J"}}


class IsUrlTests(unittest.TestCase):
    def test_detects_links(self):
        self.assertTrue(is_url("https://lnkd.in/p/ddTxabDW"))
        self.assertTrue(is_url("http://linkedin.com/posts/x"))
        self.assertTrue(is_url("  https://x.com  "))

    def test_rejects_text(self):
        self.assertFalse(is_url("Buscamos desarrollador enviar CV"))
        self.assertFalse(is_url(""))
        self.assertFalse(is_url(None))


class ReadPastedTextTests(unittest.TestCase):
    @patch("jobhunter.cli.apply.console")
    @patch("jobhunter.cli.apply.sys.stdin", io.StringIO("hola\nmundo\n.\nignorado\n"))
    def test_stops_at_dot_sentinel(self, _c):
        self.assertEqual(read_pasted_text(), "hola\nmundo")

    @patch("jobhunter.cli.apply.console")
    @patch("jobhunter.cli.apply.sys.stdin", io.StringIO("solo una linea\n"))
    def test_eof_without_sentinel(self, _c):
        self.assertEqual(read_pasted_text(), "solo una linea")


class CmdApplyTests(unittest.TestCase):
    @patch("jobhunter.cli.apply.console")
    @patch("jobhunter.cli.apply.save_kb")
    @patch("jobhunter.cli.apply.apply_to_offer", return_value={"status": "sent", "record": {}, "preview_send_all": False})
    @patch("jobhunter.cli.apply.agent_filter")
    @patch("jobhunter.cli.apply.load_kb", return_value={"applications": []})
    @patch("jobhunter.cli.apply.load_config", return_value=_cfg())
    @patch("jobhunter.cli.apply.is_configured", return_value=True)
    def test_text_flow_calls_apply_with_manual_mode(self, _ic, _lc, _lk, mock_filter, mock_apply, mock_save, _c):
        mock_filter.return_value = {
            "is_job": True, "is_relevant": True, "job_title": "Dev II",
            "company": "Simon", "contact_email": "maria@simon.com",
        }
        cmd_apply(POST)
        mock_apply.assert_called_once()
        self.assertEqual(mock_apply.call_args.kwargs.get("mode"), "manual")
        mock_save.assert_called_once()

    @patch("jobhunter.cli.apply.console")
    @patch("jobhunter.cli.apply.Confirm")
    @patch("jobhunter.cli.apply.apply_to_offer")
    @patch("jobhunter.cli.apply.agent_filter")
    @patch("jobhunter.cli.apply.load_kb", return_value={"applications": []})
    @patch("jobhunter.cli.apply.load_config", return_value=_cfg())
    @patch("jobhunter.cli.apply.is_configured", return_value=True)
    def test_not_relevant_and_user_declines(self, _ic, _lc, _lk, mock_filter, mock_apply, mock_confirm, _c):
        mock_filter.return_value = {
            "is_job": True, "is_relevant": False, "relevance_reason": "no encaja",
            "job_title": "X", "company": "Y", "contact_email": "a@b.com",
        }
        mock_confirm.ask.return_value = False
        cmd_apply(POST)
        mock_apply.assert_not_called()

    @patch("jobhunter.cli.apply.console")
    @patch("jobhunter.cli.apply.Prompt")
    @patch("jobhunter.cli.apply.save_kb")
    @patch("jobhunter.cli.apply.apply_to_offer", return_value={"status": "sent", "record": {}, "preview_send_all": False})
    @patch("jobhunter.cli.apply.agent_filter")
    @patch("jobhunter.cli.apply.load_kb", return_value={"applications": []})
    @patch("jobhunter.cli.apply.load_config", return_value=_cfg())
    @patch("jobhunter.cli.apply.is_configured", return_value=True)
    def test_missing_email_prompts_with_extracted_default(self, _ic, _lc, _lk, mock_filter, mock_apply, _save, mock_prompt, _c):
        mock_filter.return_value = {
            "is_job": True, "is_relevant": True, "job_title": "Dev",
            "company": "Simon", "contact_email": None,
        }
        mock_prompt.ask.return_value = "maria@simon.com"
        cmd_apply(POST)
        self.assertEqual(mock_prompt.ask.call_args_list[0].kwargs.get("default"), "maria@simon.com")
        job_sent = mock_apply.call_args.args[2]
        self.assertEqual(job_sent["contact_email"], "maria@simon.com")

    @patch("jobhunter.cli.apply.console")
    @patch("jobhunter.cli.apply.load_kb", return_value={"applications": []})
    @patch("jobhunter.cli.apply.load_config", return_value=_cfg())
    @patch("jobhunter.cli.apply.is_configured", return_value=True)
    def test_short_text_aborts(self, _ic, _lc, _lk, mock_console):
        cmd_apply("muy corto")
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("demasiado corto", printed)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli_apply -v`
Expected: ERROR `ModuleNotFoundError: No module named 'jobhunter.cli.apply'`

- [ ] **Step 3: Create `jobhunter/cli/apply.py`**

```python
# -*- coding: utf-8 -*-
"""Comando apply: aplica a una publicacion puntual (link o texto pegado)."""
import re
import sys

from rich.prompt import Confirm, Prompt

from jobhunter.agents.filter import agent_filter
from jobhunter.applying import apply_to_offer
from jobhunter.banner import get_banner
from jobhunter.config import is_configured, load_config
from jobhunter.offers import extract_emails, was_already_applied
from jobhunter.storage import load_kb, save_kb
from jobhunter.ui import console

URL_RE = re.compile(r"^https?://", re.IGNORECASE)
BAD_EMAIL_VALUES = ("null", "none", "n/a", "no encontrado")


def is_url(arg):
    return bool(URL_RE.match((arg or "").strip()))


def read_pasted_text():
    """Lee texto multilinea de stdin hasta una linea con solo '.' o EOF."""
    console.print(
        "  [bold]Pega el texto de la publicacion.[/bold] "
        "[dim]Termina con una linea que contenga solo un punto (.) — o Ctrl+Z y Enter[/dim]"
    )
    lines = []
    try:
        for line in sys.stdin:
            if line.strip() == ".":
                break
            lines.append(line.rstrip("\n"))
    except KeyboardInterrupt:
        return ""
    return "\n".join(lines).strip()


def cmd_apply(arg=None, test_email=None, dry_run=False):
    cfg = load_config()
    kb = load_kb()
    if not is_configured():
        console.print("  [red]✗[/red] Falta configuracion. Ejecuta: [cyan]jobhunter setup[/cyan]")
        return

    console.print(get_banner())

    post_url = None
    if arg and is_url(arg):
        post_url = arg.strip()
        console.print("  [bold dim]Abriendo publicacion...[/bold dim]")
        from jobhunter.scraper import scrape_single_post
        text = scrape_single_post(post_url)
        if not text:
            return
    elif arg:
        text = arg.strip()
    else:
        text = read_pasted_text()

    if not text or len(text) < 50:
        console.print("  [red]✗[/red] Texto demasiado corto (minimo 50 caracteres).")
        return

    console.print("  [bold dim]Analizando publicacion...[/bold dim]")
    with console.status("  [dim]Analizando...[/dim]"):
        a = agent_filter(cfg, text)

    title = (a.get("job_title") or "").strip()
    company = (a.get("company") or "").strip()
    reason = (a.get("relevance_reason") or "").strip()

    if a.get("is_job") and a.get("is_relevant", True):
        console.print(f"  [green]✓[/green] {company or '-'} [dim]—[/dim] {title or '-'}")
    else:
        head = reason[:120] or "el filtro no la marco como oferta relevante"
        console.print(f"  [yellow]![/yellow] {head}")
        if not Confirm.ask("  Aplicar de todas formas?", default=True):
            console.print("  [dim]Cancelado.[/dim]")
            return

    email = a.get("contact_email")
    if email and email.lower() in BAD_EMAIL_VALUES:
        email = None
    if not email:
        found = extract_emails(text)
        default = found[0] if found else None
        email = (Prompt.ask("  Email del reclutador", default=default) or "").strip()
        if not email or "@" not in email:
            console.print("  [red]✗[/red] Sin email de contacto. Cancelado.")
            return
    a["contact_email"] = email

    if not title:
        title = Prompt.ask("  Titulo del puesto", default="Software Developer")
    if not company:
        company = Prompt.ask("  Empresa", default="Empresa")
    a["job_title"] = title
    a["company"] = company
    a["post_url"] = post_url

    if was_already_applied(kb.get("applications", []), company, title):
        console.print("  [yellow]![/yellow] Ya aplicaste a esta oferta en los ultimos 30 dias.")
        if not Confirm.ask("  Aplicar de nuevo?", default=False):
            console.print("  [dim]Cancelado.[/dim]")
            return

    console.print()
    res = apply_to_offer(
        cfg, kb, a,
        test_email=test_email,
        dry_run=dry_run,
        interactive=True,
        mode="manual",
    )
    if res["status"] == "sent":
        save_kb(kb)
        console.print()
        console.print("  [green]✓[/green] Aplicacion enviada y guardada en historial")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cli_apply -v`
Expected: 8 tests PASS

- [ ] **Step 5: Wire dispatcher and help**

In `jobhunter/cli/main.py`:
- Add import: `from jobhunter.cli.apply import cmd_apply`
- Add branch BEFORE the final `else:` (order between other `elif`s does not matter):

```python
    elif cmd in ("apply",):
        arg = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
        apply_test = None
        for i, a in enumerate(sys.argv):
            if a == "--test" and i + 1 < len(sys.argv):
                apply_test = sys.argv[i + 1]
        cmd_apply(arg, test_email=apply_test, dry_run=dry)
```

In `jobhunter/cli/help.py`, after the `jobhunter optimize "..."` row add:

```python
    cmds.add_row("jobhunter apply [link|texto]", "Aplicar a una publicacion puntual")
```

and in the examples section at the bottom add:

```python
    console.print('  [dim]$ jobhunter apply https://lnkd.in/p/xxxx[/dim]')
    console.print("  [dim]$ jobhunter apply            (luego pega el texto y termina con '.')[/dim]")
```

- [ ] **Step 6: Run full suite**

Run: `python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -3`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add jobhunter/cli/apply.py jobhunter/cli/main.py jobhunter/cli/help.py tests/test_cli_apply.py
git commit -m "feat(apply): comando apply para publicacion puntual (texto/pegado)"
```

---

### Task 3: Link scraping for `apply` (`scrape_single_post`)

**Files:**
- Modify: `jobhunter/scraper.py`
- Test: `tests/test_scraper.py` (append new test class)

**Interfaces:**
- Produces: `scrape_single_post(url) -> str|None` (prints its own errors) and `extract_post_text(page) -> str` (pure-ish, testable with a fake page).
- Consumes: existing `SESSION_DIR`, `find_chrome`, `kill_playwright_zombies`, `console` already imported in `scraper.py`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scraper.py`:

```python
class FakeEl:
    def __init__(self, text):
        self._text = text

    def inner_text(self):
        return self._text

    def click(self):
        pass


class FakePage:
    def __init__(self, mapping, main_text=""):
        self.mapping = mapping
        self.main_text = main_text

    def query_selector(self, sel):
        return self.mapping.get(sel)

    def wait_for_timeout(self, ms):
        pass

    def inner_text(self, sel):
        return self.main_text


class ExtractPostTextTests(unittest.TestCase):
    def test_prefers_expandable_text_box(self):
        from jobhunter.scraper import extract_post_text
        page = FakePage({'span[data-testid="expandable-text-box"]': FakeEl("Oferta de trabajo " + "x" * 60)})
        self.assertTrue(extract_post_text(page).startswith("Oferta de trabajo"))

    def test_falls_back_to_article(self):
        from jobhunter.scraper import extract_post_text
        page = FakePage({"article": FakeEl("Texto del articulo " + "y" * 60)})
        self.assertTrue(extract_post_text(page).startswith("Texto del articulo"))

    def test_last_resort_main_text(self):
        from jobhunter.scraper import extract_post_text
        page = FakePage({}, main_text="Contenido main de respaldo " + "z" * 60)
        self.assertIn("Contenido main", extract_post_text(page))

    def test_short_candidates_are_skipped(self):
        from jobhunter.scraper import extract_post_text
        page = FakePage(
            {'span[data-testid="expandable-text-box"]': FakeEl("corto")},
            main_text="Respaldo largo " + "w" * 60,
        )
        self.assertIn("Respaldo largo", extract_post_text(page))
```

(Reuse the existing `import unittest` at the top of the file; add these classes at the end before the `if __name__` block.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_scraper -v`
Expected: new tests ERROR with `ImportError: cannot import name 'extract_post_text'`

- [ ] **Step 3: Implement in `jobhunter/scraper.py`**

Append at the end of the file:

```python
def extract_post_text(page):
    """Extrae el texto principal de una publicacion con selectores en cascada."""
    try:
        btn = page.query_selector("button.feed-shared-inline-show-more-text__see-more-less-toggle")
        if btn:
            btn.click()
            page.wait_for_timeout(500)
    except Exception:
        pass
    selectors = [
        'span[data-testid="expandable-text-box"]',
        "div.feed-shared-update-v2__description",
        "article",
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                text = (el.inner_text() or "").strip()
                if len(text) >= 50:
                    return text
        except Exception:
            continue
    try:
        return (page.inner_text("main") or "").strip()[:6000]
    except Exception:
        return ""


def scrape_single_post(url):
    """Abre una publicacion individual con la sesion persistente y extrae su texto.

    Retorna el texto, o None si fallo (ya imprime la causa).
    """
    if not os.path.exists(SESSION_DIR):
        console.print("  [red]✗[/red] Sin sesion LinkedIn. Ejecuta: [cyan]jobhunter login[/cyan]")
        return None
    kill_playwright_zombies()
    try:
        with sync_playwright() as p:
            chrome = find_chrome()
            browser = p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR, headless=True,
                viewport={"width": 1300, "height": 850}, executable_path=chrome,
            )
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
            if "login" in page.url or "signin" in page.url or "authwall" in page.url:
                console.print("  [red]![/red] Sesion expirada. Ejecuta: [cyan]jobhunter login[/cyan]")
                browser.close()
                return None
            text = extract_post_text(page)
            browser.close()
            if not text:
                console.print("  [red]✗[/red] No se pudo extraer texto de la publicacion. Copia el texto y usa: [cyan]jobhunter apply[/cyan]")
                return None
            return text
    except Exception as e:
        console.print(f"  [red]✗[/red] No se pudo abrir la publicacion: {e}")
        return None
```

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_scraper -v`
Expected: all PASS

- [ ] **Step 5: Manual smoke (optional, requires session)**

Run: `python job.py apply https://lnkd.in/p/ddTxabDW --dry`
Expected: opens headless Chrome, extracts text, filter runs, CV/email generated, "Dry run" panel, nothing sent. If no LinkedIn session, expect the "Sin sesion" message.

- [ ] **Step 6: Commit**

```bash
git add jobhunter/scraper.py tests/test_scraper.py
git commit -m "feat(apply): scraping de publicacion individual (lnkd.in/linkedin)"
```

---

### Task 4: Metrics aggregation (`jobhunter/metrics.py`)

**Files:**
- Create: `jobhunter/metrics.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Produces: `build_dashboard_data(kb, now=None) -> dict` with keys `totals` (dict: sent, replied, bounced, no_reply, unknown), `reply_rate` (float %), `bounce_rate` (float %), `weeks` (list of `{"week": "2026-W31", "sent": n}`, 12 items, oldest first), `runs` (list of `{"date","mode","posts","offers","sent"}`), `applications` (list of `{"date","job_title","company","sent_to","status","days_since_sent","reply_date"}` newest first), `generated_at` (iso str). Also `app_status(app) -> str`.
- Consumes: nothing from other tasks (pure; reads a kb dict).

**Status semantics (used by sync in Task 6 too):** an application whose `sent_to != recruiter_email` (or `mode == "test"`) is a test send -> status `"test"`, excluded from all metrics. Otherwise the persisted `status` field applies, defaulting to `"unknown"` when absent.

- [ ] **Step 1: Write the failing test**

Create `tests/test_metrics.py`:

```python
# -*- coding: utf-8 -*-
import unittest
from datetime import datetime

from jobhunter.metrics import app_status, build_dashboard_data

NOW = datetime(2026, 8, 5, 12, 0, 0)


def _kb():
    return {
        "runs": [
            {"date": "2026-08-01T10:00:00", "mode": "run", "posts": 100, "offers": 5, "sent": 3},
        ],
        "applications": [
            {"date": "2026-08-01T10:00:00", "job_title": "A", "company": "C1",
             "recruiter_email": "r1@x.com", "sent_to": "r1@x.com", "mode": "run",
             "status": "replied", "reply_date": "2026-08-02T09:00:00"},
            {"date": "2026-08-01T11:00:00", "job_title": "B", "company": "C2",
             "recruiter_email": "r2@x.com", "sent_to": "r2@x.com", "mode": "run",
             "status": "bounced"},
            {"date": "2026-08-02T10:00:00", "job_title": "C", "company": "C3",
             "recruiter_email": "r3@x.com", "sent_to": "r3@x.com", "mode": "run",
             "status": "no_reply"},
            {"date": "2026-08-03T10:00:00", "job_title": "D", "company": "C4",
             "recruiter_email": "r4@x.com", "sent_to": "r4@x.com", "mode": "run"},
            {"date": "2026-08-03T11:00:00", "job_title": "E", "company": "C5",
             "recruiter_email": "r5@x.com", "sent_to": "yo@gmail.com", "mode": "test"},
        ],
    }


class AppStatusTests(unittest.TestCase):
    def test_test_send_detected_by_recipient_mismatch(self):
        self.assertEqual(app_status({"recruiter_email": "a@b.com", "sent_to": "me@x.com"}), "test")

    def test_defaults_to_unknown(self):
        self.assertEqual(app_status({"recruiter_email": "a@b.com", "sent_to": "a@b.com"}), "unknown")

    def test_persisted_status_wins(self):
        self.assertEqual(app_status({"recruiter_email": "a@b.com", "sent_to": "a@b.com", "status": "replied"}), "replied")


class BuildDashboardDataTests(unittest.TestCase):
    def test_totals_exclude_test_sends(self):
        d = build_dashboard_data(_kb(), now=NOW)
        self.assertEqual(d["totals"], {"sent": 4, "replied": 1, "bounced": 1, "no_reply": 1, "unknown": 1})

    def test_rates(self):
        d = build_dashboard_data(_kb(), now=NOW)
        self.assertEqual(d["reply_rate"], 33.3)   # 1 replied / 3 delivered (4 sent - 1 bounce)
        self.assertEqual(d["bounce_rate"], 25.0)  # 1 / 4

    def test_weeks_are_12_and_count_sends(self):
        d = build_dashboard_data(_kb(), now=NOW)
        self.assertEqual(len(d["weeks"]), 12)
        this_week = [w for w in d["weeks"] if w["week"] == "2026-W32"]
        self.assertEqual(this_week[0]["sent"], 1)  # solo D (Aug 3, ISO W32); E es test y se excluye
        prev_week = [w for w in d["weeks"] if w["week"] == "2026-W31"]
        self.assertEqual(prev_week[0]["sent"], 3)  # A y B (Aug 1) + C (Aug 2, domingo, aun W31)

    def test_applications_newest_first_with_days(self):
        d = build_dashboard_data(_kb(), now=NOW)
        self.assertEqual(len(d["applications"]), 4)
        self.assertEqual(d["applications"][0]["job_title"], "D")
        self.assertEqual(d["applications"][0]["days_since_sent"], 2)
        self.assertEqual(d["applications"][0]["status"], "unknown")

    def test_runs_passthrough(self):
        d = build_dashboard_data(_kb(), now=NOW)
        self.assertEqual(d["runs"][0]["posts"], 100)

    def test_empty_kb(self):
        d = build_dashboard_data({"runs": [], "applications": []}, now=NOW)
        self.assertEqual(d["totals"]["sent"], 0)
        self.assertEqual(d["reply_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
```

Note: 2026-08-01 (Saturday) is ISO week 2026-W31; 2026-08-03 (Monday) is 2026-W32. The `%G-W%V` format gives ISO year-week.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_metrics -v`
Expected: `ModuleNotFoundError: No module named 'jobhunter.metrics'`

- [ ] **Step 3: Create `jobhunter/metrics.py`**

```python
# -*- coding: utf-8 -*-
"""Agregados de historial para el dashboard local (funciones puras sobre kb)."""
from datetime import datetime, timedelta


def app_status(app):
    """Estado efectivo de una aplicacion: test / replied / bounced / no_reply / unknown."""
    rec = app.get("recruiter_email")
    if app.get("mode") == "test":
        return "test"
    if rec and app.get("sent_to") and app["sent_to"] != rec:
        return "test"
    return app.get("status") or "unknown"


def _parse_date(value):
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def build_dashboard_data(kb, now=None):
    """Calcula totales, tasas, series semanales y listado para /api/data."""
    now = now or datetime.now()
    counts = {"sent": 0, "replied": 0, "bounced": 0, "no_reply": 0, "unknown": 0}
    week_counts = {}
    rows = []

    for app in kb.get("applications", []):
        st = app_status(app)
        if st == "test":
            continue
        counts["sent"] += 1
        bucket = st if st in ("replied", "bounced", "no_reply") else "unknown"
        counts[bucket] += 1

        d = _parse_date(app.get("date") or "")
        days = (now - d).days if d else None
        if d:
            week_counts[d.strftime("%G-W%V")] = week_counts.get(d.strftime("%G-W%V"), 0) + 1

        rows.append({
            "date": app.get("date"),
            "job_title": app.get("job_title"),
            "company": app.get("company"),
            "sent_to": app.get("sent_to"),
            "status": st,
            "days_since_sent": days,
            "reply_date": app.get("reply_date"),
        })

    rows.sort(key=lambda r: r.get("date") or "", reverse=True)

    delivered = counts["sent"] - counts["bounced"]
    reply_rate = round(counts["replied"] * 100.0 / delivered, 1) if delivered else 0.0
    bounce_rate = round(counts["bounced"] * 100.0 / counts["sent"], 1) if counts["sent"] else 0.0

    week_keys = []
    cursor = now
    for _ in range(12):
        week_keys.append(cursor.strftime("%G-W%V"))
        cursor = cursor - timedelta(days=7)
    week_keys.reverse()
    weeks = [{"week": k, "sent": week_counts.get(k, 0)} for k in week_keys]

    runs = [
        {"date": r.get("date"), "mode": r.get("mode"), "posts": r.get("posts", 0),
         "offers": r.get("offers", 0), "sent": r.get("sent", 0)}
        for r in kb.get("runs", [])
    ]

    return {
        "totals": counts,
        "reply_rate": reply_rate,
        "bounce_rate": bounce_rate,
        "weeks": weeks,
        "runs": runs,
        "applications": rows,
        "generated_at": now.isoformat(),
    }
```

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_metrics -v`
Expected: 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add jobhunter/metrics.py tests/test_metrics.py
git commit -m "feat(metrics): agregados de historial para el dashboard"
```

---

### Task 5: `jobhunter dashboard` — asset + server + dispatcher

**Files:**
- Create: `jobhunter/assets/dashboard.html`, `jobhunter/assets/__init__.py` (empty, keeps the dir in installs), `jobhunter/cli/dashboard.py`
- Modify: `jobhunter/cli/main.py`, `jobhunter/cli/help.py`
- Test: `tests/test_cli_dashboard.py`

**Interfaces:**
- Produces: `cmd_dashboard(port=4090)`; HTTP `GET /` (HTML), `GET /api/data` (JSON from `build_dashboard_data(load_kb())`).
- Consumes: `build_dashboard_data` (Task 4), `load_kb`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_dashboard.py`:

```python
# -*- coding: utf-8 -*-
import json
import threading
import unittest
import urllib.request
from unittest.mock import patch

from jobhunter.cli.dashboard import DashboardHandler
from http.server import ThreadingHTTPServer


class DashboardHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path):
        url = "http://127.0.0.1:" + str(self.port) + path
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read()

    @patch("jobhunter.cli.dashboard.load_kb", return_value={"runs": [], "applications": []})
    def test_api_data_returns_json(self, _kb):
        status, body = self._get("/api/data")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("totals", data)
        self.assertIn("applications", data)
        self.assertIn("weeks", data)

    def test_index_serves_html(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"JobHunter", body)

    def test_unknown_path_404(self):
        try:
            status, _ = self._get("/nope")
        except urllib.error.HTTPError as e:
            status = e.code
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
```

(Add `import urllib.error` at top with the other imports.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli_dashboard -v`
Expected: `ModuleNotFoundError: No module named 'jobhunter.cli.dashboard'`

- [ ] **Step 3: Create `jobhunter/assets/__init__.py`** (empty file) **and `jobhunter/assets/dashboard.html`**

Full content of `dashboard.html` (self-contained, dark, no emojis, no external requests):

```html
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JobHunter — Dashboard</title>
<style>
  :root {
    --bg: #121214; --card: #1b1b1f; --border: #2a2a30;
    --text: #e4e4e7; --dim: #8b8b93; --teal: #2dd4bf; --teal-dark: #0d9488;
    --green: #4ade80; --red: #f87171; --yellow: #facc15;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg); color: var(--text);
    font: 14px/1.5 "Segoe UI", system-ui, sans-serif;
    padding: 2rem 1rem; max-width: 1080px; margin: 0 auto;
  }
  h1 { font-size: 1.4rem; letter-spacing: .02em; }
  h1 span { color: var(--teal); }
  .sub { color: var(--dim); font-size: .8rem; margin-bottom: 1.6rem; }
  h2 { font-size: .95rem; color: var(--dim); text-transform: uppercase;
       letter-spacing: .08em; margin: 2rem 0 .8rem; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: .8rem; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1rem 1.2rem; }
  .card .num { font-size: 1.9rem; font-weight: 600; }
  .card .lbl { color: var(--dim); font-size: .78rem; margin-top: .15rem; }
  .card .rate { font-size: .78rem; margin-top: .3rem; }
  .bars { display: flex; align-items: flex-end; gap: 6px; height: 120px;
          background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1rem; }
  .bar { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; gap: 4px; height: 100%; }
  .bar .fill { width: 100%; background: linear-gradient(180deg, var(--teal), var(--teal-dark));
               border-radius: 3px 3px 0 0; min-height: 2px; }
  .bar .wk { color: var(--dim); font-size: .6rem; white-space: nowrap; }
  .bar .n { color: var(--text); font-size: .68rem; }
  table { width: 100%; border-collapse: collapse; background: var(--card);
          border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
  th, td { text-align: left; padding: .55rem .8rem; font-size: .8rem; }
  th { color: var(--dim); font-weight: 500; border-bottom: 1px solid var(--border);
       text-transform: uppercase; font-size: .68rem; letter-spacing: .06em; }
  tr + tr td { border-top: 1px solid var(--border); }
  td.dim { color: var(--dim); }
  .pill { display: inline-block; padding: .1rem .55rem; border-radius: 999px;
          font-size: .68rem; border: 1px solid; }
  .st-replied  { color: var(--green);  border-color: var(--green); }
  .st-bounced  { color: var(--red);    border-color: var(--red); }
  .st-no_reply { color: var(--yellow); border-color: var(--yellow); }
  .st-unknown  { color: var(--dim);    border-color: var(--border); }
  input[type="search"] {
    width: 100%; max-width: 340px; background: var(--card); border: 1px solid var(--border);
    color: var(--text); border-radius: 8px; padding: .45rem .8rem; margin-bottom: .8rem;
    font: inherit; outline: none;
  }
  input[type="search"]:focus { border-color: var(--teal-dark); }
  .empty { color: var(--dim); padding: 1rem; }
  .tablewrap { overflow-x: auto; }
</style>
</head>
<body>
  <h1>JobHunter <span>— Dashboard</span></h1>
  <div class="sub" id="generated"></div>

  <div class="cards" id="cards"></div>

  <h2>Envios por semana</h2>
  <div class="bars" id="bars"></div>

  <h2>Runs (posts → ofertas → enviados)</h2>
  <div class="tablewrap"><table id="runs"></table></div>

  <h2>Aplicaciones</h2>
  <input type="search" id="q" placeholder="Filtrar por empresa, puesto o email...">
  <div class="tablewrap"><table id="apps"></table></div>

<script>
const STATUS_LABEL = {
  replied: "RESPONDIO", bounced: "REBOTO",
  no_reply: "SIN RESPUESTA", unknown: "SIN CONCILIAR",
};
let APPS = [];

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, c => (
    {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]
  ));
}

function fmtDate(iso) {
  if (!iso) return "";
  return iso.slice(0, 10);
}

function renderCards(d) {
  const t = d.totals;
  document.getElementById("cards").innerHTML = `
    <div class="card"><div class="num">${t.sent}</div><div class="lbl">Enviados</div></div>
    <div class="card"><div class="num" style="color:var(--green)">${t.replied}</div>
      <div class="lbl">Respondidos</div><div class="rate" style="color:var(--green)">${d.reply_rate}% de entregados</div></div>
    <div class="card"><div class="num" style="color:var(--red)">${t.bounced}</div>
      <div class="lbl">Rebotados</div><div class="rate" style="color:var(--red)">${d.bounce_rate}%</div></div>
    <div class="card"><div class="num" style="color:var(--yellow)">${t.no_reply}</div>
      <div class="lbl">Sin respuesta</div></div>
    <div class="card"><div class="num" style="color:var(--dim)">${t.unknown}</div>
      <div class="lbl">Sin conciliar</div><div class="rate" style="color:var(--dim)">ejecuta jobhunter sync</div></div>`;
}

function renderBars(weeks) {
  const max = Math.max(1, ...weeks.map(w => w.sent));
  document.getElementById("bars").innerHTML = weeks.map(w => `
    <div class="bar">
      <div class="n">${w.sent || ""}</div>
      <div class="fill" style="height:${Math.round(w.sent / max * 100)}%"></div>
      <div class="wk">${esc(w.week.slice(5))}</div>
    </div>`).join("");
}

function renderRuns(runs) {
  const rows = runs.slice().reverse().slice(0, 15).map(r => `
    <tr><td class="dim">${fmtDate(r.date)}</td><td class="dim">${esc(r.mode)}</td>
    <td>${r.posts}</td><td>${r.offers}</td><td>${r.sent}</td></tr>`).join("");
  document.getElementById("runs").innerHTML =
    "<tr><th>Fecha</th><th>Modo</th><th>Posts</th><th>Ofertas</th><th>Enviados</th></tr>" +
    (rows || '<tr><td class="empty" colspan="5">Sin runs todavia</td></tr>');
}

function renderApps(filter) {
  const q = (filter || "").toLowerCase();
  const rows = APPS.filter(a =>
    !q || [a.company, a.job_title, a.sent_to].join(" ").toLowerCase().includes(q)
  ).map(a => `
    <tr>
      <td class="dim">${fmtDate(a.date)}</td>
      <td>${esc(a.job_title)}</td>
      <td>${esc(a.company)}</td>
      <td class="dim">${esc(a.sent_to)}</td>
      <td><span class="pill st-${a.status}">${STATUS_LABEL[a.status] || esc(a.status)}</span></td>
      <td class="dim">${a.status === "replied" ? fmtDate(a.reply_date) :
        (a.days_since_sent != null ? a.days_since_sent + " dias" : "")}</td>
    </tr>`).join("");
  document.getElementById("apps").innerHTML =
    "<tr><th>Fecha</th><th>Puesto</th><th>Empresa</th><th>Enviado a</th><th>Estado</th><th>Respuesta / Espera</th></tr>" +
    (rows || '<tr><td class="empty" colspan="6">Sin aplicaciones</td></tr>');
}

fetch("/api/data").then(r => r.json()).then(d => {
  APPS = d.applications;
  document.getElementById("generated").textContent =
    "Generado " + d.generated_at.replace("T", " ").slice(0, 19);
  renderCards(d);
  renderBars(d.weeks);
  renderRuns(d.runs);
  renderApps("");
  document.getElementById("q").addEventListener("input", e => renderApps(e.target.value));
});
</script>
</body>
</html>
```

- [ ] **Step 4: Create `jobhunter/cli/dashboard.py`**

```python
# -*- coding: utf-8 -*-
"""Comando dashboard: servidor local de historial y metricas."""
import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from jobhunter.metrics import build_dashboard_data
from jobhunter.storage import load_kb
from jobhunter.ui import console

ASSET = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "dashboard.html",
)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/data"):
            data = build_dashboard_data(load_kb())
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", payload)
        elif self.path in ("/", "/index.html"):
            with open(ASSET, "rb") as f:
                self._send(200, "text/html; charset=utf-8", f.read())
        else:
            self.send_response(404)
            self.end_headers()

    def _send(self, code, ctype, payload):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        pass


def cmd_dashboard(port=4090):
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    except OSError:
        console.print(f"  [red]✗[/red] Puerto {port} ocupado. Prueba: [cyan]jobhunter dashboard --port {port + 1}[/cyan]")
        return
    url = "http://127.0.0.1:" + str(port) + "/"
    console.print(f"  [green]✓[/green] Dashboard en [cyan]{url}[/cyan]  [dim](Ctrl+C para detener)[/dim]")
    threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n  [dim]Dashboard detenido.[/dim]")
    finally:
        server.server_close()
```

- [ ] **Step 5: Run tests**

Run: `python -m unittest tests.test_cli_dashboard -v`
Expected: 3 tests PASS

- [ ] **Step 6: Wire dispatcher and help**

`jobhunter/cli/main.py`: add import `from jobhunter.cli.dashboard import cmd_dashboard` and branch:

```python
    elif cmd in ("dashboard",):
        port = 4090
        for i, a in enumerate(sys.argv):
            if a == "--port" and i + 1 < len(sys.argv):
                try:
                    port = int(sys.argv[i + 1])
                except ValueError:
                    pass
        cmd_dashboard(port=port)
```

`jobhunter/cli/help.py`: add row after the apply row:

```python
    cmds.add_row("jobhunter dashboard", "Dashboard local de historial y metricas")
```

- [ ] **Step 7: Manual smoke + full suite**

Run: `python job.py dashboard` — browser opens, cards/tables render with real kb (Ctrl+C to stop).
Run: `python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -3`
Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add jobhunter/assets/ jobhunter/cli/dashboard.py jobhunter/cli/main.py jobhunter/cli/help.py tests/test_cli_dashboard.py
git commit -m "feat(dashboard): dashboard local de historial y metricas"
```

---

### Task 6: IMAP inbox + reconciliation logic (`jobhunter/inbox.py`)

**Files:**
- Create: `jobhunter/inbox.py`
- Test: `tests/test_inbox.py`

**Interfaces:**
- Produces:
  - `imap_date(d: datetime) -> str` — `"05-Aug-2026"`, locale-independent.
  - `fetch_inbox(cfg, since: datetime) -> (headers, bounce_texts)` where `headers` is a list of `{"from_email": str, "date": datetime|None, "subject": str}` and `bounce_texts` is a list of str (raw text of mailer-daemon/postmaster messages).
  - `reconcile(applications, headers, bounce_texts, now=None) -> dict` — mutates app dicts in place (`status`, `status_checked_at`, `reply_date`, `reply_subject`), returns `{"checked": n, "replied": n, "bounced": n, "no_reply": n}`.
- Consumes: `cfg["smtp_email"]`, `cfg["smtp_password"]`.

**Matching rules (from spec):** skip apps where `sent_to != recruiter_email`; a reply is an inbox message whose From equals `recruiter_email` (case-insensitive) with date >= app date, assigned to the most recent such app; bounce = `sent_to` appears in any bounce text; precedence replied > bounced; everything else `no_reply`. Apps already `replied`/`bounced` are not passed in by the caller (Task 7 filters).

- [ ] **Step 1: Write the failing test**

Create `tests/test_inbox.py`:

```python
# -*- coding: utf-8 -*-
import unittest
from datetime import datetime

from jobhunter.inbox import imap_date, reconcile

NOW = datetime(2026, 8, 5, 12, 0, 0)


def _app(email, date="2026-08-01T10:00:00", **kw):
    base = {"recruiter_email": email, "sent_to": email, "date": date,
            "job_title": "T", "company": "C", "mode": "run"}
    base.update(kw)
    return base


class ImapDateTests(unittest.TestCase):
    def test_format(self):
        self.assertEqual(imap_date(datetime(2026, 8, 5)), "05-Aug-2026")
        self.assertEqual(imap_date(datetime(2026, 1, 31)), "31-Jan-2026")


class ReconcileTests(unittest.TestCase):
    def test_reply_marks_replied(self):
        app = _app("r@x.com")
        headers = [{"from_email": "r@x.com", "date": datetime(2026, 8, 2, 9, 0), "subject": "Re: CV"}]
        summary = reconcile([app], headers, [], now=NOW)
        self.assertEqual(app["status"], "replied")
        self.assertEqual(app["reply_subject"], "Re: CV")
        self.assertEqual(summary["replied"], 1)

    def test_reply_before_send_does_not_count(self):
        app = _app("r@x.com", date="2026-08-03T10:00:00")
        headers = [{"from_email": "r@x.com", "date": datetime(2026, 8, 2, 9, 0), "subject": "viejo"}]
        reconcile([app], headers, [], now=NOW)
        self.assertEqual(app["status"], "no_reply")

    def test_bounce_detected_in_text(self):
        app = _app("dead@x.com")
        bounce = "Delivery incomplete ... The recipient DEAD@x.com was not found"
        summary = reconcile([app], [], [bounce], now=NOW)
        self.assertEqual(app["status"], "bounced")
        self.assertEqual(summary["bounced"], 1)

    def test_replied_wins_over_bounce(self):
        app = _app("r@x.com")
        headers = [{"from_email": "R@X.com", "date": datetime(2026, 8, 2), "subject": "hola"}]
        reconcile([app], headers, ["fallo a r@x.com"], now=NOW)
        self.assertEqual(app["status"], "replied")

    def test_reply_assigned_to_most_recent_prior_app(self):
        old = _app("r@x.com", date="2026-07-01T10:00:00")
        new = _app("r@x.com", date="2026-08-01T10:00:00")
        headers = [{"from_email": "r@x.com", "date": datetime(2026, 8, 2), "subject": "s"}]
        reconcile([old, new], headers, [], now=NOW)
        self.assertEqual(new["status"], "replied")
        self.assertEqual(old["status"], "no_reply")

    def test_no_reply_sets_checked_at(self):
        app = _app("r@x.com")
        summary = reconcile([app], [], [], now=NOW)
        self.assertEqual(app["status"], "no_reply")
        self.assertEqual(app["status_checked_at"], NOW.isoformat())
        self.assertEqual(summary["no_reply"], 1)

    def test_test_sends_are_skipped(self):
        app = _app("r@x.com", sent_to="yo@gmail.com")
        summary = reconcile([app], [], [], now=NOW)
        self.assertNotIn("status", app)
        self.assertEqual(summary["checked"], 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_inbox -v`
Expected: `ModuleNotFoundError: No module named 'jobhunter.inbox'`

- [ ] **Step 3: Create `jobhunter/inbox.py`**

```python
# -*- coding: utf-8 -*-
"""Lectura de Gmail via IMAP para conciliar respuestas y rebotes.

Una sola conexion y una sola busqueda SINCE; los rebotes se detectan por el
remitente (mailer-daemon/postmaster) y solo para esos se descarga el cuerpo.
"""
import email
import imaplib
from datetime import datetime
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
BOUNCE_SENDERS = ("mailer-daemon", "postmaster")
FETCH_BATCH = 100


def imap_date(d):
    """Fecha IMAP DD-Mon-YYYY independiente del locale."""
    return "%02d-%s-%d" % (d.day, MONTHS[d.month - 1], d.year)


def _decode_subject(raw):
    try:
        return str(make_header(decode_header(raw or "")))
    except Exception:
        return raw or ""


def _parse_header_blob(blob):
    msg = email.message_from_bytes(blob)
    from_email = (parseaddr(msg.get("From", ""))[1] or "").lower()
    try:
        mdate = parsedate_to_datetime(msg.get("Date", ""))
        if mdate is not None and mdate.tzinfo is not None:
            mdate = mdate.astimezone().replace(tzinfo=None)
    except Exception:
        mdate = None
    return {
        "from_email": from_email,
        "date": mdate,
        "subject": _decode_subject(msg.get("Subject", "")),
    }


def fetch_inbox(cfg, since):
    """Retorna (headers, bounce_texts) del INBOX desde `since` (datetime)."""
    conn = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    try:
        conn.login(cfg["smtp_email"], cfg["smtp_password"])
        conn.select("INBOX", readonly=True)
        _, data = conn.search(None, "SINCE", imap_date(since))
        ids = data[0].split() if data and data[0] else []

        headers = []
        bounce_ids = []
        for start in range(0, len(ids), FETCH_BATCH):
            chunk = ids[start:start + FETCH_BATCH]
            idset = b",".join(chunk)
            _, parts = conn.fetch(idset, "(BODY.PEEK[HEADER.FIELDS (FROM DATE SUBJECT)])")
            pos = 0
            for part in parts:
                if not isinstance(part, tuple) or len(part) < 2 or part[1] is None:
                    continue
                entry = _parse_header_blob(part[1])
                headers.append(entry)
                mid = part[0].split()[0] if part[0] else None
                if mid and any(b in entry["from_email"] for b in BOUNCE_SENDERS):
                    bounce_ids.append(mid)
                pos += 1

        bounce_texts = []
        for mid in bounce_ids:
            _, parts = conn.fetch(mid, "(BODY.PEEK[TEXT])")
            for part in parts:
                if isinstance(part, tuple) and len(part) > 1 and part[1]:
                    bounce_texts.append(part[1].decode("utf-8", errors="replace"))
        return headers, bounce_texts
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def _app_date(app):
    try:
        return datetime.fromisoformat(app.get("date", ""))
    except Exception:
        return datetime.min


def reconcile(applications, headers, bounce_texts, now=None):
    """Cruza aplicaciones con el buzon. Muta las apps; retorna resumen.

    Precedencia: replied > bounced. La respuesta se asigna a la app mas
    reciente enviada antes de la fecha de la respuesta.
    """
    now = now or datetime.now()
    summary = {"checked": 0, "replied": 0, "bounced": 0, "no_reply": 0}

    candidates = [
        a for a in (applications or [])
        if a.get("recruiter_email") and a.get("sent_to") == a.get("recruiter_email")
    ]
    summary["checked"] = len(candidates)

    by_sender = {}
    for h in headers or []:
        if h.get("from_email"):
            by_sender.setdefault(h["from_email"], []).append(h)

    for sender, msgs in by_sender.items():
        apps_to = [a for a in candidates if (a.get("recruiter_email") or "").lower() == sender]
        if not apps_to:
            continue
        for m in sorted(msgs, key=lambda x: x.get("date") or now):
            mdate = m.get("date") or now
            prior = [a for a in apps_to if a.get("status") != "replied" and _app_date(a) <= mdate]
            if not prior:
                continue
            target = max(prior, key=_app_date)
            target["status"] = "replied"
            target["reply_date"] = mdate.isoformat()
            target["reply_subject"] = m.get("subject") or ""
            target["status_checked_at"] = now.isoformat()
            summary["replied"] += 1

    bounce_blob = "\n".join(bounce_texts or []).lower()
    for app in candidates:
        if app.get("status") == "replied":
            continue
        addr = (app.get("sent_to") or "").lower()
        if addr and addr in bounce_blob:
            app["status"] = "bounced"
            summary["bounced"] += 1
        else:
            app["status"] = "no_reply"
            summary["no_reply"] += 1
        app["status_checked_at"] = now.isoformat()

    return summary
```

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_inbox -v`
Expected: 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add jobhunter/inbox.py tests/test_inbox.py
git commit -m "feat(inbox): lectura IMAP y conciliacion de respuestas/rebotes"
```

---

### Task 7: `jobhunter sync` command + dispatcher

**Files:**
- Create: `jobhunter/cli/sync.py`
- Modify: `jobhunter/cli/main.py`, `jobhunter/cli/help.py`
- Test: `tests/test_cli_sync.py`

**Interfaces:**
- Produces: `cmd_sync(days=60)`.
- Consumes: `fetch_inbox(cfg, since)`, `reconcile(apps, headers, bounce_texts)` (Task 6), `build_dashboard_data(kb)` totals for the summary panel (Task 4), `load_config`, `load_kb`, `save_kb`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_sync.py`:

```python
# -*- coding: utf-8 -*-
import imaplib
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from jobhunter.cli.sync import cmd_sync


def _cfg():
    return {"smtp_email": "yo@gmail.com", "smtp_password": "app-pass", "profile": {"name": "J"}}


def _recent(days_ago=2):
    return (datetime.now() - timedelta(days=days_ago)).isoformat()


def _kb():
    return {
        "runs": [],
        "applications": [
            {"date": _recent(2), "job_title": "A", "company": "C1",
             "recruiter_email": "r1@x.com", "sent_to": "r1@x.com", "mode": "run"},
            {"date": _recent(3), "job_title": "B", "company": "C2",
             "recruiter_email": "r2@x.com", "sent_to": "r2@x.com", "mode": "run",
             "status": "replied", "reply_date": _recent(1)},
            {"date": "2020-01-01T00:00:00", "job_title": "Vieja", "company": "C3",
             "recruiter_email": "r3@x.com", "sent_to": "r3@x.com", "mode": "run"},
        ],
    }


class CmdSyncTests(unittest.TestCase):
    @patch("jobhunter.cli.sync.console")
    @patch("jobhunter.cli.sync.save_kb")
    @patch("jobhunter.cli.sync.fetch_inbox")
    @patch("jobhunter.cli.sync.load_kb")
    @patch("jobhunter.cli.sync.load_config", return_value=_cfg())
    def test_reconciles_pending_and_saves(self, _lc, mock_lk, mock_fetch, mock_save, _c):
        kb = _kb()
        mock_lk.return_value = kb
        mock_fetch.return_value = (
            [{"from_email": "r1@x.com", "date": datetime.now(), "subject": "Re: CV"}], [],
        )
        cmd_sync(days=60)
        self.assertEqual(kb["applications"][0]["status"], "replied")
        self.assertNotIn("status", kb["applications"][2])  # fuera de ventana
        mock_save.assert_called_once_with(kb)
        # terminal previa no se re-chequea: solo 1 pendiente entro al fetch window
        since = mock_fetch.call_args.args[1]
        self.assertGreater(since, datetime.now() - timedelta(days=10))

    @patch("jobhunter.cli.sync.console")
    @patch("jobhunter.cli.sync.save_kb")
    @patch("jobhunter.cli.sync.fetch_inbox", side_effect=imaplib.IMAP4.error("auth"))
    @patch("jobhunter.cli.sync.load_kb")
    @patch("jobhunter.cli.sync.load_config", return_value=_cfg())
    def test_imap_auth_error_message(self, _lc, mock_lk, _fetch, mock_save, mock_console):
        mock_lk.return_value = _kb()
        cmd_sync(days=60)
        mock_save.assert_not_called()
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("IMAP", printed)

    @patch("jobhunter.cli.sync.console")
    @patch("jobhunter.cli.sync.load_kb", return_value={"runs": [], "applications": []})
    @patch("jobhunter.cli.sync.load_config", return_value=_cfg())
    def test_nothing_pending(self, _lc, _lk, mock_console):
        cmd_sync(days=60)
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("Nada que conciliar", printed)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli_sync -v`
Expected: `ModuleNotFoundError: No module named 'jobhunter.cli.sync'`

- [ ] **Step 3: Create `jobhunter/cli/sync.py`**

```python
# -*- coding: utf-8 -*-
"""Comando sync: concilia respuestas y rebotes leyendo Gmail via IMAP."""
import imaplib
import time
from datetime import datetime, timedelta

from rich.panel import Panel
from rich.table import Table

from jobhunter.banner import get_banner
from jobhunter.config import load_config
from jobhunter.inbox import fetch_inbox, reconcile
from jobhunter.metrics import build_dashboard_data
from jobhunter.storage import load_kb, save_kb
from jobhunter.ui import console


def cmd_sync(days=60):
    cfg = load_config()
    kb = load_kb()
    if not cfg.get("smtp_email") or not cfg.get("smtp_password"):
        console.print("  [red]✗[/red] Falta configuracion SMTP. Ejecuta: [cyan]jobhunter setup[/cyan]")
        return

    console.print(get_banner())
    cutoff = datetime.now() - timedelta(days=days)
    pending = []
    for a in kb.get("applications", []):
        if a.get("status") in ("replied", "bounced"):
            continue
        if not a.get("recruiter_email") or a.get("sent_to") != a.get("recruiter_email"):
            continue
        try:
            d = datetime.fromisoformat(a["date"])
        except Exception:
            continue
        if d >= cutoff:
            pending.append((d, a))

    if not pending:
        console.print(f"  [yellow]![/yellow] Nada que conciliar en los ultimos {days} dias.")
        return

    since = min(d for d, _ in pending)
    console.print(f"  [bold dim]Conciliando {len(pending)} aplicaciones desde {since.strftime('%Y-%m-%d')}...[/bold dim]")
    console.print()

    headers = None
    bounce_texts = None
    last_err = None
    for attempt in range(2):
        try:
            with console.status("  [dim]Leyendo Gmail (IMAP)...[/dim]"):
                headers, bounce_texts = fetch_inbox(cfg, since)
            break
        except imaplib.IMAP4.error:
            console.print("  [red]✗[/red] Autenticacion IMAP fallo. Verifica que IMAP este habilitado en Gmail y la app password sea valida.")
            console.print("    [dim]Gmail → Ver todos los ajustes → Reenvio y correo POP/IMAP → Habilitar IMAP[/dim]")
            return
        except Exception as e:
            last_err = e
            time.sleep(2)
    if headers is None:
        console.print(f"  [red]✗[/red] No se pudo leer el buzon: {last_err}")
        return

    apps = [a for _, a in pending]
    summary = reconcile(apps, headers, bounce_texts)
    save_kb(kb)

    changed = [a for a in apps if a.get("status") in ("replied", "bounced")]
    if changed:
        table = Table(border_style="cyan", title="[bold]Novedades[/bold]", padding=(0, 1))
        table.add_column("Empresa", max_width=22)
        table.add_column("Puesto", max_width=28)
        table.add_column("Email", max_width=28, style="cyan")
        table.add_column("Estado")
        table.add_column("Detalle", max_width=30, style="dim")
        for a in changed:
            if a["status"] == "replied":
                estado = "[green]RESPONDIO[/green]"
                detalle = (a.get("reply_subject") or "")[:30]
            else:
                estado = "[red]REBOTO[/red]"
                detalle = "verifica el email"
            table.add_row(a.get("company", "-"), a.get("job_title", "-"), a.get("sent_to", "-"), estado, detalle)
        console.print(table)
    else:
        console.print("  [dim]Sin novedades: nadie respondio ni reboto en esta pasada.[/dim]")

    d = build_dashboard_data(kb)
    t = d["totals"]
    console.print()
    console.print(Panel(
        f"  [dim]Chequeadas[/dim]        {summary['checked']}\n"
        f"  [dim]Enviados (total)[/dim]  {t['sent']}\n"
        f"  [dim]Respondidos[/dim]       [green]{t['replied']}[/green]  [dim]({d['reply_rate']}% de entregados)[/dim]\n"
        f"  [dim]Rebotados[/dim]         [red]{t['bounced']}[/red]  [dim]({d['bounce_rate']}%)[/dim]\n"
        f"  [dim]Sin respuesta[/dim]     [yellow]{t['no_reply']}[/yellow]\n"
        f"  [dim]Sin conciliar[/dim]     {t['unknown']}",
        border_style="green", title="[bold]Conciliacion[/bold]",
    ))
```

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_cli_sync -v`
Expected: 3 tests PASS

- [ ] **Step 5: Wire dispatcher and help**

`jobhunter/cli/main.py`: add import `from jobhunter.cli.sync import cmd_sync` and branch:

```python
    elif cmd in ("sync",):
        days = 60
        for i, a in enumerate(sys.argv):
            if a == "--days" and i + 1 < len(sys.argv):
                try:
                    days = int(sys.argv[i + 1])
                except ValueError:
                    pass
        cmd_sync(days=days)
```

`jobhunter/cli/help.py`: add rows after the dashboard row:

```python
    cmds.add_row("jobhunter sync", "Conciliar respuestas y rebotes (Gmail IMAP)")
    cmds.add_row("jobhunter sync --days 90", "Conciliar con ventana mas amplia")
```

- [ ] **Step 6: Manual smoke + full suite**

Run: `python job.py sync` against the real mailbox — verify the summary panel appears and `knowledge.json` gains `status` fields (backup: copy knowledge.json before, diff after).
Run: `python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -3`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add jobhunter/cli/sync.py jobhunter/cli/main.py jobhunter/cli/help.py tests/test_cli_sync.py
git commit -m "feat(sync): comando sync de conciliacion via Gmail IMAP"
```

---

### Task 8: Docs, Python 3.10 check, final suite

**Files:**
- Modify: `README.md` (commands section), `CLAUDE.md` (Commands + Key Files sections)
- Test: full suite + compile check

- [ ] **Step 1: Update `CLAUDE.md`**

In the Commands code block add after `jobhunter run --time ...`:

```
jobhunter apply [link|"texto"]       # Apply to a single posting (paste mode if no arg)
jobhunter dashboard [--port N]       # Local metrics dashboard (default 4090)
jobhunter sync [--days N]            # Reconcile replies/bounces via Gmail IMAP (default 60)
```

In Key Files add:

```
  - `applying.py` — per-offer apply flow (CV + email + preview + send), shared by run/apply
  - `metrics.py` — pure aggregates for the dashboard
  - `inbox.py` — IMAP fetch + reply/bounce reconciliation
  - `assets/dashboard.html` — self-contained dashboard page
  - `cli/apply.py`, `cli/dashboard.py`, `cli/sync.py` — new commands
```

- [ ] **Step 2: Update `README.md`**

Find the commands table/section and add the three commands with one-line Spanish descriptions mirroring `help.py`.

- [ ] **Step 3: Python 3.10 compatibility check**

Run: `docker run --rm -v "C:\Users\joseg\.jobhunter\jobhunter:/pkg:ro" python:3.10-slim python3 -c "import py_compile, pathlib; [py_compile.compile(str(p), doraise=True) for p in pathlib.Path('/pkg').rglob('*.py')]; print('OK 3.10')"`
Expected: `OK 3.10`. If Docker is unavailable: run local `python -m py_compile` on every new/modified file AND manually grep new files for triple-quoted f-strings (`grep -n 'f"""' jobhunter -r`) — must be none.

- [ ] **Step 4: Full suite one last time**

Run: `python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -3`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: documentar apply, dashboard y sync"
```
