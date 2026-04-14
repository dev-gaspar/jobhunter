# -*- coding: utf-8 -*-
"""Agente que genera queries de busqueda de LinkedIn a partir del perfil.

Antes esta logica vivia inline en cmd_setup con un prompt que incluia las
propias palabras del fallback robotico como 'inspiracion' y terminaba
generando queries del tipo 'enviar CV X remoto'. Este modulo inyecta stack
tecnico real, seniority estimada y nivel de ingles del usuario para que el
modelo produzca queries mas cercanas al lenguaje real de reclutadores LATAM.
"""
import json

from jobhunter.ai.gemini import call_gemini


def _estimate_seniority(profile):
    """Estimacion gruesa de seniority por cantidad de experiencias listadas."""
    exps = profile.get("experience", []) or []
    n = len(exps)
    if n <= 1:
        return "junior"
    if n <= 3:
        return "semi senior"
    return "senior"


def _english_level(cfg):
    """Nivel de ingles declarado o None si no aparece."""
    for lang in cfg.get("user_languages", []) or []:
        name = (lang.get("language") or "").lower()
        if name.startswith("ingl") or name.startswith("engl"):
            return (lang.get("level") or "").strip()
    return None


def _english_is_limited(level):
    """True si el nivel NO alcanza para ofertas 100% en ingles."""
    if not level:
        return True
    low = level.lower()
    return any(k in low for k in ("a1", "a2", "b1", "basico", "basic"))


def _top_stack(profile, n=6):
    """Aplana las skills declaradas y toma las primeras n sin categorizar."""
    skills = profile.get("skills", {})
    items = []
    if isinstance(skills, dict):
        for v in skills.values():
            if isinstance(v, list):
                items.extend(v)
    elif isinstance(skills, list):
        items = list(skills)
    return [str(s).strip() for s in items if s][:n]


def _sanitize(queries):
    """Strip + dedupe case-insensitive + descarta no-strings y vacios."""
    seen = set()
    clean = []
    for q in queries:
        if not isinstance(q, str):
            continue
        q = q.strip()
        k = q.lower()
        if not q or k in seen:
            continue
        seen.add(k)
        clean.append(q)
    return clean


def _fallback(cfg, stack, seniority, en_limited):
    """Fallback programatico mejorado: usa stack y seniority reales.

    El fallback anterior solo expandia 'enviar CV/busco/contratando/vacante' x
    titulo generico. Este agrega combos con stack y varia mas las expresiones.
    """
    job_types = cfg.get("job_types_raw", "software developer")
    wm_label = cfg.get("work_mode_label", "Cualquiera")
    lang = cfg.get("search_languages", "3")

    wm = wm_label.lower()
    mode_es = {"remoto": "remoto", "hibrido": "hibrido", "presencial": "presencial", "cualquiera": ""}.get(wm, "")
    mode_en = {"remoto": "remote", "hibrido": "hybrid", "presencial": "onsite", "cualquiera": ""}.get(wm, "")
    sen = {"junior": "junior", "semi senior": "semi senior", "senior": "senior"}.get(seniority, "")

    queries = []
    titles = [j.strip() for j in job_types.split(",") if j.strip()][:3]

    for jt in titles:
        if lang in ("1", "3"):
            queries.extend([
                f"CV {jt} {mode_es}".strip(),
                f"buscamos {jt} {mode_es}".strip(),
                f"contratando {jt} {sen}".strip(),
                f"vacante {jt} {mode_es}".strip(),
                f"aplica {jt} enviar CV".strip(),
                f"postulate {jt} {mode_es}".strip(),
            ])
        if lang == "2" or (lang == "3" and not en_limited):
            queries.extend([
                f"hiring {jt} {mode_en}".strip(),
                f"we are hiring {jt}".strip(),
                f"looking for {jt} {mode_en}".strip(),
            ])

    for tech in stack[:3]:
        if lang in ("1", "3"):
            queries.append(f"buscamos {tech} developer {mode_es}".strip())
            queries.append(f"vacante {tech} {mode_es}".strip())

    return _sanitize(queries)[:22]


def generate_queries(cfg):
    """Genera queries personalizadas. Retorna (queries, from_ai).

    from_ai=False indica que Gemini fallo y se uso el fallback. El caller
    (cmd_setup / cmd_optimize) deberia avisar al usuario en ese caso para
    que decida si reintentar o seguir con las queries del fallback.
    """
    profile = cfg.get("profile", {})
    job_types = cfg.get("job_types_raw", "software developer")
    lang = cfg.get("search_languages", "3")
    wm_label = cfg.get("work_mode_label", "Cualquiera")
    location = cfg.get("user_location", "")

    seniority = _estimate_seniority(profile)
    en_level = _english_level(cfg)
    en_limited = _english_is_limited(en_level)
    stack = _top_stack(profile)

    lang_label = {"1": "espanol", "2": "ingles", "3": "espanol e ingles"}.get(lang, "espanol e ingles")

    if lang == "3" and en_limited:
        effective_lang_rule = (
            "Genera queries en espanol. Puedes mezclar terminos en ingles SOLO dentro de una query "
            "en espanol (ej 'hiring Backend remoto Colombia'). NO generes queries 100% en ingles "
            "porque el candidato tiene nivel de ingles limitado y esas ofertas se descartaran despues."
        )
    elif lang == "1":
        effective_lang_rule = "Genera queries solo en espanol."
    elif lang == "2":
        effective_lang_rule = "Genera queries solo en ingles."
    else:
        effective_lang_rule = "Mezcla queries en espanol y en ingles."

    stack_line = f"- Stack tecnico real del candidato: {', '.join(stack)}" if stack else ""
    location_line = f"- Ubicacion: {location}" if location else ""
    en_level_line = f"- Nivel de ingles real: {en_level}" if en_level else "- Nivel de ingles: no declarado"

    prompt = f"""Eres un experto en reclutamiento IT en LinkedIn LATAM. Tu trabajo es generar queries para la barra de busqueda de LinkedIn seccion Contenido (posts), NO en la seccion Empleos. Las queries deben encontrar publicaciones de reclutadores o hiring managers que dejan email de contacto para recibir CVs.

PERFIL DEL CANDIDATO:
- Titulo actual: {profile.get('title', '?')}
- Busca empleo como: {job_types}
- Seniority estimada: {seniority}
- Modalidad preferida: {wm_label}
{location_line}
{stack_line}
- Idiomas de busqueda: {lang_label}
{en_level_line}

REGLAS:
1. {effective_lang_rule}
2. Genera entre 15 y 22 queries. Calidad sobre cantidad.
3. Usa expresiones reales que reclutadores LATAM (Colombia, Mexico, Argentina, Chile) usan al publicar en LinkedIn. Piensa en lenguaje natural y coloquial de reclutadores, no en formulas genericas.
4. Cada query debe ser corta (3-6 palabras), como alguien escribiria en la barra de busqueda.
5. AL MENOS LA MITAD de las queries deben incluir el stack tecnico concreto del candidato (ej nombres de frameworks/lenguajes), no solo el titulo generico.
6. Incluye variantes por seniority: si es "junior" usa junior/trainee; si es "semi senior" usa semi senior/SSR; si es "senior" usa senior/sr. NO mezcles seniorities lejanas.
7. NO repitas queries con solo reordenar palabras.
8. NO generes la mayoria de queries con el patron "enviar CV X" / "busco X" / "hiring X". Varia las expresiones: aplica, postulate, buscamos, contratando, vacante, incorporar, se busca, oportunidad, se necesita, estamos contratando, unete al equipo, etc.
9. Si la modalidad no es "Cualquiera", incluirla en algunas queries (no en todas).

JSON array: ["query1", "query2", ...]
Responde SOLO el JSON array, sin texto adicional ni bloques de codigo."""

    try:
        result = call_gemini(cfg, prompt)
        queries = json.loads(result)
        if not isinstance(queries, list):
            raise ValueError("respuesta no es una lista")
        clean = _sanitize(queries)
        if len(clean) < 5:
            raise ValueError("pocas queries utiles")
        return clean[:25], True
    except Exception:
        return _fallback(cfg, stack, seniority, en_limited), False
