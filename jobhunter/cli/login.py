# -*- coding: utf-8 -*-
"""Comando login: wrapper interactivo del flujo de sesion LinkedIn."""
from jobhunter.banner import get_banner
from jobhunter.scraper import do_linkedin_login
from jobhunter.ui import console


def cmd_login():
    console.print(get_banner())
    console.print()
    do_linkedin_login()
    console.print()
    console.print("  [bold]Siguiente paso:[/bold]")
    console.print("  [cyan]jobhunter --test tu@email.com[/cyan]  prueba")
    console.print("  [cyan]jobhunter run[/cyan]                   enviar a reclutadores")
    console.print()
