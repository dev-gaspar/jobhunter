# -*- coding: utf-8 -*-
import json
import unittest
from unittest.mock import patch

from jobhunter.agents.cv import agent_cv


CFG = {
    "profile": {
        "name": "Jose",
        "title": "Backend Dev",
        "skills": {"backend": ["Python", "FastAPI"]},
        "experience": [{"company": "Acme", "role": "Dev", "period": "2022-2024"}],
    },
    "user_languages": [{"language": "Espanol", "level": "Nativo"}],
    "gemini_api_key": "K",
    "gemini_model": "gemini-2.5-flash",
}


class AgentCvTests(unittest.TestCase):
    @patch("jobhunter.agents.cv.call_gemini")
    def test_returns_parsed_cv(self, mock_call):
        mock_call.return_value = json.dumps({
            "summary": "x", "title": "Backend Dev",
            "skills_highlighted": ["Python"],
            "experience": [],
            "projects": [],
            "education": [],
            "languages": [],
        })
        result = agent_cv(CFG, {"job_title": "Backend", "language": "es"})
        self.assertEqual(result["title"], "Backend Dev")
        self.assertEqual(result["skills_highlighted"], ["Python"])

    @patch("jobhunter.agents.cv.call_gemini")
    def test_prompt_includes_language_directive(self, mock_call):
        mock_call.return_value = json.dumps({"summary": "", "title": "", "skills_highlighted": [], "experience": [], "projects": [], "education": [], "languages": []})
        agent_cv(CFG, {"job_title": "Dev", "language": "en"})
        prompt = mock_call.call_args.args[1]
        self.assertIn("INGLES", prompt)

    @patch("jobhunter.agents.cv.call_gemini")
    def test_prompt_declares_anti_invention_rule(self, mock_call):
        mock_call.return_value = json.dumps({"summary": "", "title": "", "skills_highlighted": [], "experience": [], "projects": [], "education": [], "languages": []})
        agent_cv(CFG, {"job_title": "Dev", "language": "es"})
        prompt = mock_call.call_args.args[1]
        self.assertIn("PROHIBIDO INVENTAR", prompt)

    @patch("jobhunter.agents.cv.call_gemini")
    def test_prompt_includes_user_languages(self, mock_call):
        mock_call.return_value = json.dumps({"summary": "", "title": "", "skills_highlighted": [], "experience": [], "projects": [], "education": [], "languages": []})
        agent_cv(CFG, {"job_title": "Dev", "language": "es"})
        prompt = mock_call.call_args.args[1]
        self.assertIn("Espanol", prompt)

    @patch("jobhunter.agents.cv.call_gemini")
    def test_defaults_language_to_spanish(self, mock_call):
        mock_call.return_value = json.dumps({"summary": "", "title": "", "skills_highlighted": [], "experience": [], "projects": [], "education": [], "languages": []})
        agent_cv(CFG, {"job_title": "Dev"})  # sin language
        prompt = mock_call.call_args.args[1]
        self.assertIn("ESPA\u00d1OL", prompt)


if __name__ == "__main__":
    unittest.main()
