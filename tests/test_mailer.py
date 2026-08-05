import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from jobhunter.mailer import send_email


def _cfg():
    return {
        "smtp_email": "sender@gmail.com",
        "smtp_password": "fakepass",
        "profile": {"name": "Jose Test"},
    }


class MailerTests(unittest.TestCase):
    @patch("jobhunter.mailer.smtplib.SMTP")
    def test_send_email_basic(self, mock_smtp):
        ctx = MagicMock()
        mock_smtp.return_value.__enter__.return_value = ctx
        send_email(_cfg(), "to@x.com", "Hola", "Cuerpo")
        ctx.starttls.assert_called_once()
        ctx.login.assert_called_once_with("sender@gmail.com", "fakepass")
        ctx.send_message.assert_called_once()
        msg = ctx.send_message.call_args.args[0]
        self.assertEqual(msg["To"], "to@x.com")
        self.assertEqual(msg["Subject"], "Hola")
        self.assertIn("Jose Test", msg["From"])

    @patch("jobhunter.mailer.smtplib.SMTP")
    def test_send_email_with_pdf_attachment(self, mock_smtp):
        ctx = MagicMock()
        mock_smtp.return_value.__enter__.return_value = ctx
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 fake")
            pdf_path = f.name
        try:
            send_email(_cfg(), "to@x.com", "S", "B", cv_path=pdf_path)
            msg = ctx.send_message.call_args.args[0]
            parts = msg.get_payload()
            self.assertEqual(len(parts), 2)
            self.assertIn(os.path.basename(pdf_path), parts[1].get("Content-Disposition"))
        finally:
            os.unlink(pdf_path)

    @patch("jobhunter.mailer.time.sleep")
    @patch("jobhunter.mailer.smtplib.SMTP")
    def test_retry_on_failure(self, mock_smtp, _sleep):
        fail_ctx = MagicMock()
        fail_ctx.login.side_effect = Exception("auth failed")
        ok_ctx = MagicMock()
        mock_smtp.return_value.__enter__.side_effect = [fail_ctx, ok_ctx]
        send_email(_cfg(), "to@x.com", "S", "B")
        self.assertEqual(mock_smtp.call_count, 2)

    @patch("jobhunter.mailer.time.sleep")
    @patch("jobhunter.mailer.smtplib.SMTP")
    def test_raises_after_max_retries(self, mock_smtp, _sleep):
        fail_ctx = MagicMock()
        fail_ctx.login.side_effect = Exception("auth failed")
        mock_smtp.return_value.__enter__.return_value = fail_ctx
        with self.assertRaises(Exception):
            send_email(_cfg(), "to@x.com", "S", "B", max_retries=2)

    @patch("jobhunter.mailer.smtplib.SMTP")
    def test_uses_generic_name_when_profile_name_missing(self, mock_smtp):
        ctx = MagicMock()
        mock_smtp.return_value.__enter__.return_value = ctx
        cfg = _cfg()
        cfg["profile"] = {}
        send_email(cfg, "to@x.com", "S", "B")
        msg = ctx.send_message.call_args.args[0]
        self.assertIn("Candidato", msg["From"])


class DomainAcceptsMailTests(unittest.TestCase):
    def test_query_packet_ends_with_mx_qtype(self):
        from jobhunter.mailer import _build_mx_query
        pkt = _build_mx_query("acme.com", 0x1234)
        self.assertEqual(pkt[:2], b"\x12\x34")
        self.assertTrue(pkt.endswith(b"\x00\x0f\x00\x01"))
        self.assertIn(b"\x04acme\x03com\x00", pkt)

    def _resp(self, txid=0x1234, rcode=0, ancount=0):
        import struct
        flags = 0x8180 | rcode
        return struct.pack(">HHHHHH", txid, flags, 1, ancount, 0, 0) + b"\x00" * 8

    def test_parse_answers_means_mx_exists(self):
        from jobhunter.mailer import _parse_mx_response
        self.assertTrue(_parse_mx_response(self._resp(ancount=2), 0x1234))

    def test_parse_nxdomain_is_false(self):
        from jobhunter.mailer import _parse_mx_response
        self.assertIs(_parse_mx_response(self._resp(rcode=3), 0x1234), False)

    def test_parse_no_answers_is_false(self):
        from jobhunter.mailer import _parse_mx_response
        self.assertIs(_parse_mx_response(self._resp(ancount=0), 0x1234), False)

    def test_parse_wrong_txid_is_none(self):
        from jobhunter.mailer import _parse_mx_response
        self.assertIsNone(_parse_mx_response(self._resp(txid=0x9999), 0x1234))

    def test_parse_short_data_is_none(self):
        from jobhunter.mailer import _parse_mx_response
        self.assertIsNone(_parse_mx_response(b"\x00\x01", 0x1234))

    def test_invalid_email_false_without_network(self):
        from jobhunter.mailer import domain_accepts_mail
        self.assertIs(domain_accepts_mail(""), False)
        self.assertIs(domain_accepts_mail("sin-arroba"), False)
        self.assertIs(domain_accepts_mail("x@sindominio"), False)


if __name__ == "__main__":
    unittest.main()
