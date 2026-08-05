# -*- coding: utf-8 -*-
"""Agregados de historial para el dashboard local (funciones puras sobre kb)."""
from datetime import datetime, timedelta


def app_status(app):
    """Estado efectivo de una aplicacion: test / replied / bounced / no_reply / unknown."""
    rec = app.get("recruiter_email")
    if app.get("mode") == "test":
        return "test"
    if rec and app.get("sent_to") and app["sent_to"] != rec:
        return "test"
    return app.get("status") or "unknown"


def _parse_date(value):
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def build_dashboard_data(kb, now=None):
    """Calcula totales, tasas, series semanales y listado para /api/data."""
    now = now or datetime.now()
    counts = {"sent": 0, "replied": 0, "bounced": 0, "no_reply": 0, "unknown": 0}
    week_counts = {}
    rows = []

    for app in kb.get("applications", []):
        st = app_status(app)
        if st == "test":
            continue
        counts["sent"] += 1
        bucket = st if st in ("replied", "bounced", "no_reply") else "unknown"
        counts[bucket] += 1

        d = _parse_date(app.get("date") or "")
        days = (now - d).days if d else None
        if d:
            week = d.strftime("%G-W%V")
            week_counts[week] = week_counts.get(week, 0) + 1

        rows.append({
            "date": app.get("date"),
            "job_title": app.get("job_title"),
            "company": app.get("company"),
            "sent_to": app.get("sent_to"),
            "status": st,
            "days_since_sent": days,
            "reply_date": app.get("reply_date"),
        })

    rows.sort(key=lambda r: r.get("date") or "", reverse=True)

    delivered = counts["sent"] - counts["bounced"]
    reply_rate = round(counts["replied"] * 100.0 / delivered, 1) if delivered else 0.0
    bounce_rate = round(counts["bounced"] * 100.0 / counts["sent"], 1) if counts["sent"] else 0.0

    week_keys = []
    cursor = now
    for _ in range(12):
        week_keys.append(cursor.strftime("%G-W%V"))
        cursor = cursor - timedelta(days=7)
    week_keys.reverse()
    weeks = [{"week": k, "sent": week_counts.get(k, 0)} for k in week_keys]

    runs = [
        {"date": r.get("date"), "mode": r.get("mode"), "posts": r.get("posts", 0),
         "offers": r.get("offers", 0), "sent": r.get("sent", 0)}
        for r in kb.get("runs", [])
    ]

    return {
        "totals": counts,
        "reply_rate": reply_rate,
        "bounce_rate": bounce_rate,
        "weeks": weeks,
        "runs": runs,
        "applications": rows,
        "generated_at": now.isoformat(),
    }
