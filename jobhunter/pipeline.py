# -*- coding: utf-8 -*-
"""Pipeline principal: scrape LinkedIn -> filtrar -> generar CV/email -> enviar.

Orquesta las 3 fases sobre los adapters (scraper, agents, mailer) y persiste
el historial en knowledge.json. Se invoca desde cli/main via cmd_run.
"""
import base64
import csv
import json
import os
import time
from datetime import datetime

from playwright.sync_api import sync_playwright
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from jobhunter.cv.builder import generate_cv_pdf, get_cv_filename
from jobhunter.offers import (
    deduplicate_offers_by_title_company,
    extract_emails,
    was_already_applied,
)

from jobhunter.agents.cv import agent_cv
from jobhunter.agents.email import agent_email
from jobhunter.agents.filter import agent_filter
from jobhunter.banner import get_banner
from jobhunter.browser import find_chrome, kill_playwright_zombies
from jobhunter.config import is_configured, load_config
from jobhunter.constants import BASE_DIR, SESSION_DIR
from jobhunter.mailer import send_email
from jobhunter.scraper import scrape_posts
from jobhunter.storage import load_kb, save_kb
from jobhunter.ui import console


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

    kill_playwright_zombies()
    queries = cfg.get("search_queries", ["enviar CV backend developer"])

    # ── Phase 1: Scrape ──
    console.print()
    console.print("  [bold dim]Buscando en LinkedIn...[/bold dim]")
    all_posts = []
    seen = set()

    try:
        with sync_playwright() as p:
            chrome = find_chrome()
            browser = p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR, headless=True,
                viewport={"width":1300,"height":850}, executable_path=chrome,
            )
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            if "login" in page.url or "signin" in page.url:
                console.print("  [red]![/red] Sesion expirada. Ejecuta: [cyan]jobhunter login[/cyan]")
                browser.close(); return

            total_q = len(queries)
            total_emails_found = 0
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=30),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                console=console,
            ) as prog:
                task = prog.add_task("Buscando...", total=total_q)
                for qi, query in enumerate(queries, 1):
                    prog.update(task, description=f"[dim]{query[:45]}[/dim]")
                    posts = scrape_posts(page, query, time_filter=time_filter)
                    for pi in posts:
                        key = pi["text"][:150]
                        if key not in seen:
                            seen.add(key)
                            all_posts.append(pi)
                    total_emails_found = sum(len(p.get("emails_found",[])) for p in all_posts)
                    prog.advance(task)
                    time.sleep(random.uniform(2, 5))

            # Screenshots (optional, quick)
            text_boxes = page.query_selector_all('span[data-testid="expandable-text-box"]')
            for post in all_posts:
                post["screenshots"] = []
                try:
                    if post["index"] < len(text_boxes):
                        ss = text_boxes[post["index"]].screenshot()
                        post["screenshots"].append(base64.b64encode(ss).decode())
                except: pass

            browser.close()
    except KeyboardInterrupt:
        console.print("\n  [dim]Cancelado.[/dim]")
        return
    except Exception:
        pass

    posts_with_emails = [p for p in all_posts if p.get("emails_found")]
    posts_no_emails = len(all_posts) - len(posts_with_emails)
    console.print(f"  [bold]{len(all_posts)}[/bold] posts  ·  [bold]{len(posts_with_emails)}[/bold] con email  ·  [dim]{posts_no_emails} sin email (omitidos)[/dim]")

    if not posts_with_emails:
        console.print()
        console.print("  [yellow]![/yellow] No se encontraron posts con email. Intenta un periodo mas amplio.")
        console.print("    [dim]Ej: jobhunter run --time week[/dim]")
        return

    # ── Phase 2: Analyze (only posts with emails to save tokens) ──
    console.print()
    console.print("  [bold dim]Analizando ofertas...[/bold dim]")
    offers = []

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), TextColumn("{task.completed}/{task.total}"),
                  TimeElapsedColumn(), console=console) as prog:
        task = prog.add_task("Analizando...", total=len(posts_with_emails))
        for post in posts_with_emails:
            if len(post.get("text","")) < 50:
                prog.advance(task); continue
            ss = post.get("screenshots",[None])[0] if post.get("screenshots") else None
            a = agent_filter(cfg, post["text"], ss)
            if a.get("is_job") and a.get("is_relevant", True):
                a["job_title"] = a.get("job_title") or "Software Developer"
                a["company"] = a.get("company") or "Empresa"
                a["post_url"] = post.get("post_url")
                offers.append(a)
            prog.advance(task)
            time.sleep(1.5)

    # Clean emails: remove "null", "none", empty strings
    for o in offers:
        email = o.get("contact_email", "")
        if not email or email.lower() in ("null", "none", "n/a", "no encontrado"):
            o["contact_email"] = None

    # Only keep offers with valid email
    offers_with_email = [o for o in offers if o.get("contact_email")]
    offers_no_email = [o for o in offers if not o.get("contact_email")]

    # Deduplicate within this batch: same normalized title + company
    deduped = deduplicate_offers_by_title_company(offers_with_email)
    batch_dupes = len(offers_with_email) - len(deduped)
    offers_with_email = deduped

    # Filter blacklisted companies
    rejected = [r.lower() for r in kb.get("rejected_companies", [])]
    before_bl = len(offers_with_email)
    offers_with_email = [o for o in offers_with_email if (o.get("company") or "").lower() not in rejected]
    blacklisted = before_bl - len(offers_with_email)
    blacklist_info = "  ·  " + str(blacklisted) + " bloqueadas" if blacklisted else ""

    console.print(
        f"  [bold]{len(offers)}[/bold] ofertas  ·  "
        f"[green]{len(offers_with_email)}[/green] con email  ·  "
        f"[dim]{batch_dupes} duplicadas  ·  {len(offers_no_email)} sin email{blacklist_info}[/dim]"
    )
    console.print()

    if offers_with_email:
        tw = shutil.get_terminal_size((80, 24)).columns
        wide = tw >= 100
        extra_wide = tw >= 130
        table = Table(border_style="cyan", title="[bold]Ofertas encontradas[/bold]", expand=False, show_lines=False, padding=(0, 1))
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
        table.add_column("Post", width=6, justify="center")
        mode_icons = {"remote": "[green]Remoto[/green]", "hybrid": "[yellow]Hibrido[/yellow]", "onsite": "[red]Onsite[/red]", "unknown": "[dim]—[/dim]"}
        for i, o in enumerate(offers_with_email, 1):
            wm = mode_icons.get(o.get("work_mode", "unknown"), "[dim]—[/dim]")
            loc = o.get("location") or "—"
            if loc.lower() in ("null", "none", "n/a", "no especificado", "no mencionado"):
                loc = "—"
            la = (o.get("language", "?"))[:4].upper()
            salary = o.get("salary") or "—"
            if str(salary).lower() in ("null", "none", "n/a", "no mencionado", "no especificado"):
                salary = "—"
            post_link = f"[link={o['post_url']}]Ver[/link]" if o.get("post_url") else "[dim]—[/dim]"
            if extra_wide:
                table.add_row(str(i), o["job_title"][:28], o["company"][:16], wm, loc[:18], la, str(salary)[:18], o["contact_email"], post_link)
            elif wide:
                table.add_row(str(i), o["job_title"][:28], o["company"][:16], wm, loc[:18], la, o["contact_email"], post_link)
            else:
                table.add_row(str(i), o["job_title"][:20], o["company"][:12], wm, o["contact_email"], post_link)
        console.print(table)

    if not offers_with_email:
        console.print("  [yellow]![/yellow] No se encontraron ofertas con email de reclutador.")
        return

    # Filter duplicates: skip if same job_title + company was already applied within 30 days
    before_dedup = len(offers_with_email)
    offers_with_email = [
        o for o in offers_with_email
        if not was_already_applied(kb.get("applications", []), o.get("company", ""), o.get("job_title", ""))
    ]
    skipped = before_dedup - len(offers_with_email)
    if skipped:
        console.print(f"  [yellow]![/yellow] {skipped} omitidas (ya enviadas en los ultimos 30 dias)")

    if not offers_with_email:
        console.print("  [yellow]![/yellow] Todas las ofertas ya fueron enviadas anteriormente.")
        return

    # Export offers if requested
    if export_fmt and export_path and offers_with_email:
        os.makedirs(os.path.dirname(os.path.abspath(export_path)) or ".", exist_ok=True)
        export_fields = ["job_title", "company", "contact_email", "work_mode", "location", "salary", "language", "post_url"]
        if export_fmt == "csv":
            import csv
            with open(export_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=export_fields, extrasaction="ignore")
                w.writeheader()
                w.writerows(offers_with_email)
            console.print(f"  [green]>[/green] Exportado: {export_path}")
        elif export_fmt == "json":
            export_data = [{k: o.get(k) for k in export_fields} for o in offers_with_email]
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            console.print(f"  [green]>[/green] Exportado: {export_path}")

    # Use only offers with valid email for Phase 3
    offers = offers_with_email

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

    # ── Phase 3: Generate & Send ──
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
        rec_email = job.get("contact_email")
        to = test_email or rec_email
        label = f"  [cyan]{i}[/cyan][dim]/{total}[/dim] {title} [dim]→[/dim] {company}"

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
                    except Exception as e:
                        if retry == 2:
                            raise
                        time.sleep(5)

                status.update(f"{label}  [dim]Email...[/dim]")
                for retry in range(3):
                    try:
                        edata = agent_email(cfg, job, cv_data=cv_data)
                        break
                    except Exception as e:
                        if retry == 2:
                            raise
                        time.sleep(5)
        except Exception as e:
            console.print(f"{label}  [red]! {e}[/red]")
            errors += 1
            results.append({
                "job_title": title,
                "company": company,
                "recruiter_email": rec_email,
                "sent_to": to,
                "cv_path": cv_path,
            })
            time.sleep(2)
            continue

        body = edata["body"]
        if test_email:
            body = f"--- RECLUTADOR: {job.get('contact_name','?')} | EMAIL: {rec_email or '?'} | {company} ---\n\n" + body

        cv_name = os.path.basename(cv_path) if cv_path else ""

        if dry_run:
            generated += 1
            preview_text = (
                f"Para: {to}\n"
                f"Asunto: {edata['subject']}\n"
                f"CV adjunto: {cv_name or '—'}\n\n"
                f"{body}"
            )
            console.print(Panel(preview_text, border_style="dim", title="[dim]Dry run[/dim]"))
            console.print("       [yellow]·[/yellow] Dry-run: no se envia email (no se guarda en historial)")
            results.append({
                "job_title": title,
                "company": company,
                "recruiter_email": rec_email,
                "sent_to": to,
                "cv_path": cv_path,
                "dry_run": True,
            })
            console.print()
            time.sleep(2)
            continue

        do_send = False
        if auto_apply or preview_send_all:
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
            results.append({
                "job_title": title,
                "company": company,
                "recruiter_email": rec_email,
                "sent_to": to,
                "cv_path": cv_path,
                "skipped": True,
            })
            console.print()
            time.sleep(1)
            continue

        try:
            send_email(cfg, to, edata["subject"], body, cv_path)
            sent += 1
            console.print(f"{label}  [green]> Enviado[/green] [dim]→ {to}[/dim]")
            kb["applications"].append({
                "date": datetime.now().isoformat(),
                "job_title": title,
                "company": company,
                "recruiter_email": rec_email,
                "sent_to": to,
                "mode": mode,
                "post_url": job.get("post_url"),
            })
        except Exception as e:
            console.print(f"{label}  [red]! {e}[/red]")
            errors += 1

        results.append({
            "job_title": title,
            "company": company,
            "recruiter_email": rec_email,
            "sent_to": to,
            "cv_path": cv_path,
        })
        time.sleep(2)

    run_entry = {
        "date": datetime.now().isoformat(),
        "mode": "dry-run" if dry_run else mode,
        "posts": len(all_posts),
        "offers": len(offers),
        "sent": 0 if dry_run else sent,
    }
    if dry_run:
        run_entry["generated"] = generated
    kb["runs"].append(run_entry)
    save_kb(kb)

    # Summary
    err_str = f"[red]{errors}[/red]" if errors else "[dim]0[/dim]"
    if dry_run:
        summary_body = (
            f"  [dim]Posts scraped[/dim]       {len(all_posts)}\n"
            f"  [dim]Analizados[/dim]          {len(posts_with_emails)}  [dim](con email)[/dim]\n"
            f"  [dim]Ofertas[/dim]             {len(offers)}\n"
            f"  [dim]Generados[/dim]           [bold]{generated}[/bold]  [dim](CV + email)[/dim]\n"
            f"  [dim]Enviados[/dim]            [bold]0[/bold]  [dim](dry-run)[/dim]\n"
            f"  [dim]Errores[/dim]             {err_str}"
        )
    else:
        summary_body = (
            f"  [dim]Posts scraped[/dim]       {len(all_posts)}\n"
            f"  [dim]Analizados[/dim]          {len(posts_with_emails)}  [dim](con email)[/dim]\n"
            f"  [dim]Ofertas[/dim]             {len(offers)}\n"
            f"  [dim]Enviados[/dim]            [bold green]{sent}[/bold green]\n"
            f"  [dim]Errores[/dim]             {err_str}"
        )
    console.print(Panel(
        summary_body,
        border_style="green" if errors == 0 else "yellow", title="[bold]Resumen[/bold]"
    ))

    log = os.path.join(BASE_DIR, "output", "logs", f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


