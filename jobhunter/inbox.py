# -*- coding: utf-8 -*-
"""Lectura de Gmail via IMAP para conciliar respuestas y rebotes.

Una sola conexion y una sola busqueda SINCE; los rebotes se detectan por el
remitente (mailer-daemon/postmaster) y solo para esos se descarga el cuerpo.
"""
import email
import imaplib
from datetime import datetime
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
BOUNCE_SENDERS = ("mailer-daemon", "postmaster")
FETCH_BATCH = 100


def imap_date(d):
    """Fecha IMAP DD-Mon-YYYY independiente del locale."""
    return "%02d-%s-%d" % (d.day, MONTHS[d.month - 1], d.year)


def _decode_subject(raw):
    try:
        return str(make_header(decode_header(raw or "")))
    except Exception:
        return raw or ""


def _parse_header_blob(blob):
    msg = email.message_from_bytes(blob)
    from_email = (parseaddr(msg.get("From", ""))[1] or "").lower()
    try:
        mdate = parsedate_to_datetime(msg.get("Date", ""))
        if mdate is not None and mdate.tzinfo is not None:
            mdate = mdate.astimezone().replace(tzinfo=None)
    except Exception:
        mdate = None
    return {
        "from_email": from_email,
        "date": mdate,
        "subject": _decode_subject(msg.get("Subject", "")),
    }


def fetch_inbox(cfg, since):
    """Retorna (headers, bounce_texts) del INBOX desde `since` (datetime)."""
    conn = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    try:
        conn.login(cfg["smtp_email"], cfg["smtp_password"])
        conn.select("INBOX", readonly=True)
        _, data = conn.search(None, "SINCE", imap_date(since))
        ids = data[0].split() if data and data[0] else []

        headers = []
        bounce_ids = []
        for start in range(0, len(ids), FETCH_BATCH):
            chunk = ids[start:start + FETCH_BATCH]
            idset = b",".join(chunk)
            _, parts = conn.fetch(idset, "(BODY.PEEK[HEADER.FIELDS (FROM DATE SUBJECT)])")
            for part in parts:
                if not isinstance(part, tuple) or len(part) < 2 or part[1] is None:
                    continue
                entry = _parse_header_blob(part[1])
                headers.append(entry)
                mid = part[0].split()[0] if part[0] else None
                if mid and any(b in entry["from_email"] for b in BOUNCE_SENDERS):
                    bounce_ids.append(mid)

        bounce_texts = []
        for mid in bounce_ids:
            _, parts = conn.fetch(mid, "(BODY.PEEK[TEXT])")
            for part in parts:
                if isinstance(part, tuple) and len(part) > 1 and part[1]:
                    bounce_texts.append(part[1].decode("utf-8", errors="replace"))
        return headers, bounce_texts
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def _app_date(app):
    try:
        return datetime.fromisoformat(app.get("date", ""))
    except Exception:
        return datetime.min


def reconcile(applications, headers, bounce_texts, now=None):
    """Cruza aplicaciones con el buzon. Muta las apps; retorna resumen.

    Precedencia: replied > bounced. La respuesta se asigna a la app mas
    reciente enviada antes de la fecha de la respuesta.
    """
    now = now or datetime.now()
    summary = {"checked": 0, "replied": 0, "bounced": 0, "no_reply": 0}

    candidates = [
        a for a in (applications or [])
        if a.get("recruiter_email") and a.get("sent_to") == a.get("recruiter_email")
    ]
    summary["checked"] = len(candidates)

    by_sender = {}
    for h in headers or []:
        if h.get("from_email"):
            by_sender.setdefault(h["from_email"].lower(), []).append(h)

    for sender, msgs in by_sender.items():
        apps_to = [a for a in candidates if (a.get("recruiter_email") or "").lower() == sender]
        if not apps_to:
            continue
        for m in sorted(msgs, key=lambda x: x.get("date") or now):
            mdate = m.get("date") or now
            prior = [a for a in apps_to if a.get("status") != "replied" and _app_date(a) <= mdate]
            if not prior:
                continue
            target = max(prior, key=_app_date)
            target["status"] = "replied"
            target["reply_date"] = mdate.isoformat()
            target["reply_subject"] = m.get("subject") or ""
            target["status_checked_at"] = now.isoformat()
            summary["replied"] += 1

    bounce_blob = "\n".join(bounce_texts or []).lower()
    for app in candidates:
        if app.get("status") == "replied":
            continue
        addr = (app.get("sent_to") or "").lower()
        if addr and addr in bounce_blob:
            app["status"] = "bounced"
            summary["bounced"] += 1
        else:
            app["status"] = "no_reply"
            summary["no_reply"] += 1
        app["status_checked_at"] = now.isoformat()

    return summary
