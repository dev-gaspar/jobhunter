# -*- coding: utf-8 -*-
"""Comando network: cola asistida de reclutadores para ampliar la red.

Nunca automatiza acciones en LinkedIn: abre el perfil en el navegador por
defecto (donde el usuario tiene su sesion normal) y es el usuario quien da
clic en Conectar. Solo se lleva el registro en kb["network"].
"""
import urllib.parse
import webbrowser
from datetime import datetime

from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from jobhunter.banner import get_banner
from jobhunter.storage import load_kb, save_kb
from jobhunter.ui import console


def _name_from_url(url):
    """Nombre legible desde el slug del perfil cuando el post no lo trae.

    "nicolas-villalba-958a5b46" -> "Nicolas Villalba" (el token final con
    digitos es el id que LinkedIn agrega a slugs repetidos).
    """
    slug = urllib.parse.unquote((url or "").rstrip("/").rsplit("/in/", 1)[-1])
    parts = [p for p in slug.split("-") if p]
    if len(parts) > 1 and any(ch.isdigit() for ch in parts[-1]):
        parts = parts[:-1]
    return " ".join(p.capitalize() for p in parts) or "?"


def build_network_queue(applications, network):
    """Candidatos a conectar: autores de posts aplicados, sin repetir ni re-ofrecer."""
    seen = {n.get("profile_url") for n in (network or [])}
    queue = []
    ordered = sorted(applications or [], key=lambda x: x.get("date") or "", reverse=True)
    for a in ordered:
        url = a.get("author_url")
        if not url or url in seen:
            continue
        seen.add(url)
        queue.append({
            "profile_url": url,
            "name": a.get("author_name") or _name_from_url(url),
            "company": a.get("company") or "-",
            "job_title": a.get("job_title") or "-",
            "applied": (a.get("date") or "")[:10],
        })
    return queue


def cmd_network():
    kb = load_kb()
    console.print(get_banner())

    queue = build_network_queue(kb.get("applications", []), kb.get("network", []))
    if not queue:
        console.print("  [yellow]![/yellow] Sin candidatos por ahora.")
        console.print("    [dim]Los autores de los posts se capturan desde ahora en cada run/apply;[/dim]")
        console.print("    [dim]despues de tu proximo run tendras reclutadores aqui.[/dim]")
        return

    console.print(f"  [bold]{len(queue)}[/bold] reclutadores a los que ya aplicaste y aun no conectas")
    console.print("  [dim]Se abre el perfil en TU navegador y tu decides dar clic en Conectar.[/dim]")
    console.print("  [dim]Modera el ritmo: LinkedIn limita ~100 invitaciones/semana para todos.[/dim]")
    console.print()

    network = kb.setdefault("network", [])
    invited = 0
    for cand in queue:
        console.print(Panel(
            f"  [bold]{cand['name']}[/bold]\n"
            f"  [dim]Aplicaste a[/dim]  {cand['job_title']} [dim]en[/dim] {cand['company']} [dim]({cand['applied']})[/dim]\n"
            f"  [cyan]{cand['profile_url']}[/cyan]",
            border_style="cyan",
        ))
        choice = Prompt.ask("  (a) Abrir perfil  (x) Saltar  (q) Salir", default="a").strip().lower()
        if choice in ("q", "quit"):
            break
        entry = {
            "profile_url": cand["profile_url"],
            "name": cand["name"],
            "company": cand["company"],
            "date": datetime.now().isoformat(),
        }
        if choice in ("a", "abrir", ""):
            webbrowser.open(cand["profile_url"])
            sent = Confirm.ask("  Enviaste la invitacion?", default=True)
            entry["status"] = "invited" if sent else "skipped"
            if sent:
                invited += 1
        else:
            entry["status"] = "skipped"
        network.append(entry)
        console.print()

    save_kb(kb)
    console.print(f"  [green]✓[/green] {invited} invitaciones registradas  [dim]({len(network)} perfiles gestionados en total)[/dim]")
