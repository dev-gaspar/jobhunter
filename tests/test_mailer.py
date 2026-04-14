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


if __name__ == "__main__":
    unittest.main()
