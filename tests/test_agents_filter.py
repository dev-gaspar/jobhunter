# -*- coding: utf-8 -*-
import json
import unittest
from unittest.mock import patch

from jobhunter.agents.filter import agent_filter


CFG = {
    "profile": {"summary": "desarrollador", "skills": {"backend": ["Python"]}},
    "job_types_raw": "backend developer",
    "work_mode_label": "Remoto",
    "user_location": "Bogota",
    "user_languages": [{"language": "Espanol", "level": "Nativo"}],
    "gemini_api_key": "K",
    "gemini_model": "gemini-2.5-flash",
}


class AgentFilterTests(unittest.TestCase):
    @patch("jobhunter.agents.filter.call_gemini")
    def test_parses_job_response(self, mock_call):
        mock_call.return_value = json.dumps({
            "is_job": True,
            "job_title": "Backend Dev",
            "company": "Acme",
            "contact_email": "hr@acme.com",
            "is_relevant": True,
            "language": "es",
        })
        result = agent_filter(CFG, "Buscamos backend dev en Acme hr@acme.com")
        self.assertTrue(result["is_job"])
        self.assertEqual(result["company"], "Acme")
        self.assertEqual(result["contact_email"], "hr@acme.com")

    @patch("jobhunter.agents.filter.call_gemini")
    def test_fills_email_from_text_when_missing(self, mock_call):
        mock_call.return_value = json.dumps({
            "is_job": True,
            "job_title": "Dev",
            "company": "X",
            "contact_email": None,
            "is_relevant": True,
        })
        result = agent_filter(CFG, "Buscamos dev cv@empresa.com")
        self.assertEqual(result["contact_email"], "cv@empresa.com")

    @patch("jobhunter.agents.filter.call_gemini")
    def test_null_email_is_normalized(self, mock_call):
        mock_call.return_value = json.dumps({
            "is_job": True,
            "contact_email": "null",
            "is_relevant": True,
        })
        result = agent_filter(CFG, "Texto sin emails")
        self.assertIsNone(result["contact_email"])

    @patch("jobhunter.agents.filter.call_gemini")
    def test_returns_not_job_on_invalid_json(self, mock_call):
        mock_call.return_value = "no-es-json"
        result = agent_filter(CFG, "texto")
        self.assertFalse(result["is_job"])
        self.assertIn("relevance_reason", result)

    @patch("jobhunter.agents.filter.call_gemini")
    def test_prompt_contains_profile_and_job_types(self, mock_call):
        mock_call.return_value = json.dumps({"is_job": False})
        agent_filter(CFG, "post")
        prompt = mock_call.call_args.args[1]
        self.assertIn("backend developer", prompt)
        self.assertIn("Remoto", prompt)
        self.assertIn("Espanol", prompt)


class LanguageGateTests(unittest.TestCase):
    def _offer(self, lang):
        return json.dumps({
            "is_job": True, "job_title": "Dev", "company": "X",
            "contact_email": "hr@x.com", "is_relevant": True, "language": lang,
        })

    @patch("jobhunter.agents.filter.call_gemini")
    def test_pt_offer_rejected_with_spanish_only_config(self, mock_call):
        mock_call.return_value = self._offer("pt")
        cfg = dict(CFG, search_languages="1")
        result = agent_filter(cfg, "Vaga para desenvolvedor backend hr@x.com")
        self.assertFalse(result["is_relevant"])
        self.assertIn("idioma", result["relevance_reason"].lower())

    @patch("jobhunter.agents.filter.call_gemini")
    def test_es_offer_passes_with_spanish_only_config(self, mock_call):
        mock_call.return_value = self._offer("es")
        cfg = dict(CFG, search_languages="1")
        result = agent_filter(cfg, "Buscamos backend dev hr@x.com")
        self.assertTrue(result["is_relevant"])

    @patch("jobhunter.agents.filter.call_gemini")
    def test_en_offer_rejected_when_spanish_only(self, mock_call):
        mock_call.return_value = self._offer("en")
        cfg = dict(CFG, search_languages="1")
        result = agent_filter(cfg, "We are hiring backend dev hr@x.com")
        self.assertFalse(result["is_relevant"])

    @patch("jobhunter.agents.filter.call_gemini")
    def test_en_offer_passes_when_bilingual(self, mock_call):
        mock_call.return_value = self._offer("en")
        cfg = dict(CFG, search_languages="3")
        result = agent_filter(cfg, "We are hiring backend dev hr@x.com")
        self.assertTrue(result["is_relevant"])

    @patch("jobhunter.agents.filter.call_gemini")
    def test_missing_language_not_blocked(self, mock_call):
        mock_call.return_value = json.dumps({
            "is_job": True, "job_title": "Dev", "company": "X",
            "contact_email": "hr@x.com", "is_relevant": True,
        })
        cfg = dict(CFG, search_languages="1")
        result = agent_filter(cfg, "Buscamos dev hr@x.com")
        self.assertTrue(result["is_relevant"])

    @patch("jobhunter.agents.filter.call_gemini")
    def test_regional_variant_normalized(self, mock_call):
        mock_call.return_value = self._offer("pt-BR")
        cfg = dict(CFG, search_languages="3")
        result = agent_filter(cfg, "Vaga backend hr@x.com")
        self.assertFalse(result["is_relevant"])

    @patch("jobhunter.agents.filter.call_gemini")
    def test_prompt_mentions_allowed_languages(self, mock_call):
        mock_call.return_value = json.dumps({"is_job": False})
        cfg = dict(CFG, search_languages="1")
        agent_filter(cfg, "post")
        prompt = mock_call.call_args.args[1]
        self.assertIn("espanol (es)", prompt.lower())


if __name__ == "__main__":
    unittest.main()
