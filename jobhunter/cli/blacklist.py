# -*- coding: utf-8 -*-
"""Comando blacklist: gestiona lista de empresas rechazadas."""
from jobhunter.storage import load_kb, save_kb
from jobhunter.ui import console


def cmd_blacklist(action=None, company=None):
    """add/remove/list de empresas que no se contactaran."""
    kb = load_kb()
    rejected = kb.get("rejected_companies", [])

    if action == "add" and company:
        norm = company.strip()
        if norm.lower() in [r.lower() for r in rejected]:
            console.print(f"  [yellow]![/yellow] '{norm}' ya esta en la blacklist.")
        else:
            rejected.append(norm)
            kb["rejected_companies"] = rejected
            save_kb(kb)
            console.print(f"  [green]>[/green] '{norm}' agregada a la blacklist.")
    elif action == "remove" and company:
        norm = company.strip().lower()
        match = [r for r in rejected if r.lower() == norm]
        if match:
            rejected.remove(match[0])
            kb["rejected_companies"] = rejected
            save_kb(kb)
            console.print(f"  [green]>[/green] '{match[0]}' removida de la blacklist.")
        else:
            console.print(f"  [yellow]![/yellow] '{company}' no esta en la blacklist.")
    else:
        if not rejected:
            console.print('  [dim]Blacklist vacia. Usa: jobhunter blacklist add "Empresa"[/dim]')
            return
        console.print()
        for i, r in enumerate(rejected, 1):
            console.print(f"  [cyan]{i}.[/cyan] {r}")
        console.print(f"\n  [dim]{len(rejected)} empresas bloqueadas[/dim]")
        console.print()
