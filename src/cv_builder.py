"""
CV PDF Builder - Generates professional PDF CVs using ReportLab
"""

import os
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


def _safe(text: str) -> str:
    """Escape XML special chars for ReportLab Paragraph."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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


def generate_cv_pdf(
    cv_data: dict,
    profile: dict,
    output_path: str,
    job_title: str = "",
    company: str = "",
):
    """Generate a professional PDF CV."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

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
    story.append(Paragraph(_safe(profile["name"]), styles["CVName"]))
    story.append(Spacer(1, 2))
    story.append(
        Paragraph(_safe(cv_data.get("title", profile["title"])), styles["CVTitle"])
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
    story.append(Paragraph("RESUMEN PROFESIONAL", styles["CVSection"]))
    story.append(Paragraph(_safe(cv_data["summary"]), styles["CVSummary"]))

    # === HABILIDADES ===
    skills = cv_data.get("skills_highlighted", [])
    if skills:
        story.append(Paragraph("HABILIDADES TECNICAS", styles["CVSection"]))
        story.append(
            HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4)
        )
        skills_text = _safe(" | ".join(skills))
        story.append(Paragraph(skills_text, styles["CVSkill"]))

    # === EXPERIENCIA ===
    experience = cv_data.get("experience", [])
    if experience:
        story.append(Paragraph("EXPERIENCIA PROFESIONAL", styles["CVSection"]))
        story.append(
            HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4)
        )

        for exp in experience:
            company_name = _safe(exp["company"])
            role_name = _safe(exp["role"])
            story.append(
                Paragraph(
                    f"<b>{company_name}</b> — <i>{role_name}</i>", styles["CVCompany"]
                )
            )
            story.append(Paragraph(_safe(exp["period"]), styles["CVPeriod"]))

            for bullet in exp.get("bullets", []):
                story.append(Paragraph(f"- {_safe(bullet)}", styles["CVBullet"]))
            story.append(Spacer(1, 3))

    # === PROYECTOS ===
    projects = cv_data.get("projects", [])
    if projects:
        story.append(Paragraph("PROYECTOS CLAVE", styles["CVSection"]))
        story.append(
            HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4)
        )

        for proj in projects:
            tech_str = _safe(", ".join(proj.get("tech", [])))
            proj_name = _safe(proj["name"])
            proj_desc = _safe(proj["description"])
            story.append(
                Paragraph(
                    f"<b>{proj_name}</b> — {proj_desc} ({tech_str})",
                    styles["CVProject"],
                )
            )

    # === EDUCACION ===
    education = cv_data.get("education", profile.get("education", []))
    if education:
        story.append(Paragraph("EDUCACION", styles["CVSection"]))
        story.append(
            HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4)
        )

        for edu in education:
            degree = _safe(edu["degree"])
            institution = _safe(edu["institution"])
            period = _safe(edu["period"])
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
