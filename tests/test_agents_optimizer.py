# -*- coding: utf-8 -*-
import json
import unittest
from unittest.mock import patch

from jobhunter.agents.optimizer import optimize_queries


CFG = {
    "profile": {"name": "Jose", "title": "Backend Dev", "skills": {"backend": ["Python"]}},
    "job_types_raw": "backend developer",
    "search_languages": "3",
    "work_mode_label": "Remoto",
    "search_queries": ["hiring backend", "enviar CV dev"],
    "gemini_api_key": "K",
    "gemini_model": "gemini-2.5-flash",
}

KB = {
    "runs": [{"posts": 100, "offers": 10, "sent": 3}],
    "applications": [{"job_title": "Backend Dev"}],
}


class OptimizerTests(unittest.TestCase):
    @patch("jobhunter.agents.optimizer.call_gemini")
    def test_returns_analysis_and_queries(self, mock_call):
        mock_call.return_value = json.dumps({
            "analysis": "necesitas mas variedad",
            "queries": ["q1", "q2", "q3"],
            "changes_summary": "mejoras varias",
        })
        result = optimize_queries(CFG, KB)
        self.assertEqual(result["queries"], ["q1", "q2", "q3"])
        self.assertIn("necesitas", result["analysis"])

    @patch("jobhunter.agents.optimizer.call_gemini")
    def test_user_prompt_in_prompt(self, mock_call):
        mock_call.return_value = json.dumps({"analysis": "", "queries": [], "changes_summary": ""})
        optimize_queries(CFG, KB, user_prompt="quiero mas ofertas senior")
        prompt = mock_call.call_args.args[1]
        self.assertIn("quiero mas ofertas senior", prompt)

    @patch("jobhunter.agents.optimizer.call_gemini")
    def test_run_stats_included_when_runs_exist(self, mock_call):
        mock_call.return_value = json.dumps({"queries": []})
        optimize_queries(CFG, KB)
        prompt = mock_call.call_args.args[1]
        self.assertIn("HISTORIAL", prompt)
        self.assertIn("100", prompt)  # total posts

    @patch("jobhunter.agents.optimizer.call_gemini")
    def test_invalid_json_returns_empty(self, mock_call):
        mock_call.return_value = "not json"
        result = optimize_queries(CFG, KB)
        self.assertEqual(result["queries"], [])
        self.assertEqual(result["analysis"], "")

    @patch("jobhunter.agents.optimizer.call_gemini")
    def test_lang_rule_spanish_only(self, mock_call):
        mock_call.return_value = json.dumps({"queries": []})
        cfg = dict(CFG, search_languages="1")
        optimize_queries(cfg, KB)
        prompt = mock_call.call_args.args[1]
        self.assertIn("SOLO en espanol", prompt)

    @patch("jobhunter.agents.optimizer.call_gemini")
    def test_no_division_by_zero_when_empty_runs(self, mock_call):
        mock_call.return_value = json.dumps({"queries": []})
        optimize_queries(CFG, {"runs": [], "applications": []})
        prompt = mock_call.call_args.args[1]
        self.assertNotIn("HISTORIAL", prompt)


if __name__ == "__main__":
    unittest.main()
