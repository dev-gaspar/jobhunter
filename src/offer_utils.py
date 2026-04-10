import re
from datetime import datetime, timedelta


def normalize_text(value):
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def extract_emails(text):
    pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    return list(set(re.findall(pattern, text or "")))


def was_already_applied(applications, company, job_title, recruiter_email=None, cooldown_days=30):
    cutoff = datetime.now() - timedelta(days=cooldown_days)
    normalized_company = normalize_text(company)
    normalized_title = normalize_text(job_title)
    normalized_email = (recruiter_email or "").strip().lower()

    for app in applications or []:
        app_company = normalize_text(app.get("company", ""))
        app_title = normalize_text(app.get("job_title", ""))
        app_email = (app.get("recruiter_email") or "").strip().lower()
        # Match by company+title OR by same recruiter email + same company
        matched = (normalized_company == app_company and normalized_title == app_title)
        if not matched and normalized_email and app_email:
            matched = (normalized_email == app_email and normalized_company == app_company)
        if matched:
            try:
                app_date = datetime.fromisoformat(app["date"])
                if app_date > cutoff:
                    return True
            except Exception:
                return True
    return False


def deduplicate_offers_by_title_company(offers):
    seen = set()
    deduped = []
    for offer in offers or []:
        key = (
            normalize_text(offer.get("job_title", "")),
            normalize_text(offer.get("company", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(offer)
    return deduped
