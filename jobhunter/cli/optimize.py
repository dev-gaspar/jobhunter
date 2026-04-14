# -*- coding: utf-8 -*-
"""Comando optimize: llama al optimizer agent, muestra diff y aplica si confirma."""
from rich.prompt import Confirm

from jobhunter.agents.optimizer import optimize_queries
from jobhunter.banner import get_banner
from jobhunter.config import load_config, save_config
from jobhunter.storage import load_kb
from jobhunter.ui import console


def cmd_optimize(user_prompt=None):
    cfg = load_config()
    kb = load_kb()

    if not cfg.get("gemini_api_key"):
        console.print("  [red]\u2717[/red] Falta configuracion. Ejecuta: [cyan]jobhunter setup[/cyan]")
        return

    console.print(get_banner())
    console.print()
    console.print("  [bold dim]Optimizando queries de busqueda...[/bold dim]")
    console.print()

    current_queries = cfg.get("search_queries", [])

    with console.status("  [dim]Analizando y generando queries optimizadas...[/dim]"):
        result = optimize_queries(cfg, kb, user_prompt=user_prompt)

    new_queries = result.get("queries", [])
    analysis = result.get("analysis", "")
    summary = result.get("changes_summary", "")

    if not new_queries:
        console.print("  [yellow]![/yellow] El agente no genero queries nuevas.")
        return

    if analysis:
        console.print("  [bold]Analisis[/bold]")
        console.print(f"  [dim]{analysis}[/dim]")
        console.print()

    console.print(f"  [bold]Queries actuales[/bold] [dim]({len(current_queries)})[/dim]")
    for q in current_queries:
        console.print(f"    [red]-[/red] [dim]{q}[/dim]")

    console.print()
    console.print(f"  [bold]Queries propuestas[/bold] [dim]({len(new_queries)})[/dim]")
    for q in new_queries:
        console.print(f"    [green]+[/green] {q}")

    console.print()
    if summary:
        console.print(f"  [dim]{summary}[/dim]")
        console.print()

    if not Confirm.ask("  Aplicar cambios?", default=True):
        console.print("  [dim]Sin cambios.[/dim]")
        return

    cfg["search_queries"] = new_queries
    save_config(cfg)
    console.print(f"  [green]\u2713[/green] {len(new_queries)} queries guardadas")
    console.print()
