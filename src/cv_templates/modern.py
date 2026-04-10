"""Modern template — clean layout with color accents (original design)."""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from src.cv_builder import _safe, SECTION_LABELS

PRIMARY = HexColor("#1a1a2e")
ACCENT = HexColor("#0f3460")
TEXT_DARK = HexColor("#2d2d2d")
TEXT_LIGHT = HexColor("#555555")
LINE_COLOR = HexColor("#cccccc")


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CVName", fontName="Helvetica-Bold", fontSize=20,
                              textColor=PRIMARY, spaceAfter=6, leading=24, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="CVTitle", fontName="Helvetica", fontSize=10,
                              textColor=ACCENT, spaceAfter=6, leading=13, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="CVContact", fontName="Helvetica", fontSize=8,
                              textColor=TEXT_LIGHT, spaceAfter=10, leading=11, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="CVSection", fontName="Helvetica-Bold", fontSize=10,
                              textColor=PRIMARY, spaceBefore=12, spaceAfter=4, leading=13, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="CVSummary", fontName="Helvetica", fontSize=9,
                              textColor=TEXT_DARK, spaceAfter=6, alignment=TA_JUSTIFY, leading=13))
    styles.add(ParagraphStyle(name="CVCompany", fontName="Helvetica-Bold", fontSize=9,
                              textColor=TEXT_DARK, spaceAfter=1, leading=12))
    styles.add(ParagraphStyle(name="CVPeriod", fontName="Helvetica", fontSize=8,
                              textColor=TEXT_LIGHT, spaceAfter=3, leading=10))
    styles.add(ParagraphStyle(name="CVBullet", fontName="Helvetica", fontSize=8.5,
                              textColor=TEXT_DARK, leftIndent=12, spaceAfter=2, leading=11, alignment=TA_JUSTIFY))
    styles.add(ParagraphStyle(name="CVSkill", fontName="Helvetica", fontSize=8.5,
                              textColor=TEXT_DARK, spaceAfter=4, leading=12))
    styles.add(ParagraphStyle(name="CVProject", fontName="Helvetica", fontSize=8.5,
                              textColor=TEXT_DARK, spaceAfter=3, leading=11))
    return styles


def generate(cv_data, profile, output_path, job_title="", company="", language="es"):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    labels = SECTION_LABELS.get(language, SECTION_LABELS["es"])

    doc = SimpleDocTemplate(output_path, pagesize=letter,
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = build_styles()
    story = []

    # Header
    story.append(Paragraph(_safe(profile["name"]), styles["CVName"]))
    story.append(Spacer(1, 2))
    story.append(Paragraph(_safe(cv_data.get("title", profile.get("title", ""))), styles["CVTitle"]))
    story.append(Spacer(1, 4))

    contact_parts = [v for k in ("email", "phone", "linkedin", "portfolio", "location")
                     if (v := profile.get(k))]
    story.append(Paragraph(_safe(" | ".join(contact_parts)), styles["CVContact"]))
    story.append(HRFlowable(width="100%", thickness=1, color=LINE_COLOR, spaceAfter=8))

    # Summary
    story.append(Paragraph(labels["summary"], styles["CVSection"]))
    story.append(Paragraph(_safe(cv_data["summary"]), styles["CVSummary"]))

    # Skills
    skills = cv_data.get("skills_highlighted", [])
    if skills:
        story.append(Paragraph(labels["skills"], styles["CVSection"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4))
        story.append(Paragraph(_safe(" | ".join(skills)), styles["CVSkill"]))

    # Experience
    for exp in cv_data.get("experience", []):
        if exp == cv_data["experience"][0]:
            story.append(Paragraph(labels["experience"], styles["CVSection"]))
            story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4))
        story.append(Paragraph(f"<b>{_safe(exp['company'])}</b> - <i>{_safe(exp['role'])}</i>", styles["CVCompany"]))
        story.append(Paragraph(_safe(exp["period"]), styles["CVPeriod"]))
        for bullet in exp.get("bullets", []):
            story.append(Paragraph(f"- {_safe(bullet)}", styles["CVBullet"]))
        story.append(Spacer(1, 3))

    # Projects
    projects = cv_data.get("projects", [])
    if projects:
        story.append(Paragraph(labels["projects"], styles["CVSection"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4))
        for proj in projects:
            tech_str = _safe(", ".join(proj.get("tech", [])))
            story.append(Paragraph(f"<b>{_safe(proj['name'])}</b> - {_safe(proj['description'])} ({tech_str})", styles["CVProject"]))

    # Education
    education = cv_data.get("education", profile.get("education", []))
    if education:
        story.append(Paragraph(labels["education"], styles["CVSection"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4))
        for edu in education:
            story.append(Paragraph(f"<b>{_safe(edu['degree'])}</b> - {_safe(edu['institution'])} ({_safe(edu['period'])})", styles["CVProject"]))

    # Languages
    languages = cv_data.get("languages", [])
    if languages:
        lang_label = {"es": "IDIOMAS", "en": "LANGUAGES", "pt": "IDIOMAS", "fr": "LANGUES", "de": "SPRACHEN"}.get(language, "IDIOMAS")
        story.append(Paragraph(lang_label, styles["CVSection"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4))
        lang_text = " | ".join(f"{l['language']} ({l['level']})" for l in languages)
        story.append(Paragraph(_safe(lang_text), styles["CVSkill"]))

    doc.build(story)
    return output_path
