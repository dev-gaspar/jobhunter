# -*- coding: utf-8 -*-
"""Agente 2: genera un CV personalizado a cada oferta en el idioma de la misma."""
import json

from jobhunter.ai.gemini import call_gemini


def agent_cv(cfg, job):
    """Retorna dict con summary, title, skills_highlighted, experience, projects, education, languages."""
    p = cfg["profile"]
    title = job.get("job_title", "Profesional")
    company = job.get("company", "Empresa")
    desc = job.get("description", "")
    reqs = job.get("requirements", "")
    lang = job.get("language", "es")

    lang_names = {
        "es": "ESPA\u00d1OL",
        "en": "INGLES",
        "pt": "PORTUGUES",
        "fr": "FRANCES",
        "de": "ALEMAN",
    }
    lang_name = lang_names.get(lang, "ESPA\u00d1OL")
    cv_user_langs = cfg.get("user_languages", [])
    cv_user_langs_str = (
        ", ".join(ul["language"] + " (" + ul["level"] + ")" for ul in cv_user_langs)
        if cv_user_langs else "No especificados"
    )
    profile_json = json.dumps(p, indent=2)

    prompt = f"""ROLE: Eres un reclutador senior que ha revisado mas de 100,000 hojas de vida. Sabes exactamente que busca un hiring manager cuando lee un CV: relevancia inmediata, logros con numeros, y lenguaje que coincida con la oferta.
Tu trabajo es tomar el perfil del candidato y REESCRIBIRLO desde la perspectiva de lo que el hiring manager de ESTA oferta quiere leer. No es solo hacer match de keywords \u2014 es presentar la experiencia del candidato en el orden y con el enfoque que haria que un reclutador diga "este es el candidato".
Esto funciona para CUALQUIER tipo de trabajo: tecnologia, marketing, ventas, diseno, administracion, salud, educacion, etc.

REGLAS CRITICAS:
- ESCRIBE TODO EL CV EN {lang_name}. La oferta esta en {lang_name} y el CV debe estar en el MISMO idioma.
- TEXTO PLANO UNICAMENTE. PROHIBIDO usar markdown: nada de **negritas**, *italicas*, `codigo`, # encabezados, ni ningun formato. Solo texto limpio.
- Usa la MISMA TERMINOLOGIA de la oferta. Si la oferta dice "Community Manager", el CV dice "Community Manager". Si dice "Backend Developer", dice "Backend Developer".
- NO traduzcas terminos que en la industria se usan en su idioma original
- REGLA MAS IMPORTANTE \u2014 PROHIBIDO INVENTAR CUALQUIER COSA. El candidato ya te entrego su informacion real. Tu unica tarea es TOMAR LO QUE YA ESTA y REORDENARLO/REFORMULARLO. No agregues:
  * Habilidades que el candidato no tiene (si no usa React, NO pongas React)
  * Tecnologias o herramientas no mencionadas en el perfil real
  * Idiomas o niveles no declarados
  * Certificaciones o titulos no obtenidos
  * Empresas o roles que el candidato nunca tuvo
  * Numeros, porcentajes o metricas falsas (si el perfil dice "optimice proceso" NO inventes "reduje 40% el tiempo")
  * Anos de experiencia superiores a los reales
- Si la oferta pide algo que el candidato NO tiene, simplemente NO LO MENCIONES. No inventes para cubrir el gap.
- Puedes DESTACAR lo que ya hizo, usar palabras de la oferta para describir lo que ya hace, y elegir que experiencia poner primero. PUNTO. Nada mas.
- IDIOMAS: Solo incluye los idiomas que el candidato realmente maneja. Los idiomas del candidato son: {cv_user_langs_str}. NO inventes niveles de idioma ni agregues idiomas que no esten en esta lista.
- Si el perfil esta casi vacio (pocos skills, pocas experiencias), NO lo rellenes con datos falsos. Entrega un CV corto y honesto en vez de uno inventado.

CANDIDATO:
{profile_json}

OFERTA:
- Titulo: {title}
- Empresa: {company}
- Descripcion: {desc}
- Requisitos: {reqs}

INSTRUCCIONES PARA CADA SECCION:

1. SUMMARY (sobre mi): Reescribe completamente en PRIMERA PERSONA (yo tengo, yo desarrollo, mi experiencia) para que suene como si el candidato fuera la persona IDEAL para este puesto especifico. PROHIBIDO tercera persona (Jose es, Jose tiene). Menciona las habilidades y experiencia que pide la oferta. 2-3 oraciones.

2. TITLE: Usa el mismo titulo o terminologia de la oferta.

3. SKILLS: Reordena poniendo PRIMERO las que pide la oferta. Solo incluye skills relevantes para ESTE puesto.

4. EXPERIENCE: Esta es la parte MAS IMPORTANTE. Piensa como el hiring manager que lee esto: que le haria detenerse y decir "este candidato sabe hacer lo que necesito"?
   - Para CADA experiencia laboral, reescribe los bullets para que DESTAQUEN habilidades relevantes a ESTA oferta.
   - Conecta lo que el candidato hizo con lo que la oferta necesita usando el MISMO lenguaje de la descripcion del puesto.
   - Usa numeros y metricas siempre que sea posible.
   - Prioriza los bullets que resuelven los problemas que la oferta menciona, no solo los mas impresionantes.

5. PROJECTS: Selecciona solo los proyectos mas relevantes para esta oferta. Si no hay proyectos relevantes, omite esta seccion con un array vacio.

6. EDUCATION: Mantener tal cual.

JSON:
{{
    "summary": "resumen personalizado para ESTA oferta (2-3 oraciones)",
    "title": "titulo usando terminos de la oferta",
    "skills_highlighted": ["skill1", "skill2", "skill3", ...],
    "experience": [
        {{
            "company": "empresa",
            "role": "titulo del rol",
            "period": "periodo",
            "bullets": [
                "logro reescrito enfocado a esta oferta con numeros",
                "logro reescrito enfocado a esta oferta con numeros",
                "logro reescrito enfocado a esta oferta con numeros"
            ]
        }}
    ],
    "projects": [
        {{"name": "proyecto relevante", "description": "enfocado a la oferta", "tech": ["herramienta1", "herramienta2"]}}
    ],
    "education": [
        {{"institution": "institucion", "degree": "titulo", "period": "periodo"}}
    ],
    "languages": [
        {{"language": "idioma", "level": "nivel real del candidato"}}
    ]
}}
SOLO JSON valido."""

    return json.loads(call_gemini(cfg, prompt))
