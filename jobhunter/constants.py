"""Constantes globales de JobHunter: versiones, paths, banners, modelos."""
import os

# BASE_DIR apunta a la raiz del proyecto (un nivel arriba de jobhunter/).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SESSION_DIR = os.path.join(BASE_DIR, ".session")
KB_PATH = os.path.join(BASE_DIR, "knowledge.json")

VERSION = "1.2.0"

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite-preview",
]

TIME_FILTERS = {
    "24h": "past-24h",
    "week": "past-week",
    "month": "past-month",
}

BACK = "<"

BANNER_LARGE = """\
[bold cyan]
      ╦╔═╗╔╗  ╦ ╦╦ ╦╔╗╔╔╦╗╔═╗╦═╗
      ║║ ║╠╩╗ ╠═╣║ ║║║║ ║ ║╣ ╠╦╝
     ╚╝╚═╝╚═╝ ╩ ╩╚═╝╝╚╝ ╩ ╚═╝╩╚═ [white]AI[/white][/bold cyan]
[dim]  ──────────────────────────────────────
  Busqueda de empleo automatizada con IA
  Playwright + Gemini + Gmail  •  v{version}[/dim]
"""

BANNER_SMALL = """\
[bold cyan]  ╦╔═╗╔╗ ╦ ╦╦ ╦╔╗╔╔╦╗╔═╗╦═╗ [white]AI[/white]
  ║║ ║╠╩╗╠═╣║ ║║║║ ║ ║╣ ╠╦╝
 ╚╝╚═╝╚═╝╩ ╩╚═╝╝╚╝ ╩ ╚═╝╩╚═[/bold cyan]
[dim]  v{version}[/dim]
"""
