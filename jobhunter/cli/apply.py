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
