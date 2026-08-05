"""Envio de correos via Gmail SMTP con retry, y chequeo MX del destinatario."""
import os
import random
import smtplib
import socket
import struct
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Consulta DNS MX cruda por UDP (stdlib): nslookup tiene salida localizada y
# dnspython seria una dependencia nueva. Solo se necesita saber si hay
# respuestas MX, no leerlas.
DNS_RESOLVER = ("8.8.8.8", 53)


def _build_mx_query(domain, txid):
    header = struct.pack(">HHHHHH", txid, 0x0100, 1, 0, 0, 0)
    qname = b"".join(bytes([len(p)]) + p.encode("idna") for p in domain.split("."))
    return header + qname + b"\x00" + struct.pack(">HH", 15, 1)


def _parse_mx_response(data, txid):
    if not data or len(data) < 12:
        return None
    rid, flags, _qd, ancount, _ns, _ar = struct.unpack(">HHHHHH", data[:12])
    if rid != txid:
        return None
    rcode = flags & 0xF
    if rcode == 3:
        return False
    if rcode != 0:
        return None
    return ancount > 0


def domain_accepts_mail(email, resolver=DNS_RESOLVER, timeout=3.0):
    """True si el dominio del email tiene MX, False si no existe/no recibe correo,
    None si no se pudo verificar (nunca debe bloquear el envio)."""
    domain = (email or "").rsplit("@", 1)[-1].strip().lower().rstrip(".")
    if "@" not in (email or "") or not domain or "." not in domain:
        return False
    try:
        txid = random.randint(0, 0xFFFF)
        pkt = _build_mx_query(domain, txid)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        try:
            s.sendto(pkt, resolver)
            data, _ = s.recvfrom(2048)
        finally:
            s.close()
        return _parse_mx_response(data, txid)
    except Exception:
        return None


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
