# -*- coding: utf-8 -*-
"""Comando history: lista aplicaciones con filtros por fecha, empresa y cantidad."""
from datetime import datetime

from rich.panel import Panel
from rich.table import Table

from jobhunter.storage import load_kb
from jobhunter.ui import console


def cmd_history(last=10, company_filter=None, since=None, show_all=False):
    """Muestra historial de aplicaciones desde knowledge.json."""
    kb = load_kb()
    apps = kb.get("applications", [])
    if not apps:
        console.print("  [yellow]![/yellow] No hay aplicaciones registradas.")
        return

    apps = sorted(apps, key=lambda a: a.get("date", ""), reverse=True)

    if company_filter:
        cf = company_filter.lower()
        apps = [a for a in apps if cf in (a.get("company") or "").lower()]

    if since:
        try:
            cutoff = datetime.fromisoformat(since)
            apps = [a for a in apps if datetime.fromisoformat(a.get("date", "1970-01-01")) >= cutoff]
        except ValueError:
            console.print(f"  [red]![/red] Formato de fecha invalido: {since} (usa YYYY-MM-DD)")
            return

    if not show_all:
        apps = apps[:last]

    if not apps:
        console.print("  [yellow]![/yellow] No se encontraron aplicaciones con esos filtros.")
        return

    table = Table(border_style="cyan", padding=(0, 1), expand=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Fecha", style="dim", width=12)
    table.add_column("Puesto", style="bold", max_width=35)
    table.add_column("Empresa", max_width=25)
    table.add_column("Email reclutador", style="dim", max_width=30)
    table.add_column("Modo", width=6)
    table.add_column("Post", width=6, justify="center")

    for i, app in enumerate(apps, 1):
        date_str = app.get("date", "")[:10]
        mode = (app.get("mode") or "run").lower()
        mode_style = "[yellow]TEST[/yellow]" if mode == "test" else "[green]RUN[/green]"
        post_url = app.get("post_url")
        post_link = f"[link={post_url}]Ver[/link]" if post_url else "[dim]\u2014[/dim]"
        table.add_row(
            str(i),
            date_str,
            (app.get("job_title") or "-")[:35],
            (app.get("company") or "-")[:25],
            (app.get("recruiter_email") or app.get("sent_to") or "-")[:30],
            mode_style,
            post_link,
        )

    console.print()
    console.print(Panel(table, border_style="cyan", title=f"[bold]Historial de aplicaciones ({len(apps)})[/bold]"))
    console.print()
