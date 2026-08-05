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
from jobhunter.mailer import domain_accepts_mail, send_email
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

    if not test_email and domain_accepts_mail(to) is False:
        console.print(f"{label}  [yellow]![/yellow] El dominio de [bold]{to}[/bold] no tiene registros de correo (posible typo)")
        if interactive:
            alt = (Prompt.ask("  Email alternativo (vacio = omitir esta oferta)", default="") or "").strip()
            if alt and "@" in alt:
                to = alt
                rec_email = alt
                record["sent_to"] = to
                record["recruiter_email"] = rec_email
            else:
                console.print("       [yellow]·[/yellow] Omitido por dominio invalido")
                record["skipped"] = True
                return {"status": "skipped", "record": record, "preview_send_all": preview_send_all}
        else:
            console.print("       [yellow]·[/yellow] Omitido por dominio invalido")
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
            "query": job.get("query"),
            "author_url": job.get("author_url"),
            "author_name": job.get("author_name"),
        })
        return {"status": "sent", "record": record, "preview_send_all": preview_send_all}
    except Exception as e:
        console.print(f"{label}  [red]! {e}[/red]")
        return {"status": "error", "record": record, "preview_send_all": preview_send_all}
