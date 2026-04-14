# -*- coding: utf-8 -*-
"""Comando status: muestra config actual + estadisticas de ejecuciones."""
import os

from rich.panel import Panel
from rich.table import Table

from jobhunter.banner import get_banner
from jobhunter.config import load_config
from jobhunter.constants import SESSION_DIR
from jobhunter.storage import load_kb
from jobhunter.ui import console


def cmd_status():
    console.print(get_banner())
    cfg = load_config()
    kb = load_kb()

    secret_ok = lambda v: "[green]\u2713[/green] Configurado" if v else "[red]\u2717[/red] No configurado"

    runs = kb.get("runs", [])
    apps = kb.get("applications", [])
    total_sent = sum(1 for a in apps if a.get("mode") == "run")
    total_test = sum(1 for a in apps if a.get("mode") == "test")
    last_run = runs[-1]["date"][:10] if runs else "-"

    table = Table(border_style="cyan", show_header=False, padding=(0, 2), expand=False)
    table.add_column("key", style="dim", width=14)
    table.add_column("value")

    table.add_row("Nombre", cfg.get("profile", {}).get("name") or "[yellow]?[/yellow]")
    table.add_row("Correo", cfg.get("smtp_email") or "[red]No configurado[/red]")
    table.add_row("Clave API", secret_ok(cfg.get("gemini_api_key")))
    table.add_row("Contrasena", secret_ok(cfg.get("smtp_password")))
    table.add_row("Modelo", cfg.get("gemini_model", "gemini-2.5-flash"))
    table.add_row("CV", cfg.get("cv_path") or "[yellow]No configurado[/yellow]")
    table.add_row("Busqueda", cfg.get("job_types_raw") or "[yellow]No configurado[/yellow]")
    table.add_row("Queries", str(len(cfg.get("search_queries", []))))
    table.add_row(
        "LinkedIn",
        "[green]\u2713[/green] Sesion guardada" if os.path.exists(SESSION_DIR) else "[red]\u2717[/red] Sin sesion",
    )

    console.print(Panel(table, border_style="cyan", title="[bold]Configuracion[/bold]"))

    stats_table = Table(show_header=False, border_style="dim", padding=(0, 2), expand=False)
    stats_table.add_column("key", style="dim", width=14)
    stats_table.add_column("value")
    stats_table.add_row("Ejecuciones", f"[bold]{len(runs)}[/bold]")
    stats_table.add_row("Enviados", f"[bold green]{total_sent}[/bold green]")
    stats_table.add_row("Tests", f"[bold]{total_test}[/bold]")
    stats_table.add_row("Ultima vez", last_run)

    console.print(Panel(stats_table, border_style="dim", title="[bold]Estadisticas[/bold]"))
    console.print()
