"""Envio de correos via Gmail SMTP con retry."""
import os
import smtplib
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(cfg, to, subject, body, cv_path=None, max_retries=3):
    """Envia email via Gmail SMTP (smtp.gmail.com:587, STARTTLS).

    Adjunta PDF opcionalmente. Reintenta hasta max_retries con 3s de pausa.
    """
    msg = MIMEMultipart()
    msg["From"] = f"{cfg['profile'].get('name') or 'Candidato'} <{cfg['smtp_email']}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if cv_path and os.path.exists(cv_path):
        with open(cv_path, "rb") as f:
            a = MIMEApplication(f.read(), _subtype="pdf")
            a.add_header("Content-Disposition", "attachment", filename=os.path.basename(cv_path))
            msg.attach(a)

    for attempt in range(max_retries):
        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as s:
                s.starttls()
                s.login(cfg["smtp_email"], cfg["smtp_password"])
                s.send_message(msg)
            return
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(3)
