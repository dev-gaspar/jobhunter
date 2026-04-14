# -*- coding: utf-8 -*-
"""Entry point de JobHunter: parsea argv y dispatcha al comando correspondiente."""
import sys

from jobhunter.banner import get_banner
from jobhunter.cli.blacklist import cmd_blacklist
from jobhunter.cli.help import cmd_help
from jobhunter.cli.login import cmd_login
from jobhunter.cli.optimize import cmd_optimize
from jobhunter.cli.setup import cmd_setup
from jobhunter.cli.status import cmd_status
from jobhunter.cli.history import cmd_history
from jobhunter.config import is_configured
from jobhunter.pipeline import cmd_run
from jobhunter.ui import console
from jobhunter.updater import check_for_updates, cmd_update


def parse_time_filter(args):
    """Extrae --time de argv. Default: 24h. Falla con exit(1) si el valor es invalido."""
    for i, a in enumerate(args):
        if a == "--time" and i + 1 < len(args):
            val = args[i + 1]
            if val in ("24h", "week", "month"):
                return val
            else:
                console.print(f"  [red]\u2717[/red] Filtro invalido: {val}  [dim](opciones: 24h, week, month)[/dim]")
                sys.exit(1)
    return "24h"


def main():
    check_for_updates()

    if len(sys.argv) < 2:
        if not is_configured():
            cmd_setup()
        else:
            cmd_help()
        return

    cmd = sys.argv[1]
    tf = parse_time_filter(sys.argv)
    auto = "--auto" in sys.argv
    dry = "--dry" in sys.argv

    export = None
    export_path = None
    for i, a in enumerate(sys.argv):
        if a == "--export" and i + 1 < len(sys.argv) and sys.argv[i + 1] in ("csv", "json"):
            export = sys.argv[i + 1]
            export_path = sys.argv[i + 2] if i + 2 < len(sys.argv) and not sys.argv[i + 2].startswith("--") else None

    if cmd in ("setup",):
        cmd_setup()
    elif cmd in ("login",):
        cmd_login()
    elif cmd in ("optimize",):
        user_prompt = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
        cmd_optimize(user_prompt)
    elif cmd in ("history",):
        last = 10
        company_filter = None
        since = None
        show_all = "--all" in sys.argv
        for i, a in enumerate(sys.argv):
            if a == "--last" and i + 1 < len(sys.argv):
                try:
                    last = int(sys.argv[i + 1])
                except ValueError:
                    pass
            elif a == "--company" and i + 1 < len(sys.argv):
                company_filter = sys.argv[i + 1]
            elif a == "--since" and i + 1 < len(sys.argv):
                since = sys.argv[i + 1]
        cmd_history(last=last, company_filter=company_filter, since=since, show_all=show_all)
    elif cmd in ("blacklist",):
        action = sys.argv[2] if len(sys.argv) > 2 else None
        company = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_blacklist(action, company)
    elif cmd in ("status",):
        cmd_status()
    elif cmd in ("update",):
        cmd_update()
    elif cmd in ("help", "--help", "-h"):
        cmd_help()
    elif cmd == "--test" and len(sys.argv) > 2:
        if export and not export_path:
            console.print("  [red]![/red] --export requiere ruta. Ej: jobhunter --test email --export csv ofertas.csv")
            return
        cmd_run(
            test_email=sys.argv[2],
            time_filter=tf,
            auto_apply=auto,
            dry_run=dry,
            export_fmt=export,
            export_path=export_path,
        )
    elif cmd in ("run",):
        if export and not export_path:
            console.print("  [red]![/red] --export requiere ruta. Ej: jobhunter run --export csv ofertas.csv")
            return
        cmd_run(
            time_filter=tf,
            auto_apply=auto,
            dry_run=dry,
            export_fmt=export,
            export_path=export_path,
        )
    else:
        console.print(get_banner())
        console.print(f"  [red]\u2717[/red] Comando desconocido: [bold]{cmd}[/bold]")
        console.print("  [dim]Ejecuta 'jobhunter help' para ver comandos[/dim]")
        console.print()
