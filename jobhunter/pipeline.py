# -*- coding: utf-8 -*-
"""Pipeline principal (frontend de terminal): consume la fachada service.py.

Renderiza banner, progreso Rich, tabla de ofertas y seleccion interactiva;
la logica de scrape/analisis/filtros vive en jobhunter.service.
"""
import csv
import json
import os
import time

from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt
from rich.table import Table
import shutil

from jobhunter.applying import apply_to_offer
from jobhunter.banner import get_banner
from jobhunter.config import is_configured, load_config
from jobhunter.service import record_run, search_offers, write_run_log
from jobhunter.storage import load_kb
from jobhunter.ui import console


def _print_decision(d):
    """Linea inline por decision del filtro (mismo formato historico)."""
    company = (d.get("company") or "").strip()
    title = (d.get("job_title") or "").strip()
    reason = (d.get("relevance_reason") or "").strip()
    if d.get("is_job") and d.get("is_relevant", True):
        label = f"    [green]✓[/green] {company or '-'} [dim]—[/dim] {title or '-'}"
    elif d.get("is_job"):
        short = reason[:90] or "no relevante"
        head = f"{company or '-'} — {title or '-'}" if (company or title) else "oferta no relevante"
        label = f"    [yellow]–[/yellow] [dim]{head}[/dim] [yellow]·[/yellow] [yellow]{short}[/yellow]"
    else:
        short = reason[:100] or "no es oferta"
        label = f"    [dim red]✗[/dim red] [dim]{short}[/dim]"
    console.print(label)


class _RichEvents:
    """Traduce eventos de la fachada a Progress/prints de Rich."""

    def __init__(self):
        self.prog = None
        self.task = None

    def _start_progress(self, description, total):
        self.prog = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        )
        self.prog.start()
        self.task = self.prog.add_task(description, total=total)

    def _stop_progress(self, total):
        if self.prog is not None:
            self.prog.update(self.task, completed=total)
            self.prog.stop()
            self.prog = None

    def __call__(self, name, payload):
        if name == "phase":
            phase = payload["phase"]
            if payload["status"] == "start":
                if phase == "scrape":
                    console.print()
                    console.print("  [bold dim]Buscando en LinkedIn...[/bold dim]")
                    self._start_progress("Buscando...", payload.get("total") or 0)
                elif phase == "analyze":
                    console.print()
                    console.print("  [bold dim]Analizando ofertas...[/bold dim]")
                    self._start_progress("Analizando...", payload.get("total") or 0)
            elif payload["status"] == "done" and phase in ("scrape", "analyze"):
                self._stop_progress(payload.get("total") or 0)
        elif name == "progress" and self.prog is not None:
            msg = (payload.get("msg") or "")[:45]
            self.prog.update(self.task, description=f"[dim]{msg}[/dim]",
                             completed=payload.get("current", 0))
        elif name == "decision":
            _print_decision(d=payload)


def _print_offers_table(offers):
    tw = shutil.get_terminal_size((80, 24)).columns
    wide = tw >= 100
    extra_wide = tw >= 130
    table = Table(border_style="cyan", title="[bold]Ofertas encontradas[/bold]",
                  expand=False, show_lines=False, padding=(0, 1))
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Puesto", max_width=28 if wide else 20, style="bold")
    table.add_column("Empresa", max_width=16 if wide else 12)
    table.add_column("Modo", width=10)
    if wide:
        table.add_column("Ubicacion", max_width=18, style="dim")
        table.add_column("Lang", width=4, style="dim")
    if extra_wide:
        table.add_column("Salario", max_width=18, style="green")
    table.add_column("Email", max_width=26 if wide else 22, style="cyan")
    table.add_column("Post", max_width=20 if wide else 6, justify="left" if wide else "center")
    mode_icons = {"remote": "[green]Remoto[/green]", "hybrid": "[yellow]Hibrido[/yellow]",
                  "onsite": "[red]Onsite[/red]", "unknown": "[dim]—[/dim]"}
    for i, o in enumerate(offers, 1):
        wm = mode_icons.get(o.get("work_mode", "unknown"), "[dim]—[/dim]")
        loc = o.get("location") or "—"
        if loc.lower() in ("null", "none", "n/a", "no especificado", "no mencionado"):
            loc = "—"
        la = (o.get("language", "?"))[:4].upper()
        salary = o.get("salary") or "—"
        if str(salary).lower() in ("null", "none", "n/a", "no mencionado", "no especificado"):
            salary = "—"
        if o.get("post_url"):
            shown = o["post_url"].replace("https://", "") if wide else "Ver"
            post_link = f"[link={o['post_url']}]{shown}[/link]"
        else:
            post_link = "[dim]—[/dim]"
        if extra_wide:
            table.add_row(str(i), o["job_title"][:28], o["company"][:16], wm, loc[:18], la,
                          str(salary)[:18], o["contact_email"], post_link)
        elif wide:
            table.add_row(str(i), o["job_title"][:28], o["company"][:16], wm, loc[:18], la,
                          o["contact_email"], post_link)
        else:
            table.add_row(str(i), o["job_title"][:20], o["company"][:12], wm,
                          o["contact_email"], post_link)
    console.print(table)


def _export_offers(offers, export_fmt, export_path):
    os.makedirs(os.path.dirname(os.path.abspath(export_path)) or ".", exist_ok=True)
    export_fields = ["job_title", "company", "contact_email", "work_mode", "location",
                     "salary", "language", "post_url"]
    if export_fmt == "csv":
        with open(export_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=export_fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(offers)
        console.print(f"  [green]>[/green] Exportado: {export_path}")
    elif export_fmt == "json":
        export_data = [{k: o.get(k) for k in export_fields} for o in offers]
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        console.print(f"  [green]>[/green] Exportado: {export_path}")


def cmd_run(
    test_email=None,
    time_filter="24h",
    auto_apply=False,
    dry_run=False,
    export_fmt=None,
    export_path=None,
):
    cfg = load_config()
    kb = load_kb()

    if not is_configured():
        console.print("  [red]✗[/red] Falta configuracion. Ejecuta: [cyan]jobhunter setup[/cyan]")
        return
    from jobhunter.constants import SESSION_DIR
    if not os.path.exists(SESSION_DIR):
        console.print("  [red]✗[/red] Sin sesion LinkedIn. Ejecuta: [cyan]jobhunter login[/cyan]")
        return

    console.print(get_banner())
    mode = "test" if test_email else "run"

    time_labels = {"24h": "Ultimas 24h", "week": "Esta semana", "month": "Este mes"}
    mode_label = f"[yellow]TEST → {test_email}[/yellow]" if test_email else "[green]Reclutadores[/green]"
    dry_line = "\n  [dim]Dry-run[/dim]   [yellow]Si — sin enviar emails[/yellow]" if dry_run else ""
    console.print(Panel(
        f"  [dim]Perfil[/dim]     {cfg['profile'].get('name','?')}\n"
        f"  [dim]Destino[/dim]    {mode_label}\n"
        f"  [dim]Periodo[/dim]    {time_labels.get(time_filter, time_filter)}\n"
        f"  [dim]Queries[/dim]    {len(cfg.get('search_queries',[]))}{dry_line}",
        border_style="cyan", title="[bold]Sesion[/bold]"
    ))

    events = _RichEvents()
    result = search_offers(cfg, kb, time_filter=time_filter, on_event=events, pace=True)
    if events.prog is not None:  # por si un error corto el flujo a mitad de fase
        events.prog.stop()

    stats = result["stats"]
    decisions = result["decisions"]

    if result["error"]:
        kind = result["error"]["kind"]
        if kind == "cancelled":
            console.print("\n  [dim]Cancelado.[/dim]")
        elif kind == "session_expired":
            console.print("  [red]![/red] Sesion expirada. Ejecuta: [cyan]jobhunter login[/cyan]")
        elif kind == "no_posts":
            console.print(
                f"  [bold]{stats.get('posts_scraped', 0)}[/bold] posts  ·  "
                f"[bold]{stats.get('posts_with_emails', 0)}[/bold] con email  ·  "
                f"[dim]{stats.get('posts_no_emails', 0)} sin email (omitidos)[/dim]"
            )
            console.print()
            console.print("  [yellow]![/yellow] No se encontraron posts con email. Intenta un periodo mas amplio.")
            console.print("    [dim]Ej: jobhunter run --time week[/dim]")
        else:
            console.print(f"  [red]✗[/red] {result['error']['message']}")
        return

    console.print(
        f"  [bold]{stats['posts_scraped']}[/bold] posts  ·  "
        f"[bold]{stats['posts_with_emails']}[/bold] con email  ·  "
        f"[dim]{stats['posts_no_emails']} sin email (omitidos)[/dim]"
    )

    offers = result["offers"]
    blacklist_info = "  ·  " + str(stats["blacklisted"]) + " bloqueadas" if stats.get("blacklisted") else ""
    console.print(
        f"  [bold]{stats['filter_accepted']}[/bold] ofertas  ·  "
        f"[green]{len(offers)}[/green] con email  ·  "
        f"[dim]{stats['batch_dupes']} duplicadas  ·  {stats['offers_no_email']} sin email{blacklist_info}[/dim]"
    )
    if stats.get("already_applied"):
        console.print(f"  [yellow]![/yellow] {stats['already_applied']} omitidas (ya enviadas en los ultimos 30 dias)")
    console.print()

    if not offers:
        if stats.get("already_applied") and not stats.get("offers_final"):
            console.print("  [yellow]![/yellow] Todas las ofertas ya fueron enviadas anteriormente.")
        else:
            console.print("  [yellow]![/yellow] No se encontraron ofertas con email de reclutador.")
        return

    _print_offers_table(offers)

    if export_fmt and export_path:
        _export_offers(offers, export_fmt, export_path)

    # ── Seleccion de ofertas (si no es modo auto) ──
    if not auto_apply:
        console.print()
        console.print("  [bold]Selecciona ofertas:[/bold]  [dim]numeros separados por coma, 'all' para todas, 'q' cancelar[/dim]")
        while True:
            choice = Prompt.ask("  Aplicar a")
            if choice.strip().lower() == 'q':
                console.print("  [yellow]Cancelado.[/yellow]")
                return
            if choice.strip().lower() in ('all', 'todas', '*'):
                console.print(f"  [green]✓[/green] Todas ({len(offers)})")
                break
            try:
                indices = [int(x.strip()) - 1 for x in choice.split(",")]
                selected = [offers[i] for i in indices if 0 <= i < len(offers)]
                if selected:
                    offers = selected
                    console.print(f"  [green]✓[/green] {len(offers)} seleccionadas")
                    break
                else:
                    console.print(f"  [red]✗[/red] Ningun numero valido (rango: 1-{len(offers)})")
            except (ValueError, IndexError):
                console.print(f"  [red]✗[/red] Formato invalido. Ej: 1,3,5 o 'all'")

    # ── Fase 3: Generar y enviar ──
    console.print()
    phase3_label = "Generando CVs (dry-run, sin enviar)..." if dry_run else "Generando y enviando..."
    console.print(f"  [bold dim]{phase3_label}[/bold dim]")
    console.print()
    sent = 0
    generated = 0
    errors = 0
    results = []
    preview_send_all = False

    total = len(offers)
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

    record_run(kb, mode, posts=stats["posts_scraped"], offers=len(offers), sent=sent,
               generated=generated, dry_run=dry_run)

    # Resumen
    err_str = f"[red]{errors}[/red]" if errors else "[dim]0[/dim]"
    if dry_run:
        summary_body = (
            f"  [dim]Posts scraped[/dim]       {stats['posts_scraped']}\n"
            f"  [dim]Analizados[/dim]          {stats['posts_with_emails']}  [dim](con email)[/dim]\n"
            f"  [dim]Ofertas[/dim]             {len(offers)}\n"
            f"  [dim]Generados[/dim]           [bold]{generated}[/bold]  [dim](CV + email)[/dim]\n"
            f"  [dim]Enviados[/dim]            [bold]0[/bold]  [dim](dry-run)[/dim]\n"
            f"  [dim]Errores[/dim]             {err_str}"
        )
    else:
        summary_body = (
            f"  [dim]Posts scraped[/dim]       {stats['posts_scraped']}\n"
            f"  [dim]Analizados[/dim]          {stats['posts_with_emails']}  [dim](con email)[/dim]\n"
            f"  [dim]Ofertas[/dim]             {len(offers)}\n"
            f"  [dim]Enviados[/dim]            [bold green]{sent}[/bold green]\n"
            f"  [dim]Errores[/dim]             {err_str}"
        )
    console.print(Panel(
        summary_body,
        border_style="green" if errors == 0 else "yellow", title="[bold]Resumen[/bold]"
    ))

    write_run_log(mode, stats, decisions, results, sent, errors)
