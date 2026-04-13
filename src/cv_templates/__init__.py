"""CV Template registry — each template exports a generate() function."""

from src.cv_templates.modern import generate as modern_generate
from src.cv_templates.minimal import generate as minimal_generate
from src.cv_templates.classic import generate as classic_generate
from src.cv_templates.compact import generate as compact_generate

TEMPLATES = {
    "modern": {"name": "Modern", "description": "Limpio con acentos de color", "generate": modern_generate},
    "minimal": {"name": "Minimal", "description": "Espacioso, lineas finas, elegante", "generate": minimal_generate},
    "classic": {"name": "Classic", "description": "Tradicional con fuente serif", "generate": classic_generate},
    "compact": {"name": "Compact", "description": "Denso, mas contenido por pagina", "generate": compact_generate},
}

DEFAULT_TEMPLATE = "modern"


def get_template(name: str):
    return TEMPLATES.get(name, TEMPLATES[DEFAULT_TEMPLATE])
