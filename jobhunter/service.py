# -*- coding: utf-8 -*-
"""Fachada de la logica de negocio, sin UI.

Consumida por el CLI (pipeline/applying/cli/*) y por la app de escritorio
(desktop/). Toda operacion larga reporta progreso via on_event(name, payload)
y nunca imprime ni pregunta nada. Eventos emitidos por search_offers:

  ("phase",    {"phase": "scrape"|"analyze"|"dedupe", "status": "start"|"done",
                "detail": str, "total": int|None})
  ("progress", {"phase": str, "current": int, "total": int, "msg": str})
  ("decision", {...decision del agent_filter, ver pipeline...})
"""
import base64
import json
import os
import random
import re
import smtplib
import time
from datetime import datetime

import requests
from playwright.sync_api import sync_playwright

from jobhunter.agents.cv import agent_cv
from jobhunter.agents.email import agent_email
from jobhunter.agents.filter import agent_filter
from jobhunter.agents.query_generator import generate_queries
from jobhunter.ai.gemini import call_gemini_vision
from jobhunter.browser import find_chrome, kill_playwright_zombies
from jobhunter.config import save_config
from jobhunter.constants import BASE_DIR, SESSION_DIR
from jobhunter.cv.builder import generate_cv_pdf, get_cv_filename
from jobhunter.mailer import domain_accepts_mail, send_email
from jobhunter.offers import deduplicate_offers_by_title_company, was_already_applied
from jobhunter.scraper import do_linkedin_login, scrape_posts
from jobhunter.storage import save_kb


def _noop(name, payload):
    return None


def cfg_ready(cfg):
    """Equivalente a config.is_configured pero sobre un cfg ya cargado."""
    keys = ("gemini_api_key", "smtp_email", "smtp_password", "profile")
    return all(cfg.get(k) for k in keys)


def _error(kind, message, stats=None, decisions=None):
    return {
        "offers": [],
        "stats": stats or {},
        "decisions": decisions or [],
        "error": {"kind": kind, "message": message},
    }


def search_offers(cfg, kb, time_filter="24h", on_event=None, pace=True):
    """Fases 1-2 del pipeline: scrape + analisis + filtros. Sin UI.

    Retorna {"offers": [job_dict], "stats": dict, "decisions": [dict],
    "error": None | {"kind", "message"}}. error.kind:
    not_configured | no_session | session_expired | no_posts | cancelled.
    """
    emit = on_event or _noop

    if not cfg_ready(cfg):
        return _error("not_configured", "Falta configuracion. Ejecuta el setup.")
    if not os.path.exists(SESSION_DIR):
        return _error("no_session", "Sin sesion LinkedIn. Inicia sesion primero.")

    kill_playwright_zombies()
    queries = cfg.get("search_queries", ["enviar CV backend developer"])

    # ── Fase 1: Scrape ──
    all_posts = []
    seen = set()
    scrape_error = None
    emit("phase", {"phase": "scrape", "status": "start", "detail": "Buscando en LinkedIn",
                   "total": len(queries)})
    try:
        with sync_playwright() as p:
            chrome = find_chrome()
            browser = p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR, headless=True,
                viewport={"width": 1300, "height": 850}, executable_path=chrome,
                permissions=["clipboard-read", "clipboard-write"],
            )
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            if "login" in page.url or "signin" in page.url:
                browser.close()
                return _error("session_expired", "Sesion de LinkedIn expirada. Vuelve a iniciar sesion.")

            total_q = len(queries)
            for qi, query in enumerate(queries, 1):
                emit("progress", {"phase": "scrape", "current": qi - 1,
                                  "total": total_q, "msg": query})
                posts = scrape_posts(page, query, time_filter=time_filter)
                for pi in posts:
                    key = pi["text"][:150]
                    if key not in seen:
                        seen.add(key)
                        pi["query"] = query
                        all_posts.append(pi)
                if pace:
                    time.sleep(random.uniform(2, 5))

            # Screenshots (opcional, rapido)
            text_boxes = page.query_selector_all('span[data-testid="expandable-text-box"]')
            for post in all_posts:
                post["screenshots"] = []
                try:
                    if post["index"] < len(text_boxes):
                        ss = text_boxes[post["index"]].screenshot()
                        post["screenshots"].append(base64.b64encode(ss).decode())
                except Exception:
                    pass

            browser.close()
    except KeyboardInterrupt:
        return _error("cancelled", "Cancelado por el usuario.")
    except Exception as e:  # paridad con pipeline: el scrape parcial no es fatal
        scrape_error = str(e)

    posts_with_emails = [p for p in all_posts if p.get("emails_found")]
    stats = {
        "posts_scraped": len(all_posts),
        "posts_with_emails": len(posts_with_emails),
        "posts_no_emails": len(all_posts) - len(posts_with_emails),
        "scrape_error": scrape_error,
    }
    emit("phase", {"phase": "scrape", "status": "done",
                   "detail": str(len(all_posts)) + " posts, " + str(len(posts_with_emails)) + " con email",
                   "total": len(queries)})

    if not posts_with_emails:
        return _error("no_posts", "No se encontraron posts con email. Intenta un periodo mas amplio.",
                      stats=stats)

    # ── Fase 2: Analisis con IA ──
    offers = []
    decisions = []
    emit("phase", {"phase": "analyze", "status": "start", "detail": "Analizando ofertas",
                   "total": len(posts_with_emails)})
    for idx, post in enumerate(posts_with_emails):
        emit("progress", {"phase": "analyze", "current": idx,
                          "total": len(posts_with_emails),
                          "msg": post.get("text", "")[:60]})
        if len(post.get("text", "")) < 50:
            d = {
                "post_url": post.get("post_url"),
                "post_preview": post.get("text", "")[:200],
                "is_job": False,
                "is_relevant": False,
                "relevance_reason": "skipped (text < 50 chars)",
            }
            decisions.append(d)
            emit("decision", d)
            continue
        ss = post.get("screenshots", [None])[0] if post.get("screenshots") else None
        a = agent_filter(cfg, post["text"], ss)
        d = {
            "post_url": post.get("post_url"),
            "post_preview": post.get("text", "")[:200],
            "is_job": bool(a.get("is_job")),
            "is_relevant": bool(a.get("is_relevant", True)),
            "relevance_reason": a.get("relevance_reason", ""),
            "job_title": a.get("job_title"),
            "company": a.get("company"),
            "language": a.get("language"),
            "work_mode": a.get("work_mode"),
            "contact_email": a.get("contact_email"),
        }
        decisions.append(d)
        emit("decision", d)

        if a.get("is_job") and a.get("is_relevant", True):
            a["job_title"] = a.get("job_title") or "Software Developer"
            a["company"] = a.get("company") or "Empresa"
            a["post_url"] = post.get("post_url")
            a["query"] = post.get("query")
            a["author_url"] = post.get("author_url")
            a["author_name"] = post.get("author_name")
            offers.append(a)
        if pace:
            time.sleep(1.5)
    emit("phase", {"phase": "analyze", "status": "done",
                   "detail": str(len(offers)) + " ofertas", "total": len(posts_with_emails)})

    # ── Limpieza y filtros ──
    emit("phase", {"phase": "dedupe", "status": "start", "detail": "Filtrando duplicados",
                   "total": None})
    for o in offers:
        email = o.get("contact_email", "")
        if not email or str(email).lower() in ("null", "none", "n/a", "no encontrado"):
            o["contact_email"] = None

    offers_with_email = [o for o in offers if o.get("contact_email")]
    stats["filter_accepted"] = len(offers)
    stats["offers_no_email"] = len(offers) - len(offers_with_email)

    deduped = deduplicate_offers_by_title_company(offers_with_email)
    stats["batch_dupes"] = len(offers_with_email) - len(deduped)
    offers_with_email = deduped

    rejected = [r.lower() for r in kb.get("rejected_companies", [])]
    before_bl = len(offers_with_email)
    offers_with_email = [o for o in offers_with_email
                         if (o.get("company") or "").lower() not in rejected]
    stats["blacklisted"] = before_bl - len(offers_with_email)

    before_cd = len(offers_with_email)
    offers_with_email = [
        o for o in offers_with_email
        if not was_already_applied(kb.get("applications", []), o.get("company", ""),
                                   o.get("job_title", ""))
    ]
    stats["already_applied"] = before_cd - len(offers_with_email)
    stats["offers_final"] = len(offers_with_email)
    emit("phase", {"phase": "dedupe", "status": "done",
                   "detail": str(len(offers_with_email)) + " ofertas finales", "total": None})

    return {"offers": offers_with_email, "stats": stats, "decisions": decisions, "error": None}


CV_EXTRACT_PROMPT = """Lee este CV/resume y extrae TODA la informacion en JSON.
Adapta las categorias de skills al perfil real de la persona (no asumas que es tech).
{"name":"","title":"titulo profesional","email":"","phone":"","linkedin":"","portfolio":"","location":"",
"summary":"resumen profesional completo",
"skills": "objeto con categorias relevantes al perfil, ej: para tech {backend:[],frontend:[]}, para marketing {estrategia:[],herramientas:[]}, para diseno {tools:[],especialidades:[]}, etc.",
"experience":[{"company":"","role":"","period":"","description":"descripcion completa de logros y responsabilidades"}],
"education":[{"institution":"","degree":"","period":""}],
"projects":[{"name":"","description":"","tech":[]}],"achievements":[]}
SOLO JSON valido."""


def validate_gemini_key(key):
    """Valida una API key de Gemini con una llamada de prueba (como el setup)."""
    key = (key or "").replace(" ", "")
    if not key:
        return {"ok": False, "error": "La clave es obligatoria."}
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + key
        r = requests.post(url, json={"contents": [{"parts": [{"text": "test"}]}]}, timeout=10)
        r.raise_for_status()
        return {"ok": True, "error": None}
    except Exception as e:
        return {"ok": False, "error": "Clave invalida. Revisa que sea correcta. (" + str(e) + ")"}


def verify_smtp(email, password):
    """Verifica Gmail + App Password contra el SMTP real (como el setup)."""
    email = (email or "").strip()
    password = (password or "").replace(" ", "")
    if not re.match(r"^[^@]+@gmail\.com$", email):
        return {"ok": False, "error": "Debe ser una cuenta @gmail.com"}
    if not password or len(password) < 10:
        return {"ok": False, "error": "La contrasena de aplicacion tiene 16 caracteres"}
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(email, password)
        return {"ok": True, "error": None}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def extract_profile_from_cv(cfg, pdf_b64):
    """Extrae el perfil desde un CV en PDF (base64) con Gemini vision."""
    try:
        result = call_gemini_vision(cfg, CV_EXTRACT_PROMPT, pdf_b64, "application/pdf")
        parsed = json.loads(result)
        if not parsed.get("name"):
            return {"ok": False, "profile": None,
                    "error": "No se pudo extraer informacion del CV. Verifica que el PDF sea legible."}
        return {"ok": True, "profile": parsed, "error": None}
    except Exception as e:
        return {"ok": False, "profile": None, "error": str(e)}


def linkedin_login():
    """Login de LinkedIn para GUI (sin input de terminal). Retorna bool."""
    return do_linkedin_login(interactive=False)


def has_linkedin_session():
    """True si existe una sesion persistente de LinkedIn."""
    return os.path.exists(SESSION_DIR)


def regenerate_queries(cfg):
    """Genera queries de busqueda con IA, las guarda en cfg y persiste."""
    queries, from_ai = generate_queries(cfg)
    cfg["search_queries"] = queries
    save_config(cfg)
    return {"queries": queries, "from_ai": from_ai}


def prepare_application(cfg, job, test_email=None, on_event=None, pace=True):
    """Genera CV (PDF) + email para una oferta, con 3 reintentos por etapa.

    Retorna {"ok": bool, "cv_data": dict|None, "cv_path": str|None,
    "subject": str|None, "body": str|None, "error": str|None}.
    Con test_email el body ya incluye el banner de datos del reclutador.
    Eventos: ("apply_progress", {"stage": "cv"|"email", "job_title", "company"}).
    """
    emit = on_event or _noop
    title = (job.get("job_title") or "Posicion")[:80]
    company = (job.get("company") or "Empresa")[:40]
    result = {"ok": False, "cv_data": None, "cv_path": None,
              "subject": None, "body": None, "error": None}

    emit("apply_progress", {"stage": "cv", "job_title": title, "company": company})
    cv_data = None
    cv_path = None
    try:
        for retry in range(3):
            try:
                cv_data = agent_cv(cfg, job)
                cv_fn = get_cv_filename(company, title)
                cv_path = os.path.join(BASE_DIR, "output", "cvs", cv_fn)
                os.makedirs(os.path.dirname(cv_path), exist_ok=True)
                generate_cv_pdf(
                    cv_data,
                    cfg["profile"],
                    cv_path,
                    title,
                    company,
                    language=job.get("language", "es"),
                    template=cfg.get("cv_template", "modern"),
                )
                break
            except Exception:
                if retry == 2:
                    raise
                if pace:
                    time.sleep(5)
        result["cv_data"] = cv_data
        result["cv_path"] = cv_path

        emit("apply_progress", {"stage": "email", "job_title": title, "company": company})
        edata = None
        for retry in range(3):
            try:
                edata = agent_email(cfg, job, cv_data=cv_data)
                break
            except Exception:
                if retry == 2:
                    raise
                if pace:
                    time.sleep(5)
    except Exception as e:
        result["error"] = str(e)
        return result

    body = edata["body"]
    if test_email:
        rec_email = job.get("contact_email")
        banner = "--- RECLUTADOR: " + str(job.get("contact_name", "?")) + \
                 " | EMAIL: " + str(rec_email or "?") + " | " + company + " ---"
        body = banner + "\n\n" + body

    result["ok"] = True
    result["subject"] = edata["subject"]
    result["body"] = body
    return result


def check_recipient(email):
    """True si el dominio recibe correo, False si no, None si no verificable."""
    return domain_accepts_mail(email)


def send_application(cfg, kb, job, prepared, to, mode="run", recruiter_email=None):
    """Envia la aplicacion preparada y la registra en kb['applications'].

    NO persiste kb a disco (el caller decide cuando). Retorna
    {"status": "sent"|"error", "error": str|None, "entry": dict|None}.
    """
    title = (job.get("job_title") or "Posicion")[:80]
    company = (job.get("company") or "Empresa")[:40]
    if recruiter_email is None:
        recruiter_email = job.get("contact_email")
    try:
        send_email(cfg, to, prepared["subject"], prepared["body"], prepared["cv_path"])
    except Exception as e:
        return {"status": "error", "error": str(e), "entry": None}
    entry = {
        "date": datetime.now().isoformat(),
        "job_title": title,
        "company": company,
        "recruiter_email": recruiter_email,
        "sent_to": to,
        "mode": mode,
        "post_url": job.get("post_url"),
        "subject": prepared["subject"],
        "query": job.get("query"),
        "author_url": job.get("author_url"),
        "author_name": job.get("author_name"),
        "cv_path": prepared.get("cv_path"),
    }
    kb["applications"].append(entry)
    return {"status": "sent", "error": None, "entry": entry}


def record_run(kb, mode, posts, offers, sent, generated=None, dry_run=False):
    """Appendea el run al historial y persiste knowledge.json (shape actual)."""
    entry = {
        "date": datetime.now().isoformat(),
        "mode": "dry-run" if dry_run else mode,
        "posts": posts,
        "offers": offers,
        "sent": 0 if dry_run else sent,
    }
    if dry_run:
        entry["generated"] = generated or 0
    kb["runs"].append(entry)
    save_kb(kb)
    return entry


def write_run_log(mode, stats, decisions, results, sent, errors):
    """Escribe el log JSON del run en output/logs (shape actual). Retorna la ruta."""
    log = os.path.join(BASE_DIR, "output", "logs",
                       "run_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    reject_reasons = {}
    for d in decisions:
        if not (d.get("is_job") and d.get("is_relevant", True)):
            reason = d.get("relevance_reason") or "(sin razon)"
            reject_reasons[reason] = reject_reasons.get(reason, 0) + 1
    accepted = sum(1 for d in decisions if d.get("is_job") and d.get("is_relevant", True))
    log_data = {
        "run_date": datetime.now().isoformat(),
        "mode": mode,
        "stats": {
            "posts_scraped": stats.get("posts_scraped", 0),
            "posts_with_emails": stats.get("posts_with_emails", 0),
            "filter_accepted": accepted,
            "filter_rejected": len(decisions) - accepted,
            "reject_reasons_top": dict(sorted(reject_reasons.items(), key=lambda x: -x[1])[:10]),
            "applications_attempted": len(results),
            "sent": sent,
            "errors": errors,
        },
        "filter_decisions": decisions,
        "applications": results,
    }
    with open(log, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)
    return log
