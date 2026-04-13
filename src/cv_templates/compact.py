"""Compact template — dense layout, fits more content per page."""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_JUSTIFY
from src.cv_builder import _safe, SECTION_LABELS, safe_header_name

PRIMARY = HexColor("#0d47a1")
TEXT_DARK = HexColor("#212121")
TEXT_LIGHT = HexColor("#616161")
LINE_COLOR = HexColor("#0d47a1")


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CVName", fontName="Helvetica-Bold", fontSize=16,
                              textColor=PRIMARY, spaceAfter=2, leading=19, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="CVTitle", fontName="Helvetica", fontSize=9,
                              textColor=TEXT_LIGHT, spaceAfter=3, leading=11, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="CVContact", fontName="Helvetica", fontSize=7,
                              textColor=TEXT_LIGHT, spaceAfter=6, leading=9, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="CVSection", fontName="Helvetica-Bold", fontSize=9,
                              textColor=PRIMARY, spaceBefore=8, spaceAfter=3, leading=11, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="CVSummary", fontName="Helvetica", fontSize=8,
                              textColor=TEXT_DARK, spaceAfter=4, alignment=TA_JUSTIFY, leading=11))
    styles.add(ParagraphStyle(name="CVCompanyRole", fontName="Helvetica-Bold", fontSize=8,
                              textColor=TEXT_DARK, spaceAfter=0, leading=10))
    styles.add(ParagraphStyle(name="CVPeriod", fontName="Helvetica", fontSize=7,
                              textColor=TEXT_LIGHT, spaceAfter=2, leading=9))
    styles.add(ParagraphStyle(name="CVBullet", fontName="Helvetica", fontSize=7.5,
                              textColor=TEXT_DARK, leftIndent=8, spaceAfter=1, leading=9.5, alignment=TA_JUSTIFY))
    styles.add(ParagraphStyle(name="CVSkill", fontName="Helvetica", fontSize=7.5,
                              textColor=TEXT_DARK, spaceAfter=3, leading=10))
    styles.add(ParagraphStyle(name="CVProject", fontName="Helvetica", fontSize=7.5,
                              textColor=TEXT_DARK, spaceAfter=2, leading=10))
    styles.add(ParagraphStyle(name="CVPeriodRight", fontName="Helvetica", fontSize=7,
                              textColor=TEXT_LIGHT, alignment=TA_RIGHT, leading=10))
    return styles


def generate(cv_data, profile, output_path, job_title="", company="", language="es"):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    labels = SECTION_LABELS.get(language, SECTION_LABELS["es"])

    doc = SimpleDocTemplate(output_path, pagesize=letter,
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.4*inch, bottomMargin=0.4*inch)
    styles = build_styles()
    story = []
    page_width = letter[0] - 1.0 * inch  # usable width

    # Header — compact with name and contact on same visual block
    story.append(Paragraph(_safe(safe_header_name(profile, cv_data)), styles["CVName"]))
    story.append(Paragraph(_safe(cv_data.get("title", profile.get("title", ""))), styles["CVTitle"]))

    contact_parts = [v for k in ("email", "phone", "linkedin", "portfolio", "location")
                     if (v := profile.get(k))]
    story.append(Paragraph(_safe(" | ".join(contact_parts)), styles["CVContact"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=LINE_COLOR, spaceAfter=4))

    # Summary — compact
    story.append(Paragraph(labels["summary"], styles["CVSection"]))
    story.append(Paragraph(_safe(cv_data.get("summary") or ""), styles["CVSummary"]))

    # Skills — two-column layout
    skills = cv_data.get("skills_highlighted", [])
    if skills:
        story.append(Paragraph(labels["skills"], styles["CVSection"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=3))
        mid = (len(skills) + 1) // 2
        col1 = skills[:mid]
        col2 = skills[mid:]
        rows = []
        for i in range(max(len(col1), len(col2))):
            left = _safe(col1[i]) if i < len(col1) else ""
            right = _safe(col2[i]) if i < len(col2) else ""
            rows.append([
                Paragraph(f"- {left}" if left else "", styles["CVBullet"]),
                Paragraph(f"- {right}" if right else "", styles["CVBullet"]),
            ])
        t = Table(rows, colWidths=[page_width * 0.5, page_width * 0.5])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(t)

    # Experience — company + role + period on same line block
    experience = cv_data.get("experience", [])
    if experience:
        story.append(Paragraph(labels["experience"], styles["CVSection"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=3))
        for exp in experience:
            # Company — Role | Period
            header = Table(
                [[Paragraph(f"<b>{_safe(exp['company'])}</b> - {_safe(exp['role'])}", styles["CVCompanyRole"]),
                  Paragraph(_safe(exp["period"]), styles["CVPeriodRight"])]],
                colWidths=[page_width * 0.7, page_width * 0.3],
            )
            header.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]))
            story.append(header)
            for bullet in exp.get("bullets", []):
                story.append(Paragraph(f"- {_safe(bullet)}", styles["CVBullet"]))
            story.append(Spacer(1, 3))

    # Projects
    projects = cv_data.get("projects", [])
    if projects:
        story.append(Paragraph(labels["projects"], styles["CVSection"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE_COLOR, spaceAfter=3))
        for proj in projects:
            tech_str = _safe(", ".join(proj.get("tech", [])))
            story.append(Paragraph(f"<b>{_safe(proj['name'])}</b> - {_safe(proj['description'])} ({tech_str})", styles["CVProject"]))

    # Education + Languages side by side
    education = cv_data.get("education", profile.get("education", []))
    languages = cv_data.get("languages", [])

    if education or languages:
        story.append(Spacer(1, 2))
        edu_parts = []
        if education:
            edu_parts.append(Paragraph(labels["education"], styles["CVSection"]))
            for edu in education:
                edu_parts.append(Paragraph(f"<b>{_safe(edu['degree'])}</b> - {_safe(edu['institution'])} ({_safe(edu['period'])})", styles["CVProject"]))

        lang_parts = []
        if languages:
            lang_label = {"es": "IDIOMAS", "en": "LANGUAGES", "pt": "IDIOMAS", "fr": "LANGUES", "de": "SPRACHEN"}.get(language, "IDIOMAS")
            lang_parts.append(Paragraph(lang_label, styles["CVSection"]))
            for l in languages:
                lang_parts.append(Paragraph(f"- {_safe(l['language'])} ({_safe(l['level'])})", styles["CVProject"]))

        if edu_parts and lang_parts:
            row = Table([[edu_parts, lang_parts]], colWidths=[page_width * 0.6, page_width * 0.4])
            row.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(row)
        else:
            for p in edu_parts + lang_parts:
                story.append(p)

    doc.build(story)
    return output_path
