"""
CV PDF Builder - Generates professional PDF CVs using ReportLab
"""

import os, re
from datetime import datetime


def _normalize_ats(text: str) -> str:
    """Normalize Unicode characters that ATS parsers handle poorly."""
    t = str(text)
    t = t.replace("\u2014", "-").replace("\u2013", "-")        # em/en dash
    t = t.replace("\u2018", "'").replace("\u2019", "'")        # smart single quotes
    t = t.replace("\u201c", '"').replace("\u201d", '"')        # smart double quotes
    t = t.replace("\u2026", "...")                              # ellipsis
    t = t.replace("\u00a0", " ")                               # non-breaking space
    t = t.replace("\u200b", "").replace("\ufeff", "")          # zero-width chars
    t = t.replace("\u2022", "-")                               # bullet
    t = t.replace("\u00b7", "-")                               # middle dot
    return t


def _clean_markdown(text: str) -> str:
    """Remove all markdown formatting from text."""
    t = str(text)
    t = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', t)  # ***bold italic***
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)        # **bold**
    t = re.sub(r'\*(.+?)\*', r'\1', t)             # *italic*
    t = re.sub(r'__(.+?)__', r'\1', t)             # __bold__
    t = re.sub(r'_(.+?)_', r'\1', t)               # _italic_
    t = re.sub(r'`(.+?)`', r'\1', t)               # `code`
    t = re.sub(r'^#{1,6}\s+', '', t, flags=re.MULTILINE)  # # headers
    t = re.sub(r'^\s*[-*+]\s+', '', t, flags=re.MULTILINE)  # - list items
    t = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', t)      # [link](url)
    return t


def _safe(text: str) -> str:
    """Clean markdown, normalize ATS chars, and escape XML for ReportLab."""
    t = _clean_markdown(text)
    t = _normalize_ats(t)
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def safe_header_name(profile: dict, cv_data: dict) -> str:
    """Nombre para el encabezado si falta profile.name (evita KeyError)."""
    return (profile.get("name") or cv_data.get("title") or "Candidato").strip() or "Candidato"


SECTION_LABELS = {
    "es": {"summary": "RESUMEN PROFESIONAL", "skills": "HABILIDADES TECNICAS", "experience": "EXPERIENCIA PROFESIONAL", "projects": "PROYECTOS CLAVE", "education": "EDUCACION"},
    "en": {"summary": "PROFESSIONAL SUMMARY", "skills": "TECHNICAL SKILLS", "experience": "PROFESSIONAL EXPERIENCE", "projects": "KEY PROJECTS", "education": "EDUCATION"},
    "pt": {"summary": "RESUMO PROFISSIONAL", "skills": "HABILIDADES TECNICAS", "experience": "EXPERIENCIA PROFISSIONAL", "projects": "PROJETOS CHAVE", "education": "EDUCACAO"},
    "fr": {"summary": "RESUME PROFESSIONNEL", "skills": "COMPETENCES TECHNIQUES", "experience": "EXPERIENCE PROFESSIONNELLE", "projects": "PROJETS CLES", "education": "FORMATION"},
    "de": {"summary": "BERUFSPROFIL", "skills": "FACHKENNTNISSE", "experience": "BERUFSERFAHRUNG", "projects": "SCHLUSSELPROJEKTE", "education": "AUSBILDUNG"},
}


def generate_cv_pdf(
    cv_data: dict,
    profile: dict,
    output_path: str,
    job_title: str = "",
    company: str = "",
    language: str = "es",
    template: str = "modern",
):
    """Generate a professional PDF CV using the specified template."""
    from jobhunter.cv.templates import get_template
    tmpl = get_template(template)
    return tmpl["generate"](cv_data, profile, output_path, job_title, company, language)


def get_cv_filename(company: str, job_title: str) -> str:
    """Generate a clean filename for the CV."""
    clean = (
        lambda s: "".join(c if c.isalnum() or c in " -_" else "" for c in s)
        .strip()
        .replace(" ", "_")
    )
    timestamp = datetime.now().strftime("%Y%m%d")
    company_part = clean(company)[:40]
    title_part = clean(job_title)[:80]
    return f"CV_{company_part}_{title_part}_{timestamp}.pdf"
