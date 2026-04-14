# -*- coding: utf-8 -*-
"""Agente 3: escribe emails de aplicacion cortos y humanos, coherentes con el CV."""
import json

from jobhunter.ai.gemini import call_gemini


def agent_email(cfg, job, cv_data=None):
    """Retorna dict {subject, body} del email para enviar a la oferta."""
    p = cfg["profile"]
    portfolio_line = "\n- Portfolio: " + p["portfolio"] if p.get("portfolio") else ""
    linkedin_line = "\n- LinkedIn: " + p["linkedin"] if p.get("linkedin") else ""

    cv_context = ""
    if cv_data:
        cv_skills = ", ".join(cv_data.get("skills_highlighted", [])[:8])
        cv_context = (
            "\nCV GENERADO PARA ESTA OFERTA (usa estos datos para que el email sea coherente con el CV adjunto):"
            "\n- Titulo: " + cv_data.get("title", "") +
            "\n- Resumen: " + cv_data.get("summary", "") +
            "\n- Skills destacadas: " + cv_skills + "\n"
        )
    lang = job.get("language", "es")

    lang_names = {
        "es": "ESPA\u00d1OL",
        "en": "INGLES",
        "pt": "PORTUGUES",
        "fr": "FRANCES",
        "de": "ALEMAN",
    }
    lang_name = lang_names.get(lang, "ESPA\u00d1OL")

    sig_parts = [p.get("name", "")]
    if p.get("portfolio"):
        sig_parts.append(p["portfolio"])
    if p.get("linkedin"):
        sig_parts.append(p["linkedin"])

    lang_rules = {
        "es": '1. ESPA\u00d1OL NEUTRO LATINOAMERICANO. PROHIBIDO: "flipa", "mola", "tio", "chevere", "bacano", "pana"',
        "en": "1. ENGLISH. Write in professional, natural English. No overly formal or robotic language.",
        "pt": "1. PORTUGUES. Escreva em portugues profissional e natural.",
    }
    lang_rule = lang_rules.get(lang, f"1. Escribe en {lang_name}. Lenguaje profesional y natural.")

    cv_clause = " o en el CV generado" if cv_data else ""
    signer_name = p.get("name", "el candidato")
    signature = ", ".join(sig_parts)
    name = p.get("name", "")
    job_types_raw = cfg.get("job_types_raw", "")
    job_title = job.get("job_title", "")
    company = job.get("company", "")
    description = job.get("description", "")
    contact_name = job.get("contact_name", "equipo de seleccion")

    prompt = f"""ROLE: Eres un agente especializado en escribir emails de aplicacion a ofertas de trabajo.
Tu objetivo: escribir un email que suene 100% humano, personal, y que haga que el reclutador quiera responder.
Esto funciona para CUALQUIER sector: tecnologia, marketing, ventas, diseno, salud, educacion, finanzas, etc.

IDIOMA: Escribe TODO el email en {lang_name}. La oferta esta en {lang_name}.

CANDIDATO:
- Nombre: {name}{portfolio_line}{linkedin_line}
- Busca empleo como: {job_types_raw}
{cv_context}
OFERTA:
- Puesto: {job_title}
- Empresa: {company}
- Descripcion: {description}
- Contacto: {contact_name}

REGLAS ESTRICTAS:
{lang_rule}
2. TEXTO PLANO UNICAMENTE. PROHIBIDO: markdown, corchetes [], asteriscos **, formato [texto](url), HTML
3. Las URLs van tal cual, sin formato alrededor
4. MAXIMO 100 palabras en el cuerpo
5. Debe sonar como si {signer_name} lo escribiera personalmente
6. PROHIBIDO frases de plantilla: "me emociona", "me apasiona profundamente", "me encantaria unirme", "I am excited", "I am passionate"
7. NO propongas agendar llamadas ni reuniones
8. Menciona 1-2 logros CONCRETOS con numeros que sean relevantes para ESTA oferta. PROHIBIDO inventar logros, cifras o habilidades que no esten en el perfil del candidato{cv_clause}.
9. El asunto debe ser corto y directo (max 8 palabras)
10. Firma simple en texto plano: {signature}

JSON (sin markdown, sin bloques de codigo):
{{"subject": "asunto corto", "body": "cuerpo completo con saludo y despedida"}}"""

    return json.loads(call_gemini(cfg, prompt))
