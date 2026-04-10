"""Minimal template — spacious layout, thin lines, elegant."""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from src.cv_builder import _safe, SECTION_LABELS

PRIMARY = HexColor("#333333")
TEXT_DARK = HexColor("#444444")
TEXT_LIGHT = HexColor("#888888")
LINE_COLOR = HexColor("#dddddd")


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CVName", fontName="Helvetica", fontSize=22,
                              textColor=PRIMARY, spaceAfter=4, leading=26, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="CVTitle", fontName="Helvetica", fontSize=10,
                              textColor=TEXT_LIGHT, spaceAfter=6, leading=13, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="CVContact", fontName="Helvetica", fontSize=7.5,
                              textColor=TEXT_LIGHT, spaceAfter=14, leading=10, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="CVSection", fontName="Helvetica", fontSize=9,
                              textColor=PRIMARY, spaceBefore=14, spaceAfter=6, leading=12,
                              alignment=TA_LEFT, tracking=2))
    styles.add(ParagraphStyle(name="CVSummary", fontName="Helvetica", fontSize=8.5,
                              textColor=TEXT_DARK, spaceAfter=8, alignment=TA_JUSTIFY, leading=13))
    styles.add(ParagraphStyle(name="CVCompany", fontName="Helvetica-Bold", fontSize=8.5,
                              textColor=PRIMARY, spaceAfter=1, leading=11))
    styles.add(ParagraphStyle(name="CVPeriod", fontName="Helvetica", fontSize=7.5,
                              textColor=TEXT_LIGHT, spaceAfter=3, leading=10))
    styles.add(ParagraphStyle(name="CVBullet", fontName="Helvetica", fontSize=8,
                              textColor=TEXT_DARK, leftIndent=10, spaceAfter=2, leading=11, alignment=TA_JUSTIFY))
    styles.add(ParagraphStyle(name="CVSkill", fontName="Helvetica", fontSize=8,
                              textColor=TEXT_DARK, spaceAfter=4, leading=11))
    styles.add(ParagraphStyle(name="CVProject", fontName="Helvetica", fontSize=8,
                              textColor=TEXT_DARK, spaceAfter=3, leading=11))
    return styles


def generate(cv_data, profile, output_path, job_title="", company="", language="es"):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    labels = SECTION_LABELS.get(language, SECTION_LABELS["es"])

    doc = SimpleDocTemplate(output_path, pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.7*inch, bottomMargin=0.7*inch)
    styles = build_styles()
    story = []

    # Header — centered, minimal
    story.append(Paragraph(_safe(profile["name"]).upper(), styles["CVName"]))
    story.append(Paragraph(_safe(cv_data.get("title", profile.get("title", ""))), styles["CVTitle"]))

    contact_parts = [v for k in ("email", "phone", "linkedin", "portfolio", "location")
                     if (v := profile.get(k))]
    story.append(Paragraph(_safe("  /  ".join(contact_parts)), styles["CVContact"]))
    story.append(HRFlowable(width="100%", thickness=0.3, color=LINE_COLOR, spaceAfter=6))

    # Summary
    story.append(Paragraph(labels["summary"].upper(), styles["CVSection"]))
    story.append(Paragraph(_safe(cv_data["summary"]), styles["CVSummary"]))

    # Skills
    skills = cv_data.get("skills_highlighted", [])
    if skills:
        story.append(Paragraph(labels["skills"].upper(), styles["CVSection"]))
        story.append(Paragraph(_safe("  /  ".join(skills)), styles["CVSkill"]))

    # Experience
    experience = cv_data.get("experience", [])
    if experience:
        story.append(Paragraph(labels["experience"].upper(), styles["CVSection"]))
        for exp in experience:
            story.append(Paragraph(f"<b>{_safe(exp['company'])}</b>  -  {_safe(exp['role'])}", styles["CVCompany"]))
            story.append(Paragraph(_safe(exp["period"]), styles["CVPeriod"]))
            for bullet in exp.get("bullets", []):
                story.append(Paragraph(f"- {_safe(bullet)}", styles["CVBullet"]))
            story.append(Spacer(1, 6))

    # Projects
    projects = cv_data.get("projects", [])
    if projects:
        story.append(Paragraph(labels["projects"].upper(), styles["CVSection"]))
        for proj in projects:
            tech_str = _safe(", ".join(proj.get("tech", [])))
            story.append(Paragraph(f"<b>{_safe(proj['name'])}</b>  -  {_safe(proj['description'])} ({tech_str})", styles["CVProject"]))
            story.append(Spacer(1, 3))

    # Education
    education = cv_data.get("education", profile.get("education", []))
    if education:
        story.append(Paragraph(labels["education"].upper(), styles["CVSection"]))
        for edu in education:
            story.append(Paragraph(f"<b>{_safe(edu['degree'])}</b>  -  {_safe(edu['institution'])} ({_safe(edu['period'])})", styles["CVProject"]))

    # Languages
    languages = cv_data.get("languages", [])
    if languages:
        lang_label = {"es": "IDIOMAS", "en": "LANGUAGES", "pt": "IDIOMAS", "fr": "LANGUES", "de": "SPRACHEN"}.get(language, "IDIOMAS")
        story.append(Paragraph(lang_label, styles["CVSection"]))
        lang_text = "  /  ".join(f"{l['language']} ({l['level']})" for l in languages)
        story.append(Paragraph(_safe(lang_text), styles["CVSkill"]))

    doc.build(story)
    return output_path
