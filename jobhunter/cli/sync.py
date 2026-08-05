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
