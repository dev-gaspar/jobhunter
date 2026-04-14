# -*- coding: utf-8 -*-
"""Comando update + aviso pasivo de nueva version disponible."""
import subprocess
import sys

from jobhunter.banner import get_banner
from jobhunter.constants import BASE_DIR
from jobhunter.ui import console


def cmd_update():
    """git pull --ff-only + reinstala dependencias silenciosamente."""
    console.print(get_banner())

    with console.status("  [dim]Buscando actualizaciones...[/dim]"):
        try:
            result = subprocess.run(
                ["git", "-C", BASE_DIR, "pull", "--ff-only"],
                capture_output=True, text=True, timeout=30,
            )
        except FileNotFoundError:
            console.print("  [red]\u2717[/red] git no esta instalado")
            return
        except subprocess.TimeoutExpired:
            console.print("  [red]\u2717[/red] Timeout al conectar con GitHub")
            return

    if result.returncode != 0:
        err = result.stderr.strip()
        console.print(f"  [red]\u2717[/red] Error: {err}")
        return

    output = result.stdout.strip()
    if "Already up to date" in output or "Ya esta actualizado" in output:
        console.print("  [green]\u2713[/green] Ya tienes la ultima version")
    else:
        console.print("  [green]\u2713[/green] Actualizado correctamente")
        console.print(f"    [dim]{output}[/dim]")

    with console.status("  [dim]Verificando dependencias...[/dim]"):
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet",
             "rich", "requests", "playwright", "reportlab"],
            capture_output=True,
        )

    console.print("  [green]\u2713[/green] Dependencias al dia")
    console.print()


def check_for_updates():
    """Aviso pasivo si el remoto tiene cambios. No bloquea ni pregunta."""
    try:
        result = subprocess.run(
            ["git", "-C", BASE_DIR, "fetch", "--dry-run"],
            capture_output=True, text=True, timeout=5,
        )
        if result.stderr.strip():
            console.print("  [cyan]\u2726[/cyan] Hay una nueva version disponible con mejoras y nuevas funciones")
            console.print("    [dim]Actualiza cuando quieras con[/dim] [cyan]jobhunter update[/cyan]\n")
    except Exception:
        pass
