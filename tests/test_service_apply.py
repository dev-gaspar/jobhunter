# -*- coding: utf-8 -*-
"""Tests de service.prepare_application / send_application / check_recipient."""
import unittest
from unittest.mock import MagicMock, patch

from jobhunter.service import check_recipient, prepare_application, send_application

CFG = {
    "gemini_api_key": "k",
    "smtp_email": "yo@gmail.com",
    "smtp_password": "app",
    "profile": {"name": "Jose"},
    "cv_template": "modern",
}

JOB = {
    "job_title": "Backend Dev",
    "company": "TechCo",
    "contact_email": "hr@techco.com",
    "contact_name": "Ana",
    "language": "es",
    "post_url": "https://lnkd.in/x",
    "query": "backend",
    "author_url": None,
    "author_name": None,
}


class TestPrepare(unittest.TestCase):
    @patch("jobhunter.service.generate_cv_pdf")
    @patch("jobhunter.service.get_cv_filename", return_value="cv.pdf")
    @patch("jobhunter.service.agent_email", return_value={"subject": "Asunto", "body": "Cuerpo"})
    @patch("jobhunter.service.agent_cv", return_value={"title": "cv"})
    def test_happy_path(self, m_cv, m_email, m_fn, m_pdf):
        events = []
        res = prepare_application(CFG, JOB, on_event=lambda n, p: events.append((n, p)), pace=False)
        self.assertTrue(res["ok"])
        self.assertEqual(res["subject"], "Asunto")
        self.assertEqual(res["body"], "Cuerpo")
        self.assertIn("cv.pdf", res["cv_path"])
        stages = [p["stage"] for n, p in events if n == "apply_progress"]
        self.assertEqual(stages, ["cv", "email"])

    @patch("jobhunter.service.generate_cv_pdf")
    @patch("jobhunter.service.get_cv_filename", return_value="cv.pdf")
    @patch("jobhunter.service.agent_email", return_value={"subject": "S", "body": "B"})
    @patch("jobhunter.service.agent_cv", return_value={})
    def test_test_email_adds_banner(self, m_cv, m_email, m_fn, m_pdf):
        res = prepare_application(CFG, JOB, test_email="yo@test.com", pace=False)
        self.assertTrue(res["body"].startswith("--- RECLUTADOR: Ana | EMAIL: hr@techco.com | TechCo ---"))
        self.assertIn("B", res["body"])

    @patch("jobhunter.service.agent_cv", side_effect=RuntimeError("boom"))
    def test_cv_failure_exhausts_retries(self, m_cv):
        res = prepare_application(CFG, JOB, pace=False)
        self.assertFalse(res["ok"])
        self.assertIn("boom", res["error"])
        self.assertEqual(m_cv.call_count, 3)

    @patch("jobhunter.service.generate_cv_pdf")
    @patch("jobhunter.service.get_cv_filename", return_value="cv.pdf")
    @patch("jobhunter.service.agent_email", side_effect=RuntimeError("mail-fail"))
    @patch("jobhunter.service.agent_cv", return_value={})
    def test_email_failure_after_cv_ok(self, m_cv, m_email, m_fn, m_pdf):
        res = prepare_application(CFG, JOB, pace=False)
        self.assertFalse(res["ok"])
        self.assertIn("mail-fail", res["error"])
        self.assertIsNotNone(res["cv_path"])
        self.assertEqual(m_email.call_count, 3)


class TestSend(unittest.TestCase):
    def _prepared(self):
        return {"ok": True, "cv_data": {}, "cv_path": "/tmp/cv.pdf",
                "subject": "Asunto", "body": "Cuerpo", "error": None}

    @patch("jobhunter.service.send_email")
    def test_sent_appends_history(self, m_send):
        kb = {"runs": [], "applications": [], "rejected_companies": []}
        res = send_application(CFG, kb, JOB, self._prepared(), to="hr@techco.com", mode="run")
        self.assertEqual(res["status"], "sent")
        self.assertEqual(len(kb["applications"]), 1)
        entry = kb["applications"][0]
        self.assertEqual(entry["company"], "TechCo")
        self.assertEqual(entry["subject"], "Asunto")
        self.assertEqual(entry["mode"], "run")
        self.assertEqual(entry["sent_to"], "hr@techco.com")
        self.assertEqual(entry["recruiter_email"], "hr@techco.com")
        m_send.assert_called_once_with(CFG, "hr@techco.com", "Asunto", "Cuerpo", "/tmp/cv.pdf")

    @patch("jobhunter.service.send_email")
    def test_alt_recruiter_email_recorded(self, m_send):
        kb = {"runs": [], "applications": [], "rejected_companies": []}
        res = send_application(CFG, kb, JOB, self._prepared(), to="alt@x.com",
                               mode="run", recruiter_email="alt@x.com")
        self.assertEqual(kb["applications"][0]["recruiter_email"], "alt@x.com")

    @patch("jobhunter.service.send_email", side_effect=RuntimeError("smtp down"))
    def test_error_keeps_history_clean(self, m_send):
        kb = {"runs": [], "applications": [], "rejected_companies": []}
        res = send_application(CFG, kb, JOB, self._prepared(), to="hr@techco.com")
        self.assertEqual(res["status"], "error")
        self.assertIn("smtp down", res["error"])
        self.assertEqual(kb["applications"], [])


class TestCheckRecipient(unittest.TestCase):
    @patch("jobhunter.service.domain_accepts_mail", return_value=None)
    def test_passthrough(self, m_mx):
        self.assertIsNone(check_recipient("a@b.com"))
        m_mx.assert_called_once_with("a@b.com")


if __name__ == "__main__":
    unittest.main()
