# -*- coding: utf-8 -*-
"""Tests de la fachada de onboarding: key, smtp, cv, linkedin, queries."""
import json
import unittest
from unittest.mock import MagicMock, patch

from jobhunter.service import (
    extract_profile_from_cv,
    has_linkedin_session,
    linkedin_login,
    regenerate_queries,
    validate_gemini_key,
    verify_smtp,
)

CFG = {"gemini_api_key": "k", "gemini_model": "gemini-2.5-flash"}


class TestValidateKey(unittest.TestCase):
    @patch("jobhunter.service.requests.post")
    def test_valid_key(self, m_post):
        m_post.return_value = MagicMock()
        res = validate_gemini_key("AIza test")
        self.assertTrue(res["ok"])
        called_url = m_post.call_args.args[0]
        self.assertIn("AIzatest", called_url)  # espacios removidos

    @patch("jobhunter.service.requests.post", side_effect=RuntimeError("403"))
    def test_invalid_key(self, m_post):
        res = validate_gemini_key("bad")
        self.assertFalse(res["ok"])
        self.assertTrue(res["error"])

    def test_empty_key(self):
        res = validate_gemini_key("")
        self.assertFalse(res["ok"])


class TestVerifySmtp(unittest.TestCase):
    def test_rejects_non_gmail(self):
        res = verify_smtp("yo@hotmail.com", "abcdefghijklmnop")
        self.assertFalse(res["ok"])

    def test_rejects_short_password(self):
        res = verify_smtp("yo@gmail.com", "corta")
        self.assertFalse(res["ok"])

    @patch("jobhunter.service.smtplib.SMTP")
    def test_valid_login(self, m_smtp):
        server = MagicMock()
        m_smtp.return_value.__enter__ = MagicMock(return_value=server)
        m_smtp.return_value.__exit__ = MagicMock(return_value=False)
        res = verify_smtp("yo@gmail.com", "abcd efgh ijkl mnop")
        self.assertTrue(res["ok"])
        server.login.assert_called_once_with("yo@gmail.com", "abcdefghijklmnop")

    @patch("jobhunter.service.smtplib.SMTP", side_effect=RuntimeError("auth fail"))
    def test_login_failure(self, m_smtp):
        res = verify_smtp("yo@gmail.com", "abcdefghijklmnop")
        self.assertFalse(res["ok"])
        self.assertIn("auth fail", res["error"])


class TestExtractCv(unittest.TestCase):
    @patch("jobhunter.service.call_gemini_vision")
    def test_happy(self, m_vision):
        m_vision.return_value = json.dumps({"name": "Jose", "title": "Dev"})
        res = extract_profile_from_cv(CFG, "cGRm")
        self.assertTrue(res["ok"])
        self.assertEqual(res["profile"]["name"], "Jose")

    @patch("jobhunter.service.call_gemini_vision")
    def test_no_name_is_invalid(self, m_vision):
        m_vision.return_value = json.dumps({"name": ""})
        res = extract_profile_from_cv(CFG, "cGRm")
        self.assertFalse(res["ok"])

    @patch("jobhunter.service.call_gemini_vision", side_effect=RuntimeError("api"))
    def test_api_error(self, m_vision):
        res = extract_profile_from_cv(CFG, "cGRm")
        self.assertFalse(res["ok"])
        self.assertIn("api", res["error"])


class TestLinkedin(unittest.TestCase):
    @patch("jobhunter.service.do_linkedin_login", return_value=True)
    def test_login_non_interactive(self, m_login):
        self.assertTrue(linkedin_login())
        m_login.assert_called_once_with(interactive=False)

    @patch("jobhunter.service.os.path.exists", return_value=True)
    def test_has_session(self, m_exists):
        self.assertTrue(has_linkedin_session())


class TestQueries(unittest.TestCase):
    @patch("jobhunter.service.save_config")
    @patch("jobhunter.service.generate_queries", return_value=(["q1", "q2"], True))
    def test_regenerate_saves(self, m_gen, m_save):
        cfg = {"profile": {"name": "J"}}
        res = regenerate_queries(cfg)
        self.assertEqual(res["queries"], ["q1", "q2"])
        self.assertTrue(res["from_ai"])
        self.assertEqual(cfg["search_queries"], ["q1", "q2"])
        m_save.assert_called_once_with(cfg)


if __name__ == "__main__":
    unittest.main()
