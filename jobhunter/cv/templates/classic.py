"""Classic template — traditional serif font, conservative layout."""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from jobhunter.cv.builder import _safe, SECTION_LABELS, safe_header_name

PRIMARY = HexColor("#1a1a1a")
ACCENT = HexColor("#8b0000")
TEXT_DARK = HexColor("#2d2d2d")
TEXT_LIGHT = HexColor("#666666")
LINE_COLOR = HexColor("#999999")


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CVName", fontName="Times-Bold", fontSize=22,
                              textColor=PRIMARY, spaceAfter=4, leading=26, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="CVTitle", fontName="Times-Italic", fontSize=11,
                              textColor=TEXT_LIGHT, spaceAfter=6, leading=14, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="CVContact", fontName="Times-Roman", fontSize=8.5,
                              textColor=TEXT_LIGHT, spaceAfter=8, leading=11, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="CVSection", fontName="Times-Bold", fontSize=11,
                              textColor=ACCENT, spaceBefore=12, spaceAfter=4, leading=14, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="CVSummary", fontName="Times-Roman", fontSize=9.5,
                              textColor=TEXT_DARK, spaceAfter=6, alignment=TA_JUSTIFY, leading=13))
    styles.add(ParagraphStyle(name="CVCompany", fontName="Times-Bold", fontSize=9.5,
                              textColor=PRIMARY, spaceAfter=1, leading=12))
    styles.add(ParagraphStyle(name="CVRole", fontName="Times-Italic", fontSize=9,
                              textColor=TEXT_DARK, spaceAfter=1, leading=11))
    styles.add(ParagraphStyle(name="CVPeriod", fontName="Times-Roman", fontSize=8,
                              textColor=TEXT_LIGHT, spaceAfter=3, leading=10))
    styles.add(ParagraphStyle(name="CVBullet", fontName="Times-Roman", fontSize=9,
                              textColor=TEXT_DARK, leftIndent=14, spaceAfter=2, leading=12, alignment=TA_JUSTIFY))
    styles.add(ParagraphStyle(name="CVSkill", fontName="Times-Roman", fontSize=9,
                              textColor=TEXT_DARK, spaceAfter=4, leading=12))
    styles.add(ParagraphStyle(name="CVProject", fontName="Times-Roman", fontSize=9,
                              textColor=TEXT_DARK, spaceAfter=3, leading=12))
    return styles


def generate(cv_data, profile, output_path, job_title="", company="", language="es"):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    labels = SECTION_LABELS.get(language, SECTION_LABELS["es"])

    doc = SimpleDocTemplate(output_path, pagesize=letter,
                            leftMargin=0.7*inch, rightMargin=0.7*inch,
                            topMargin=0.6*inch, bottomMargin=0.6*inch)
    styles = build_styles()
    story = []

    # Header — centered, traditional
    story.append(Paragraph(_safe(safe_header_name(profile, cv_data)), styles["CVName"]))
    story.append(Paragraph(_safe(cv_data.get("title", profile.get("title", ""))), styles["CVTitle"]))

    contact_parts = [v for k in ("email", "phone", "linkedin", "portfolio", "location")
                     if (v := profile.get(k))]
    story.append(Paragraph(_safe(" | ".join(contact_parts)), styles["CVContact"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=LINE_COLOR, spaceAfter=10))

    # Summary
    story.append(Paragraph(labels["summary"], styles["CVSection"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4))
    story.append(Paragraph(_safe(cv_data.get("summary") or ""), styles["CVSummary"]))

    # Skills
    skills = cv_data.get("skills_highlighted", [])
    if skills:
        story.append(Paragraph(labels["skills"], styles["CVSection"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4))
        story.append(Paragraph(_safe(", ".join(skills)), styles["CVSkill"]))

    # Experience
    experience = cv_data.get("experience", [])
    if experience:
        story.append(Paragraph(labels["experience"], styles["CVSection"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4))
        for exp in experience:
            story.append(Paragraph(_safe(exp["company"]), styles["CVCompany"]))
            story.append(Paragraph(_safe(exp["role"]), styles["CVRole"]))
            story.append(Paragraph(_safe(exp["period"]), styles["CVPeriod"]))
            for bullet in exp.get("bullets", []):
                story.append(Paragraph(f"- {_safe(bullet)}", styles["CVBullet"]))
            story.append(Spacer(1, 4))

    # Projects
    projects = cv_data.get("projects", [])
    if projects:
        story.append(Paragraph(labels["projects"], styles["CVSection"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4))
        for proj in projects:
            tech_str = _safe(", ".join(proj.get("tech", [])))
            story.append(Paragraph(f"<b>{_safe(proj['name'])}</b> - {_safe(proj['description'])} ({tech_str})", styles["CVProject"]))
            story.append(Spacer(1, 2))

    # Education
    education = cv_data.get("education", profile.get("education", []))
    if education:
        story.append(Paragraph(labels["education"], styles["CVSection"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4))
        for edu in education:
            story.append(Paragraph(f"<b>{_safe(edu['institution'])}</b>", styles["CVCompany"]))
            story.append(Paragraph(f"{_safe(edu['degree'])} ({_safe(edu['period'])})", styles["CVProject"]))
            story.append(Spacer(1, 2))

    # Languages
    languages = cv_data.get("languages", [])
    if languages:
        lang_label = {"es": "IDIOMAS", "en": "LANGUAGES", "pt": "IDIOMAS", "fr": "LANGUES", "de": "SPRACHEN"}.get(language, "IDIOMAS")
        story.append(Paragraph(lang_label, styles["CVSection"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=4))
        lang_text = ", ".join(f"{l['language']} ({l['level']})" for l in languages)
        story.append(Paragraph(_safe(lang_text), styles["CVSkill"]))

    doc.build(story)
    return output_path
