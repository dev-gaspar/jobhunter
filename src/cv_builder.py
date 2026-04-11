"""
CV PDF Builder - Generates professional PDF CVs using ReportLab
"""

import os, re
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY


# Color scheme
PRIMARY = HexColor("#1a1a2e")
ACCENT = HexColor("#0f3460")
TEXT_DARK = HexColor("#2d2d2d")
TEXT_LIGHT = HexColor("#555555")
LINE_COLOR = HexColor("#cccccc")


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
    """Clean markdown and escape XML special chars for ReportLab Paragraph."""
    t = _clean_markdown(text)
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_styles():
    """Create custom paragraph styles for the CV."""
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="CVName",
            fontName="Helvetica-Bold",
            fontSize=20,
            textColor=PRIMARY,
            spaceAfter=6,
            leading=24,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVTitle",
            fontName="Helvetica",
            fontSize=10,
            textColor=ACCENT,
            spaceAfter=6,
            leading=13,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVContact",
            fontName="Helvetica",
            fontSize=8,
            textColor=TEXT_LIGHT,
            spaceAfter=10,
            leading=11,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVSection",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=PRIMARY,
            spaceBefore=12,
            spaceAfter=4,
            leading=13,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVSummary",
            fontName="Helvetica",
            fontSize=9,
            textColor=TEXT_DARK,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            leading=13,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVCompany",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=TEXT_DARK,
            spaceAfter=1,
            leading=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVPeriod",
            fontName="Helvetica",
            fontSize=8,
            textColor=TEXT_LIGHT,
            spaceAfter=3,
            leading=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVBullet",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=TEXT_DARK,
            leftIndent=12,
            spaceAfter=2,
            leading=11,
            alignment=TA_JUSTIFY,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVSkill",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=TEXT_DARK,
            spaceAfter=4,
            leading=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CVProject",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=TEXT_DARK,
            spaceAfter=3,
            leading=11,
        )
    )
    return styles


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
):
    """Generate a professional PDF CV."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    labels = SECTION_LABELS.get(language, SECTION_LABELS["es"])

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = build_styles()
    story = []

    # === HEADER ===
    display_name = (profile.get("name") or cv_data.get("title") or "Candidato").strip() or "Candidato"
    story.append(Paragraph(_safe(display_name), styles["CVName"]))
    story.append(Spacer(1, 2))
    story.append(
        Paragraph(
            _safe(cv_data.get("title") or profile.get("title") or ""),
            styles["CVTitle"],
        )
    )
    story.append(Spacer(1, 4))

    contact_parts = []
    if profile.get("email"):
        contact_parts.append(profile["email"])
    if profile.get("phone"):
        contact_parts.append(profile["phone"])
    if profile.get("linkedin"):
        contact_parts.append(profile["linkedin"])
    if profile.get("portfolio"):
        contact_parts.append(profile["portfolio"])
    if profile.get("location"):
        contact_parts.append(profile["location"])

    story.append(Paragraph(_safe(" | ".join(contact_parts)), styles["CVContact"]))
    story.append(HRFlowable(width="100%", thickness=1, color=LINE_COLOR, spaceAfter=8))

    # === RESUMEN PROFESIONAL ===
    story.append(Paragraph(labels["summary"], styles["CVSection"]))
    story.append(
        Paragraph(_safe(cv_data.get("summary") or ""), styles["CVSummary"])
    )

    # === HABILIDADES ===
    skills = cv_data.get("skills_highlighted", [])
    if skills:
        story.append(Paragraph(labels["skills"], styles["CVSection"]))
        story.append(
            HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4)
        )
        skills_text = _safe(" | ".join(skills))
        story.append(Paragraph(skills_text, styles["CVSkill"]))

    # === EXPERIENCIA ===
    experience = cv_data.get("experience", [])
    if experience:
        story.append(Paragraph(labels["experience"], styles["CVSection"]))
        story.append(
            HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4)
        )

        for exp in experience:
            company_name = _safe(exp.get("company") or "")
            role_name = _safe(exp.get("role") or "")
            story.append(
                Paragraph(
                    f"<b>{company_name}</b> — <i>{role_name}</i>", styles["CVCompany"]
                )
            )
            story.append(Paragraph(_safe(exp.get("period") or ""), styles["CVPeriod"]))

            for bullet in exp.get("bullets", []):
                story.append(Paragraph(f"- {_safe(bullet)}", styles["CVBullet"]))
            story.append(Spacer(1, 3))

    # === PROYECTOS ===
    projects = cv_data.get("projects", [])
    if projects:
        story.append(Paragraph(labels["projects"], styles["CVSection"]))
        story.append(
            HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4)
        )

        for proj in projects:
            tech_str = _safe(", ".join(proj.get("tech", [])))
            proj_name = _safe(proj.get("name") or "")
            proj_desc = _safe(proj.get("description") or "")
            story.append(
                Paragraph(
                    f"<b>{proj_name}</b> — {proj_desc} ({tech_str})",
                    styles["CVProject"],
                )
            )

    # === EDUCACION ===
    education = cv_data.get("education", profile.get("education", []))
    if education:
        story.append(Paragraph(labels["education"], styles["CVSection"]))
        story.append(
            HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4)
        )

        for edu in education:
            degree = _safe(edu.get("degree") or "")
            institution = _safe(edu.get("institution") or "")
            period = _safe(edu.get("period") or "")
            story.append(
                Paragraph(
                    f"<b>{degree}</b> — {institution} ({period})", styles["CVProject"]
                )
            )

    doc.build(story)
    return output_path


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
