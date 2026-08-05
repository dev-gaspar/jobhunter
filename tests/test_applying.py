# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch

from jobhunter.applying import apply_to_offer


def _cfg():
    return {"profile": {"name": "Jose Test"}, "cv_template": "modern"}


def _job():
    return {
        "job_title": "AI Engineer",
        "company": "Acme",
        "contact_email": "hr@acme.com",
        "language": "es",
        "post_url": "https://x.com/p/1",
    }


class ApplyToOfferTests(unittest.TestCase):
    @patch("jobhunter.applying.console")
    @patch("jobhunter.applying.send_email")
    @patch("jobhunter.applying.agent_email", return_value={"subject": "Asunto X", "body": "Cuerpo"})
    @patch("jobhunter.applying.generate_cv_pdf")
    @patch("jobhunter.applying.get_cv_filename", return_value="cv.pdf")
    @patch("jobhunter.applying.agent_cv", return_value={"title": "cv"})
    def test_sent_appends_to_kb_with_subject_and_mode(self, _cv, _fn, _pdf, _em, mock_send, _c):
        kb = {"applications": []}
        res = apply_to_offer(_cfg(), kb, _job(), interactive=False, mode="manual")
        self.assertEqual(res["status"], "sent")
        mock_send.assert_called_once()
        self.assertEqual(len(kb["applications"]), 1)
        app = kb["applications"][0]
        self.assertEqual(app["mode"], "manual")
        self.assertEqual(app["subject"], "Asunto X")
        self.assertEqual(app["recruiter_email"], "hr@acme.com")
        self.assertEqual(app["sent_to"], "hr@acme.com")

    @patch("jobhunter.applying.console")
    @patch("jobhunter.applying.send_email")
    @patch("jobhunter.applying.agent_email", return_value={"subject": "S", "body": "B"})
    @patch("jobhunter.applying.generate_cv_pdf")
    @patch("jobhunter.applying.get_cv_filename", return_value="cv.pdf")
    @patch("jobhunter.applying.agent_cv", return_value={})
    def test_dry_run_does_not_send_nor_persist(self, _cv, _fn, _pdf, _em, mock_send, _c):
        kb = {"applications": []}
        res = apply_to_offer(_cfg(), kb, _job(), dry_run=True, interactive=False)
        self.assertEqual(res["status"], "dry")
        mock_send.assert_not_called()
        self.assertEqual(kb["applications"], [])
        self.assertTrue(res["record"].get("dry_run"))

    @patch("jobhunter.applying.console")
    @patch("jobhunter.applying.time.sleep")
    @patch("jobhunter.applying.agent_cv", side_effect=RuntimeError("boom"))
    def test_generation_error_returns_error(self, _cv, _sleep, _c):
        kb = {"applications": []}
        res = apply_to_offer(_cfg(), kb, _job(), interactive=False)
        self.assertEqual(res["status"], "error")
        self.assertEqual(kb["applications"], [])

    @patch("jobhunter.applying.console")
    @patch("jobhunter.applying.send_email")
    @patch("jobhunter.applying.agent_email", return_value={"subject": "S", "body": "B"})
    @patch("jobhunter.applying.generate_cv_pdf")
    @patch("jobhunter.applying.get_cv_filename", return_value="cv.pdf")
    @patch("jobhunter.applying.agent_cv", return_value={})
    def test_test_email_overrides_recipient(self, _cv, _fn, _pdf, _em, mock_send, _c):
        kb = {"applications": []}
        res = apply_to_offer(_cfg(), kb, _job(), test_email="yo@test.com", interactive=False, mode="test")
        self.assertEqual(res["status"], "sent")
        args = mock_send.call_args.args
        self.assertEqual(args[1], "yo@test.com")
        self.assertEqual(kb["applications"][0]["sent_to"], "yo@test.com")


if __name__ == "__main__":
    unittest.main()
