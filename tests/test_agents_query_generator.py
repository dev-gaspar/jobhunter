# -*- coding: utf-8 -*-
import json
import unittest
from unittest.mock import patch

from jobhunter.agents.query_generator import (
    _english_is_limited,
    _english_level,
    _estimate_seniority,
    _fallback,
    _sanitize,
    _top_stack,
    generate_queries,
)


CFG_BASE = {
    "profile": {
        "title": "Backend Developer",
        "skills": {"backend": ["Java", "Spring"], "other": ["Docker"]},
        "experience": [{"role": "Dev"}, {"role": "Intern"}],
    },
    "job_types_raw": "Backend Developer, Full Stack Developer",
    "search_languages": "3",
    "work_mode_label": "Remoto",
    "user_languages": [
        {"language": "Espanol", "level": "Nativo"},
        {"language": "Ingles", "level": "B1"},
    ],
    "gemini_api_key": "K",
    "gemini_model": "gemini-2.5-flash",
}


class HelperTests(unittest.TestCase):
    def test_seniority_junior_no_experience(self):
        self.assertEqual(_estimate_seniority({"experience": []}), "junior")

    def test_seniority_semi_senior_two_to_three(self):
        self.assertEqual(_estimate_seniority({"experience": [1, 2]}), "semi senior")
        self.assertEqual(_estimate_seniority({"experience": [1, 2, 3]}), "semi senior")

    def test_seniority_senior_four_plus(self):
        self.assertEqual(_estimate_seniority({"experience": [1, 2, 3, 4]}), "senior")

    def test_english_level_extracted(self):
        self.assertEqual(_english_level(CFG_BASE), "B1")

    def test_english_level_none_when_missing(self):
        self.assertIsNone(_english_level({"user_languages": [{"language": "Espanol", "level": "Nativo"}]}))

    def test_english_is_limited_b1_and_below(self):
        self.assertTrue(_english_is_limited("B1"))
        self.assertTrue(_english_is_limited("A2"))
        self.assertTrue(_english_is_limited("Basico"))
        self.assertTrue(_english_is_limited(None))

    def test_english_is_not_limited_b2_and_above(self):
        self.assertFalse(_english_is_limited("B2"))
        self.assertFalse(_english_is_limited("C1"))
        self.assertFalse(_english_is_limited("Fluent"))

    def test_top_stack_flattens_dict(self):
        stack = _top_stack(CFG_BASE["profile"])
        self.assertIn("Java", stack)
        self.assertIn("Spring", stack)
        self.assertIn("Docker", stack)

    def test_top_stack_list_form(self):
        stack = _top_stack({"skills": ["Python", "Django"]})
        self.assertEqual(stack, ["Python", "Django"])

    def test_sanitize_dedupe_case_insensitive(self):
        clean = _sanitize(["Hola", "hola", "HOLA", "mundo", ""])
        self.assertEqual(clean, ["Hola", "mundo"])

    def test_sanitize_drops_non_strings(self):
        clean = _sanitize(["ok", None, 42, "otra"])
        self.assertEqual(clean, ["ok", "otra"])


class GenerateQueriesAITests(unittest.TestCase):
    @patch("jobhunter.agents.query_generator.call_gemini")
    def test_ai_success_returns_from_ai_true(self, mock_call):
        mock_call.return_value = json.dumps([
            "buscamos backend java spring", "vacante backend semi senior",
            "aplica backend developer remoto", "contratando developer NestJS",
            "postulate Full Stack remoto", "se busca backend java",
        ])
        queries, from_ai = generate_queries(CFG_BASE)
        self.assertTrue(from_ai)
        self.assertGreaterEqual(len(queries), 5)

    @patch("jobhunter.agents.query_generator.call_gemini")
    def test_ai_fallback_on_exception(self, mock_call):
        mock_call.side_effect = Exception("quota exceeded")
        queries, from_ai = generate_queries(CFG_BASE)
        self.assertFalse(from_ai)
        self.assertGreater(len(queries), 0)

    @patch("jobhunter.agents.query_generator.call_gemini")
    def test_ai_fallback_when_not_a_list(self, mock_call):
        mock_call.return_value = json.dumps({"queries": ["x"]})
        queries, from_ai = generate_queries(CFG_BASE)
        self.assertFalse(from_ai)

    @patch("jobhunter.agents.query_generator.call_gemini")
    def test_ai_fallback_when_too_few(self, mock_call):
        mock_call.return_value = json.dumps(["one", "two"])
        queries, from_ai = generate_queries(CFG_BASE)
        self.assertFalse(from_ai)

    @patch("jobhunter.agents.query_generator.call_gemini")
    def test_prompt_includes_stack(self, mock_call):
        mock_call.return_value = json.dumps(["a", "b", "c", "d", "e", "f"])
        generate_queries(CFG_BASE)
        prompt = mock_call.call_args.args[1]
        self.assertIn("Java", prompt)
        self.assertIn("Spring", prompt)

    @patch("jobhunter.agents.query_generator.call_gemini")
    def test_prompt_includes_seniority(self, mock_call):
        mock_call.return_value = json.dumps(["a", "b", "c", "d", "e", "f"])
        generate_queries(CFG_BASE)
        prompt = mock_call.call_args.args[1]
        self.assertIn("semi senior", prompt)

    @patch("jobhunter.agents.query_generator.call_gemini")
    def test_prompt_warns_limited_english(self, mock_call):
        mock_call.return_value = json.dumps(["a", "b", "c", "d", "e", "f"])
        generate_queries(CFG_BASE)
        prompt = mock_call.call_args.args[1]
        self.assertIn("NO generes queries 100% en ingles", prompt)

    @patch("jobhunter.agents.query_generator.call_gemini")
    def test_prompt_allows_english_when_not_limited(self, mock_call):
        mock_call.return_value = json.dumps(["a", "b", "c", "d", "e", "f"])
        cfg = dict(CFG_BASE, user_languages=[
            {"language": "Espanol", "level": "Nativo"},
            {"language": "Ingles", "level": "C1"},
        ])
        generate_queries(cfg)
        prompt = mock_call.call_args.args[1]
        self.assertNotIn("NO generes queries 100% en ingles", prompt)


class FallbackTests(unittest.TestCase):
    def test_fallback_includes_stack_combos(self):
        stack = ["Java", "Spring"]
        queries = _fallback(CFG_BASE, stack, "semi senior", en_limited=True)
        joined = " ".join(queries).lower()
        self.assertIn("java", joined)

    def test_fallback_respects_limited_english(self):
        stack = ["Java"]
        queries = _fallback(CFG_BASE, stack, "junior", en_limited=True)
        # Con ingles limitado y search_languages=3, NO debe haber queries puras en ingles
        for q in queries:
            # Una query pura en ingles tipicamente empieza con hiring/we are/looking
            lower = q.lower()
            self.assertFalse(
                lower.startswith("hiring ") or lower.startswith("we are hiring") or lower.startswith("looking for"),
                f"Query en ingles no deberia aparecer con ingles limitado: {q}",
            )

    def test_fallback_includes_english_when_not_limited(self):
        queries = _fallback(CFG_BASE, ["Java"], "senior", en_limited=False)
        lower = " ".join(queries).lower()
        self.assertIn("hiring", lower)


if __name__ == "__main__":
    unittest.main()
