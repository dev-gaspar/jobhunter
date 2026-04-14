# -*- coding: utf-8 -*-
"""Agente 4: analiza historial y genera queries de busqueda optimizadas."""
import json

from jobhunter.ai.gemini import call_gemini


def optimize_queries(cfg, kb, user_prompt=None):
    """Genera queries optimizadas a partir del perfil, queries actuales y metricas de historial.

    Retorna dict {analysis, queries, changes_summary}. Vacio si falla.
    """
    profile = cfg.get("profile", {})
    current_queries = cfg.get("search_queries", [])
    job_types = cfg.get("job_types_raw", "")
    lang = cfg.get("search_languages", "3")
    work_mode = cfg.get("work_mode_label", "Cualquiera")
    location = cfg.get("user_location", "")

    lang_labels = {"1": "Espanol", "2": "Ingles", "3": "Espanol e Ingles"}
    lang_label = lang_labels.get(lang, "Espanol e Ingles")

    runs = kb.get("runs", [])
    apps = kb.get("applications", [])

    run_stats = ""
    if runs:
        total_posts = sum(r.get("posts", 0) for r in runs)
        total_offers = sum(r.get("offers", 0) for r in runs)
        total_sent = sum(r.get("sent", 0) for r in runs)
        rate_offers = (total_offers / total_posts * 100) if total_posts else 0
        rate_sent = (total_sent / total_posts * 100) if total_posts else 0
        run_stats = (
            f"\nHISTORIAL DE EJECUCIONES ({len(runs)} ejecuciones):"
            f"\n- Posts scrapeados en total: {total_posts}"
            f"\n- Ofertas encontradas en total: {total_offers}"
            f"\n- Emails enviados en total: {total_sent}"
            f"\n- Tasa de conversion posts->ofertas: {rate_offers:.1f}% (idealmente >15%)"
            f"\n- Tasa de conversion posts->enviados: {rate_sent:.1f}%"
        )

    applied_titles = ""
    if apps:
        titles = list(set(a.get("job_title", "") for a in apps[-30:]))
        applied_titles = f"\nPUESTOS A LOS QUE YA APLICO (ultimos 30): {', '.join(titles[:15])}"

    user_context = ""
    if user_prompt:
        user_context = (
            '\nFEEDBACK DEL USUARIO (prioridad maxima, atender esto):\n"'
            + user_prompt + '"\n'
        )

    skills = profile.get("skills", {})
    skills_str = json.dumps(skills) if isinstance(skills, dict) else str(skills)[:500]
    exp = profile.get("experience", [])
    exp_str = json.dumps(exp[:2]) if exp else "N/A"
    location_line = f"- Ubicacion: {location}" if location else ""
    lang_rule = "- SOLO en espanol" if lang == "1" else "- SOLO en ingles" if lang == "2" else "- En espanol Y en ingles"
    queries_json = json.dumps(current_queries, indent=2)

    prompt = f"""ROLE: Eres un agente experto en busqueda de empleo en LinkedIn. Tu trabajo es optimizar las queries de busqueda para maximizar la cantidad de ofertas REALES con email de reclutador encontradas.

CONTEXTO DEL CANDIDATO:
- Nombre: {profile.get('name', '?')}
- Titulo: {profile.get('title', '?')}
- Busca empleo como: {job_types}
- Habilidades: {skills_str}
- Experiencia reciente: {exp_str}
- Idiomas de busqueda: {lang_label}
- Modalidad: {work_mode}
{location_line}

QUERIES ACTUALES ({len(current_queries)}):
{queries_json}
{run_stats}
{applied_titles}
{user_context}

INSTRUCCIONES:
1. Analiza las queries actuales y determina por que pueden estar dando pocos resultados
2. Genera queries OPTIMIZADAS que:
   - Usen terminos que los reclutadores REALMENTE usan en LinkedIn cuando publican ofertas
   - Incluyan variaciones naturales (abreviaciones, sinonimos, terminos de la industria)
   - Cubran tanto posts de reclutadores como de hiring managers
   - Sean especificas al perfil pero no tan nicho que no encuentren nada
   - Incluyan frases que impliquen que hay email de contacto ("enviar CV a", "send resume to", "apply via email")
   - Consideren la modalidad de trabajo ({work_mode})
   {lang_rule}
3. NO repitas las mismas queries con minimas variaciones
4. Apunta a 15-25 queries totales (suficientes para cubrir variaciones, no tantas que sea lento)
5. Cada query debe ser de 3-6 palabras (asi funciona mejor en LinkedIn search)

JSON (sin markdown, sin bloques de codigo):
{{"analysis": "analisis breve de por que las queries actuales pueden ser suboptimas", "queries": ["query1", "query2", ...], "changes_summary": "resumen de 2-3 lineas de que cambio y por que"}}"""

    try:
        return json.loads(call_gemini(cfg, prompt))
    except Exception:
        return {"analysis": "", "queries": [], "changes_summary": ""}
