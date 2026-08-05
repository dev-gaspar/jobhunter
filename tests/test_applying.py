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
    @patch("jobhunter.applying.domain_accepts_mail", return_value=True)
    @patch("jobhunter.applying.console")
    @patch("jobhunter.applying.send_email")
    @patch("jobhunter.applying.agent_email", return_value={"subject": "Asunto X", "body": "Cuerpo"})
    @patch("jobhunter.applying.generate_cv_pdf")
    @patch("jobhunter.applying.get_cv_filename", return_value="cv.pdf")
    @patch("jobhunter.applying.agent_cv", return_value={"title": "cv"})
    def test_sent_appends_to_kb_with_subject_and_mode(self, _cv, _fn, _pdf, _em, mock_send, _c, _mx):
        kb = {"applications": []}
        job = dict(_job(), query="Vacante AI remoto", author_url="https://linkedin.com/in/rec", author_name="Reclutadora X")
        res = apply_to_offer(_cfg(), kb, job, interactive=False, mode="manual")
        self.assertEqual(res["status"], "sent")
        mock_send.assert_called_once()
        self.assertEqual(len(kb["applications"]), 1)
        app = kb["applications"][0]
        self.assertEqual(app["mode"], "manual")
        self.assertEqual(app["subject"], "Asunto X")
        self.assertEqual(app["recruiter_email"], "hr@acme.com")
        self.assertEqual(app["sent_to"], "hr@acme.com")
        self.assertEqual(app["query"], "Vacante AI remoto")
        self.assertEqual(app["author_url"], "https://linkedin.com/in/rec")
        self.assertEqual(app["author_name"], "Reclutadora X")

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


class MxGateTests(unittest.TestCase):
    def _patches(self):
        return [
            patch("jobhunter.applying.console"),
            patch("jobhunter.applying.send_email"),
            patch("jobhunter.applying.agent_email", return_value={"subject": "S", "body": "B"}),
            patch("jobhunter.applying.generate_cv_pdf"),
            patch("jobhunter.applying.get_cv_filename", return_value="cv.pdf"),
            patch("jobhunter.applying.agent_cv", return_value={}),
        ]

    def _run(self, mx_value, prompt_answer=None, interactive=False):
        kb = {"applications": []}
        ps = self._patches()
        mocks = [p.start() for p in ps]
        try:
            with patch("jobhunter.applying.domain_accepts_mail", return_value=mx_value):
                if interactive:
                    with patch("jobhunter.applying.Prompt") as mock_prompt:
                        mock_prompt.ask.return_value = prompt_answer if prompt_answer is not None else "s"
                        res = apply_to_offer(_cfg(), kb, _job(), interactive=True)
                else:
                    res = apply_to_offer(_cfg(), kb, _job(), interactive=False)
        finally:
            for p in ps:
                p.stop()
        return res, kb, mocks[1]

    def test_mx_false_non_interactive_skips(self):
        res, kb, mock_send = self._run(False)
        self.assertEqual(res["status"], "skipped")
        mock_send.assert_not_called()
        self.assertEqual(kb["applications"], [])

    def test_mx_none_does_not_block(self):
        res, kb, mock_send = self._run(None)
        self.assertEqual(res["status"], "sent")
        mock_send.assert_called_once()

    def test_mx_false_interactive_alternate_email(self):
        kb = {"applications": []}
        ps = self._patches()
        mocks = [p.start() for p in ps]
        try:
            with patch("jobhunter.applying.domain_accepts_mail", return_value=False):
                with patch("jobhunter.applying.Prompt") as mock_prompt:
                    mock_prompt.ask.side_effect = ["s", "hr@acme-corp.com"]
                    res = apply_to_offer(_cfg(), kb, _job(), interactive=True)
        finally:
            for p in ps:
                p.stop()
        self.assertEqual(res["status"], "sent")
        self.assertEqual(mocks[1].call_args.args[1], "hr@acme-corp.com")
        self.assertEqual(kb["applications"][0]["sent_to"], "hr@acme-corp.com")
        self.assertEqual(kb["applications"][0]["recruiter_email"], "hr@acme-corp.com")

    def test_mx_false_interactive_empty_alt_skips(self):
        kb = {"applications": []}
        ps = self._patches()
        mocks = [p.start() for p in ps]
        try:
            with patch("jobhunter.applying.domain_accepts_mail", return_value=False):
                with patch("jobhunter.applying.Prompt") as mock_prompt:
                    mock_prompt.ask.side_effect = ["s", ""]
                    res = apply_to_offer(_cfg(), kb, _job(), interactive=True)
        finally:
            for p in ps:
                p.stop()
        self.assertEqual(res["status"], "skipped")
        mocks[1].assert_not_called()

    def test_mx_not_checked_in_test_mode(self):
        kb = {"applications": []}
        ps = self._patches()
        [p.start() for p in ps]
        try:
            with patch("jobhunter.applying.domain_accepts_mail") as mock_mx:
                res = apply_to_offer(_cfg(), kb, _job(), test_email="yo@test.com", interactive=False, mode="test")
        finally:
            for p in ps:
                p.stop()
        self.assertEqual(res["status"], "sent")
        mock_mx.assert_not_called()


if __name__ == "__main__":
    unittest.main()
