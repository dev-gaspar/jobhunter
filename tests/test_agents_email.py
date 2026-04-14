# -*- coding: utf-8 -*-
import json
import unittest
from unittest.mock import patch

from jobhunter.agents.email import agent_email


CFG = {
    "profile": {
        "name": "Jose Test",
        "portfolio": "https://jose.dev",
        "linkedin": "https://linkedin.com/in/jose",
    },
    "job_types_raw": "backend developer",
    "gemini_api_key": "K",
    "gemini_model": "gemini-2.5-flash",
}


class AgentEmailTests(unittest.TestCase):
    @patch("jobhunter.agents.email.call_gemini")
    def test_returns_subject_and_body(self, mock_call):
        mock_call.return_value = json.dumps({"subject": "Aplicacion Backend", "body": "Hola..."})
        result = agent_email(CFG, {"job_title": "Backend", "company": "Acme", "language": "es"})
        self.assertEqual(result["subject"], "Aplicacion Backend")
        self.assertIn("Hola", result["body"])

    @patch("jobhunter.agents.email.call_gemini")
    def test_prompt_contains_signature(self, mock_call):
        mock_call.return_value = json.dumps({"subject": "s", "body": "b"})
        agent_email(CFG, {"job_title": "Dev", "company": "X"})
        prompt = mock_call.call_args.args[1]
        self.assertIn("Jose Test", prompt)
        self.assertIn("https://jose.dev", prompt)

    @patch("jobhunter.agents.email.call_gemini")
    def test_cv_data_injected_into_prompt(self, mock_call):
        mock_call.return_value = json.dumps({"subject": "s", "body": "b"})
        cv = {"title": "Senior Backend", "summary": "5 anos", "skills_highlighted": ["Python", "FastAPI"]}
        agent_email(CFG, {"job_title": "Dev"}, cv_data=cv)
        prompt = mock_call.call_args.args[1]
        self.assertIn("Senior Backend", prompt)
        self.assertIn("Python", prompt)

    @patch("jobhunter.agents.email.call_gemini")
    def test_language_rule_applied_to_english(self, mock_call):
        mock_call.return_value = json.dumps({"subject": "s", "body": "b"})
        agent_email(CFG, {"job_title": "Dev", "language": "en"})
        prompt = mock_call.call_args.args[1]
        self.assertIn("ENGLISH", prompt)

    @patch("jobhunter.agents.email.call_gemini")
    def test_no_cv_no_cv_clause(self, mock_call):
        mock_call.return_value = json.dumps({"subject": "s", "body": "b"})
        agent_email(CFG, {"job_title": "Dev"})
        prompt = mock_call.call_args.args[1]
        self.assertNotIn("o en el CV generado", prompt)


if __name__ == "__main__":
    unittest.main()
