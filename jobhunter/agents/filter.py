# -*- coding: utf-8 -*-
"""Agente 1: filtra posts de LinkedIn y detecta ofertas reales relevantes al perfil."""
import json

from jobhunter.ai.gemini import call_gemini, call_gemini_vision
from src.offer_utils import extract_emails


def agent_filter(cfg, text, ss=None):
    """Analiza un post de LinkedIn y devuelve dict con is_job / is_relevant / datos."""
    emails = extract_emails(text)
    if ss:
        try:
            r = call_gemini_vision(
                cfg,
                'Extrae emails y detalles de este post LinkedIn. JSON: {"email":"email o null","details":"detalles"}',
                ss,
            )
            d = json.loads(r)
            if d.get("email") and d["email"] != "null":
                emails.append(d["email"])
            if d.get("details"):
                text += "\n" + d["details"]
        except Exception:
            pass

    profile = cfg.get("profile", {})
    job_types = cfg.get("job_types_raw", "")
    profile_summary = profile.get("summary", "")
    profile_skills = profile.get("skills", {})
    work_mode_label = cfg.get("work_mode_label", "Cualquiera")
    user_location = cfg.get("user_location", "")
    user_languages = cfg.get("user_languages", [])
    user_langs_str = (
        ", ".join(lang["language"] + " (" + lang["level"] + ")" for lang in user_languages)
        if user_languages else "No especificados"
    )
    user_location_line = "- Ubicacion del candidato: " + user_location if user_location else ""

    work_mode_rule = ""
    if work_mode_label.lower() == "remoto":
        work_mode_rule = "- SOLO ofertas remotas o que permitan trabajo remoto. Descartar presenciales y hibridas."
    elif work_mode_label.lower() == "hibrido":
        work_mode_rule = f"- SOLO ofertas hibridas o remotas. Si es hibrida/presencial, debe ser compatible con la ubicacion del candidato: {user_location}"
    elif work_mode_label.lower() == "presencial":
        work_mode_rule = f"- SOLO ofertas presenciales o hibridas compatibles con la ubicacion del candidato: {user_location}"

    emails_line = ", ".join(emails) if emails else "ninguno"
    skills_str = json.dumps(profile_skills) if isinstance(profile_skills, dict) else str(profile_skills)[:500]

    prompt = f"""ROLE: Eres un agente especializado en filtrar ofertas de trabajo de LinkedIn.
Tu unico trabajo es analizar publicaciones y determinar si contienen ofertas REALES y RELEVANTES para este candidato.

PERFIL DEL CANDIDATO:
- Busca empleo como: {job_types}
- Modalidad preferida: {work_mode_label}
{user_location_line}
- Idiomas del candidato: {user_langs_str}
- Resumen: {profile_summary[:300]}
- Habilidades: {skills_str}

PUBLICACION:
{text[:4000]}

EMAILS ENCONTRADOS EN EL TEXTO: {emails_line}

REGLAS DE FILTRADO:
- Solo ofertas de TRABAJO reales (no cursos, certificaciones, logros personales, contenido general, publicidad)
- Relevante si el puesto tiene relacion con lo que busca el candidato: {job_types}
{work_mode_rule}
- Si la oferta REQUIERE un idioma con nivel avanzado o fluido que el candidato NO tiene a ese nivel, marcar is_relevant=false. Los idiomas del candidato son: {user_langs_str}
- Extraer SIEMPRE el email si existe en el texto
- Extraer empresa, titulo, descripcion COMPLETA con todos los detalles
- Extraer requisitos especificos (habilidades, herramientas, anos de experiencia, idiomas, etc.)
- Si la publicacion tiene multiples ofertas, toma la mas relevante para el candidato
- DETECTAR el idioma en que esta escrita la publicacion (es, en, pt, etc.)

JSON:
{{"is_job": true/false, "job_title": "titulo exacto del puesto", "company": "empresa", "description": "descripcion DETALLADA incluyendo responsabilidades y lo que se espera del candidato", "requirements": "TODOS los requisitos mencionados", "contact_email": "email@empresa.com o null", "contact_name": "nombre de quien publica", "location": "ubicacion", "work_mode": "remote/hybrid/onsite/unknown", "salary": "salario o null", "language": "es/en/pt/fr/etc", "is_relevant": true/false, "relevance_reason": "razon concreta"}}

Si NO es oferta: {{"is_job": false, "relevance_reason": "razon"}}
SOLO JSON valido."""

    try:
        a = json.loads(call_gemini(cfg, prompt))
        ce = a.get("contact_email", "")
        if not ce or str(ce).lower() in ("null", "none", "n/a"):
            a["contact_email"] = None
        if emails and not a.get("contact_email"):
            a["contact_email"] = emails[0]
        return a
    except Exception as e:
        return {"is_job": False, "relevance_reason": str(e)}
