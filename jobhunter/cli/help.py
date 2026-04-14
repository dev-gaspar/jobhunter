# -*- coding: utf-8 -*-
"""Comando help: tabla de comandos, opciones y ejemplos."""
from rich.panel import Panel
from rich.table import Table

from jobhunter.banner import get_banner
from jobhunter.ui import console


def cmd_help():
    console.print(get_banner())

    cmds = Table(show_header=False, border_style="cyan", padding=(0, 2), expand=False)
    cmds.add_column("cmd", style="cyan", width=32)
    cmds.add_column("desc")
    cmds.add_row("jobhunter setup", "Configuracion inicial")
    cmds.add_row("jobhunter login", "Iniciar sesion en LinkedIn")
    cmds.add_row("jobhunter --test email@test.com", "Modo prueba (envia a tu correo)")
    cmds.add_row("jobhunter run", "Buscar y enviar a reclutadores")
    cmds.add_row("jobhunter optimize", "Optimizar queries con IA")
    cmds.add_row('jobhunter optimize "..."', "Optimizar con feedback tuyo")
    cmds.add_row("jobhunter history", "Historial de aplicaciones")
    cmds.add_row("jobhunter blacklist", "Ver/agregar/quitar empresas bloqueadas")
    cmds.add_row("jobhunter status", "Ver configuracion y estadisticas")
    cmds.add_row("jobhunter update", "Actualizar desde GitHub")
    cmds.add_row("jobhunter help", "Mostrar esta ayuda")
    console.print(Panel(cmds, border_style="cyan", title="[bold]Comandos[/bold]"))

    opts = Table(show_header=False, border_style="dim", padding=(0, 2), expand=False)
    opts.add_column("opt", style="cyan", width=20)
    opts.add_column("desc")
    opts.add_row("--time 24h", "Ultimas 24 horas [dim](defecto)[/dim]")
    opts.add_row("--time week", "Esta semana")
    opts.add_row("--time month", "Este mes")
    opts.add_row("--auto", "Aplicar a todas sin preguntar")
    opts.add_row("--dry", "Generar CVs y emails sin enviar [dim](run / --test)[/dim]")
    opts.add_row("--export csv|json ruta", "Exportar ofertas a archivo [dim](run)[/dim]")
    opts.add_row("--last N", "Ultimas N aplicaciones [dim](history)[/dim]")
    opts.add_row('--company "..."', "Filtrar por empresa [dim](history)[/dim]")
    opts.add_row("--since YYYY-MM-DD", "Desde fecha [dim](history)[/dim]")
    opts.add_row("--all", "Mostrar todas [dim](history)[/dim]")
    console.print(Panel(opts, border_style="dim", title="[bold]Opciones[/bold]"))

    console.print("  [bold]Seleccion de ofertas[/bold]")
    console.print("  [dim]Despues del analisis puedes elegir a cuales aplicar:[/dim]")
    console.print("  [cyan]1,3,5[/cyan]  Solo esas  \u00b7  [cyan]all[/cyan]  Todas  \u00b7  [cyan]q[/cyan]  Cancelar")
    console.print()
    console.print("  [bold]Preview antes de enviar[/bold]  [dim](sin --auto ni --dry)[/dim]")
    console.print("  Tras generar CV y email: [cyan]s[/cyan] enviar \u00b7 [cyan]x[/cyan] saltar \u00b7 [cyan]e[/cyan] editar asunto \u00b7 [cyan]a[/cyan] enviar todos")
    console.print()

    console.print("  [bold]Ejemplos[/bold]")
    console.print("  [dim]$ jobhunter --test mi@email.com[/dim]")
    console.print("  [dim]$ jobhunter run --time week[/dim]")
    console.print("  [dim]$ jobhunter run --auto[/dim]")
    console.print("  [dim]$ jobhunter run --time month --auto[/dim]")
    console.print("  [dim]$ jobhunter run --dry --time week[/dim]")
    console.print("  [dim]$ jobhunter optimize[/dim]")
    console.print('  [dim]$ jobhunter optimize "no encuentro ofertas remotas"[/dim]')
    console.print()
