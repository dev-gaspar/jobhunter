# -*- coding: utf-8 -*-
"""Aplicacion por oferta (frontend de terminal): preview interactivo y envio.

La generacion (CV + email) y el envio viven en jobhunter.service; aqui queda
solo la interaccion Rich. Lo comparten cmd_run y el comando apply.
"""
import os

from rich.panel import Panel
from rich.prompt import Prompt

from jobhunter.service import check_recipient, prepare_application, send_application
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

    with console.status(f"{label}  [dim]CV...[/dim]") as status:
        def _on_event(name, payload):
            if name == "apply_progress" and payload.get("stage") == "email":
                status.update(f"{label}  [dim]Email...[/dim]")

        prepared = prepare_application(cfg, job, test_email=test_email,
                                       on_event=_on_event)
    record["cv_path"] = prepared["cv_path"]

    if not prepared["ok"]:
        console.print(f"{label}  [red]! {prepared['error']}[/red]")
        return {"status": "error", "record": record, "preview_send_all": preview_send_all}

    cv_name = os.path.basename(prepared["cv_path"]) if prepared["cv_path"] else ""

    if dry_run:
        preview_text = (
            f"Para: {to}\n"
            f"Asunto: {prepared['subject']}\n"
            f"CV adjunto: {cv_name or '—'}\n\n"
            f"{prepared['body']}"
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
                f"Asunto: {prepared['subject']}\n"
                f"CV adjunto: {cv_name or '—'}\n\n"
                f"{prepared['body']}"
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
                prepared["subject"] = Prompt.ask("  Asunto", default=prepared["subject"])
                continue
            if choice in ("a", "all"):
                preview_send_all = True
                do_send = True
                break
            console.print("  [red]✗[/red] Opcion invalida (s/x/e/a)")

    if not do_send:
        record["skipped"] = True
        return {"status": "skipped", "record": record, "preview_send_all": preview_send_all}

    if not test_email and check_recipient(to) is False:
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

    res = send_application(cfg, kb, job, prepared, to, mode=mode,
                           recruiter_email=rec_email)
    if res["status"] == "sent":
        console.print(f"{label}  [green]> Enviado[/green] [dim]→ {to}[/dim]")
        return {"status": "sent", "record": record, "preview_send_all": preview_send_all}
    console.print(f"{label}  [red]! {res['error']}[/red]")
    return {"status": "error", "record": record, "preview_send_all": preview_send_all}
