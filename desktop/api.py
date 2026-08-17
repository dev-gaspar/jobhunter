# -*- coding: utf-8 -*-
"""Puente JS <-> Python de la app de escritorio.

NUNCA importa webview: app.py inyecta emit (evaluate_js) y file_dialog.
Todos los metodos retornan {"ok": bool, "data": ..., "error": str|None}.
Las operaciones largas corren en un hilo y reportan por eventos via emit.
"""
import base64
import json
import os
import re
import threading
import webbrowser

from jobhunter import service
from jobhunter.ai.gemini import call_gemini
from jobhunter.config import load_config, save_config
from jobhunter.constants import BASE_DIR, GEMINI_MODELS, VERSION
from jobhunter.storage import load_kb

from desktop import updates

MODE_OPTIONS = {"1": "Remoto", "2": "Hibrido", "3": "Presencial", "4": "Cualquiera"}


def _ok(data=None):
    return {"ok": True, "data": data, "error": None}


def _err(message, data=None):
    return {"ok": False, "data": data, "error": message}


def _mask(value):
    if not value:
        return ""
    v = str(value)
    if len(v) <= 4:
        return "***"
    return v[:4] + "***"


class Bridge:
    """API expuesta a la UI. emit(name, payload) empuja eventos a JS."""

    def __init__(self, emit, file_dialog=None, quit_app=None, sync=False):
        self._emit = emit
        self._file_dialog = file_dialog
        self._quit_app = quit_app
        self._sync = sync
        self._lock = threading.Lock()
        self._op = None
        self._run = None  # estado de la busqueda en curso (cfg, kb, offers...)

    # ── infraestructura ──

    def _start_op(self, name):
        with self._lock:
            if self._op:
                return False
            self._op = name
            return True

    def _end_op(self):
        with self._lock:
            self._op = None

    def _run_async(self, fn):
        if self._sync:
            try:
                fn()
            finally:
                self._end_op()
            return
        def wrapper():
            try:
                fn()
            except Exception as e:
                try:
                    self._emit("fatal_error", {"message": str(e)})
                except Exception:
                    pass
            finally:
                self._end_op()
        threading.Thread(target=wrapper, daemon=True).start()

    # ── estado ──

    def get_state(self):
        try:
            cfg = load_config()
            profile = cfg.get("profile") or {}
            required = ("gemini_api_key", "smtp_email", "smtp_password", "profile")
            from jobhunter.cv.templates import TEMPLATES, DEFAULT_TEMPLATE
            data = {
                "configured": all(cfg.get(k) for k in required),
                "version": VERSION,
                "has_session": service.has_linkedin_session(),
                "profile_name": profile.get("name", ""),
                "profile": profile,
                "smtp_email": cfg.get("smtp_email", ""),
                "smtp_set": bool(cfg.get("smtp_password")),
                "gemini_key_masked": _mask(cfg.get("gemini_api_key", "")),
                "model": cfg.get("gemini_model", "gemini-2.5-flash"),
                "models": GEMINI_MODELS,
                "cv_template": cfg.get("cv_template", DEFAULT_TEMPLATE),
                "templates": [
                    {"key": k, "name": t["name"], "description": t["description"]}
                    for k, t in TEMPLATES.items()
                ],
                "job_types": cfg.get("job_types_raw", ""),
                "search_languages": cfg.get("search_languages", "3"),
                "user_languages": cfg.get("user_languages", []),
                "work_mode": cfg.get("work_mode", "4"),
                "user_location": cfg.get("user_location", ""),
                "links": {
                    "portfolio": profile.get("portfolio", ""),
                    "linkedin": profile.get("linkedin", ""),
                },
                "cv_path": cfg.get("cv_path", ""),
                "queries_count": len(cfg.get("search_queries", [])),
                "onboarding": {
                    "has_key": bool(cfg.get("gemini_api_key")),
                    "has_profile": bool(profile.get("name")),
                    "has_cv": bool(cfg.get("cv_path")),
                    "has_job_types": bool(cfg.get("job_types_raw")),
                    "has_languages": bool(cfg.get("user_languages")),
                    "has_smtp": bool(cfg.get("smtp_email") and cfg.get("smtp_password")),
                    "has_session": service.has_linkedin_session(),
                    "has_queries": bool(cfg.get("search_queries")),
                },
            }
            return _ok(data)
        except Exception as e:
            return _err(str(e))

    # ── onboarding ──

    def validate_gemini_key(self, key):
        try:
            res = service.validate_gemini_key(key)
            if not res["ok"]:
                return _err(res["error"])
            cfg = load_config()
            cfg["gemini_api_key"] = (key or "").replace(" ", "")
            save_config(cfg)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def save_model(self, model):
        try:
            if model not in GEMINI_MODELS:
                return _err("Modelo desconocido")
            cfg = load_config()
            cfg["gemini_model"] = model
            save_config(cfg)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def pick_cv_file(self):
        try:
            if not self._file_dialog:
                return _err("Selector de archivos no disponible")
            path = self._file_dialog()
            if not path:
                return _ok(None)  # cancelado
            return _ok({"path": path})
        except Exception as e:
            return _err(str(e))

    def extract_cv_from_path(self, path):
        try:
            if not path or not os.path.exists(path):
                return _err("No se encontro el archivo: " + str(path))
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            cfg = load_config()
            res = service.extract_profile_from_cv(cfg, b64)
            if not res["ok"]:
                return _err(res["error"])
            cfg["cv_path"] = path
            save_config(cfg)
            return _ok({"profile": res["profile"]})
        except PermissionError:
            return _err("Sin permisos para leer el archivo. Copialo a otra carpeta e intenta de nuevo.")
        except Exception as e:
            return _err(str(e))

    def extract_cv_b64(self, filename, b64):
        try:
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename or "cv.pdf")
            if not safe.lower().endswith(".pdf"):
                safe += ".pdf"
            dest = os.path.join(BASE_DIR, "cv_" + safe)
            with open(dest, "wb") as f:
                f.write(base64.b64decode(b64))
            return self.extract_cv_from_path(dest)
        except Exception as e:
            return _err(str(e))

    def save_profile(self, profile):
        try:
            cfg = load_config()
            prev = cfg.get("profile") or {}
            if prev.get("portfolio") and not profile.get("portfolio"):
                profile["portfolio"] = prev["portfolio"]
            if prev.get("linkedin") and not profile.get("linkedin"):
                profile["linkedin"] = prev["linkedin"]
            cfg["profile"] = profile
            save_config(cfg)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def save_links(self, portfolio, linkedin):
        try:
            cfg = load_config()
            profile = cfg.get("profile") or {}
            profile["portfolio"] = (portfolio or "").strip()
            profile["linkedin"] = (linkedin or "").strip()
            cfg["profile"] = profile
            save_config(cfg)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def suggest_job_types(self):
        try:
            cfg = load_config()
            profile = cfg.get("profile") or {}
            if not (cfg.get("gemini_api_key") and profile.get("skills")):
                return _ok([])
            s = json.dumps(profile.get("skills", {}))
            e = json.dumps(profile.get("experience", [])[:3])
            prompt = ("Basado en skills: " + s + " y experiencia: " + e +
                      ", sugiere 6 tipos de empleo. JSON array: [\"tipo1\",\"tipo2\"]")
            result = call_gemini(cfg, prompt)
            suggestions = json.loads(result)
            if not isinstance(suggestions, list):
                return _ok([])
            return _ok([str(x) for x in suggestions[:6]])
        except Exception:
            return _ok([])

    def save_job_types(self, raw):
        try:
            cfg = load_config()
            cfg["job_types_raw"] = (raw or "").strip() or "software developer"
            save_config(cfg)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def save_languages(self, search_languages, user_languages):
        try:
            cfg = load_config()
            cfg["search_languages"] = search_languages if search_languages in ("1", "2", "3") else "3"
            langs = []
            for item in user_languages or []:
                lang = (item.get("language") or "").strip()
                level = (item.get("level") or "Nativo").strip()
                if lang:
                    langs.append({"language": lang, "level": level})
            cfg["user_languages"] = langs
            save_config(cfg)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def save_work_mode(self, mode, location):
        try:
            cfg = load_config()
            if mode not in MODE_OPTIONS:
                mode = "4"
            cfg["work_mode"] = mode
            cfg["work_mode_label"] = MODE_OPTIONS[mode]
            if mode in ("2", "3"):
                cfg["user_location"] = (location or "").strip()
            else:
                cfg["user_location"] = cfg.get("user_location", "")
            save_config(cfg)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def save_template(self, name):
        try:
            from jobhunter.cv.templates import TEMPLATES
            if name not in TEMPLATES:
                return _err("Plantilla desconocida")
            cfg = load_config()
            cfg["cv_template"] = name
            save_config(cfg)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def verify_smtp(self, email, password):
        try:
            res = service.verify_smtp(email, password)
            if not res["ok"]:
                return _err(res["error"])
            cfg = load_config()
            cfg["smtp_email"] = (email or "").strip()
            cfg["smtp_password"] = (password or "").replace(" ", "")
            save_config(cfg)
            return _ok()
        except Exception as e:
            return _err(str(e))

    def linkedin_login_start(self):
        if not self._start_op("linkedin"):
            return _err("Hay una operacion en curso")
        def work():
            ok = False
            try:
                ok = service.linkedin_login()
            finally:
                self._emit("linkedin_done", {"ok": bool(ok)})
        self._run_async(work)
        return _ok()

    def finish_onboarding(self):
        if not self._start_op("queries"):
            return _err("Hay una operacion en curso")
        def work():
            cfg = load_config()
            res = service.regenerate_queries(cfg)
            self._emit("onboarding_done", {
                "queries_count": len(res["queries"]),
                "from_ai": res["from_ai"],
            })
        self._run_async(work)
        return _ok()

    # ── busqueda / aplicacion ──

    def start_search(self, time_filter, test_email=None):
        if not self._start_op("search"):
            return _err("Hay una operacion en curso")
        cfg = load_config()
        kb = load_kb()
        self._run = {
            "cfg": cfg, "kb": kb,
            "mode": "test" if test_email else "run",
            "test_email": test_email or None,
            "offers": {}, "prepared": {},
            "stats": {}, "decisions": [],
            "results": [], "sent": 0, "errors": 0, "skipped": 0,
        }
        def work():
            result = service.search_offers(cfg, kb, time_filter=time_filter,
                                           on_event=self._emit, pace=True)
            self._run["stats"] = result["stats"]
            self._run["decisions"] = result["decisions"]
            if result["error"]:
                payload = dict(result["error"])
                payload["stats"] = result["stats"]
                self._emit("search_error", payload)
                return
            offers_out = []
            for i, offer in enumerate(result["offers"], 1):
                offer["id"] = i
                self._run["offers"][i] = offer
                offers_out.append(offer)
            self._emit("search_done", {"offers": offers_out, "stats": result["stats"]})
        self._run_async(work)
        return _ok()

    def prepare_offer(self, offer_id):
        if not self._run:
            return _err("No hay una busqueda activa")
        job = self._run["offers"].get(offer_id)
        if not job:
            return _err("Oferta desconocida")
        if not self._start_op("prepare"):
            return _err("Hay una operacion en curso")
        def work():
            prepared = service.prepare_application(
                self._run["cfg"], job, test_email=self._run["test_email"],
                on_event=self._emit)
            if not prepared["ok"]:
                self._run["errors"] += 1
                self._run["results"].append({
                    "job_title": job.get("job_title"), "company": job.get("company"),
                    "error": prepared["error"],
                })
                self._emit("prepare_error", {"id": offer_id, "error": prepared["error"]})
                return
            self._run["prepared"][offer_id] = prepared
            self._emit("preview_ready", {
                "id": offer_id,
                "to": self._run["test_email"] or job.get("contact_email"),
                "subject": prepared["subject"],
                "body": prepared["body"],
                "cv_path": prepared["cv_path"],
                "cv_name": os.path.basename(prepared["cv_path"]) if prepared["cv_path"] else "",
            })
        self._run_async(work)
        return _ok()

    def send_offer(self, offer_id, subject=None, alt_email=None):
        if not self._run:
            return _err("No hay una busqueda activa")
        job = self._run["offers"].get(offer_id)
        prepared = self._run["prepared"].get(offer_id)
        if not job or not prepared:
            return _err("La oferta no esta preparada")
        if subject:
            prepared["subject"] = subject
        test_email = self._run["test_email"]
        to = test_email or alt_email or job.get("contact_email")
        recruiter_email = alt_email or job.get("contact_email")
        if not test_email and not alt_email:
            if service.check_recipient(to) is False:
                return _err("mx", data={"recruiter_email": recruiter_email})
        if not self._start_op("send"):
            return _err("Hay una operacion en curso")
        def work():
            res = service.send_application(
                self._run["cfg"], self._run["kb"], job, prepared, to,
                self._run["mode"], recruiter_email)
            record = {
                "job_title": job.get("job_title"), "company": job.get("company"),
                "recruiter_email": recruiter_email, "sent_to": to,
                "cv_path": prepared.get("cv_path"),
            }
            if res["status"] == "sent":
                self._run["sent"] += 1
            else:
                self._run["errors"] += 1
                record["error"] = res["error"]
            self._run["results"].append(record)
            self._emit("send_result", {"id": offer_id, "status": res["status"],
                                       "error": res["error"]})
        self._run_async(work)
        return _ok()

    def skip_offer(self, offer_id):
        if not self._run:
            return _err("No hay una busqueda activa")
        job = self._run["offers"].get(offer_id)
        if not job:
            return _err("Oferta desconocida")
        self._run["skipped"] += 1
        self._run["results"].append({
            "job_title": job.get("job_title"), "company": job.get("company"),
            "skipped": True,
        })
        return _ok()

    def finish_run(self):
        if not self._run:
            return _err("No hay una busqueda activa")
        try:
            run = self._run
            service.record_run(run["kb"], run["mode"],
                               posts=run["stats"].get("posts_scraped", 0),
                               offers=len(run["offers"]), sent=run["sent"])
            service.write_run_log(run["mode"], run["stats"], run["decisions"],
                                  run["results"], run["sent"], run["errors"])
            summary = {
                "total": len(run["offers"]),
                "sent": run["sent"],
                "skipped": run["skipped"],
                "errors": run["errors"],
            }
            self._run = None
            return _ok(summary)
        except Exception as e:
            return _err(str(e))

    # ── historial / utilidades ──

    def get_history(self, last=50, company=None):
        try:
            kb = load_kb()
            apps = list(kb.get("applications", []))
            apps.sort(key=lambda a: a.get("date", ""), reverse=True)
            if company:
                needle = company.lower()
                apps = [a for a in apps if needle in (a.get("company") or "").lower()]
            if last:
                apps = apps[:last]
            rows = []
            for a in apps:
                rows.append({
                    "date": (a.get("date") or "")[:10],
                    "job_title": a.get("job_title", ""),
                    "company": a.get("company", ""),
                    "recruiter_email": a.get("recruiter_email") or a.get("sent_to", ""),
                    "sent_to": a.get("sent_to", ""),
                    "mode": (a.get("mode") or "run").lower(),
                    "post_url": a.get("post_url"),
                    "subject": a.get("subject", ""),
                    "cv_path": a.get("cv_path"),
                })
            return _ok(rows)
        except Exception as e:
            return _err(str(e))

    def open_cv(self, path):
        try:
            if not path:
                return _err("Sin archivo")
            full = os.path.abspath(path)
            allowed = os.path.abspath(os.path.join(BASE_DIR, "output", "cvs"))
            if not full.startswith(allowed):
                return _err("Ruta no permitida")
            if not os.path.exists(full):
                return _err("El archivo ya no existe")
            os.startfile(full)  # noqa: S606 — visor del sistema
            return _ok()
        except Exception as e:
            return _err(str(e))

    def open_url(self, url):
        try:
            if not str(url).startswith(("http://", "https://")):
                return _err("URL no permitida")
            webbrowser.open(url)
            return _ok()
        except Exception as e:
            return _err(str(e))

    # ── updates ──

    def check_updates(self):
        try:
            return _ok(updates.get_latest(VERSION))
        except Exception as e:
            return _err(str(e))

    def download_update(self, url):
        if not str(url).startswith("https://github.com/dev-gaspar/jobhunter/"):
            return _err("URL de actualizacion no valida")
        if not self._start_op("update"):
            return _err("Hay una operacion en curso")
        def work():
            try:
                def prog(done, total):
                    self._emit("update_progress", {"done": done, "total": total})
                dest = updates.download_installer(url, on_progress=prog)
                os.startfile(dest)  # noqa: S606 — lanza el instalador
                self._emit("update_launched", {})
                if self._quit_app:
                    self._quit_app()
            except Exception as e:
                self._emit("update_error", {"message": str(e)})
        self._run_async(work)
        return _ok()
