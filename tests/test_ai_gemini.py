import json
import unittest
from unittest.mock import MagicMock, patch

from jobhunter.ai.gemini import GeminiProvider, call_gemini, call_gemini_vision


def _mock_response(status_code=200, text="respuesta ok"):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": text}]}}]
    }
    r.raise_for_status = MagicMock()
    return r


class GeminiProviderTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"gemini_api_key": "FAKEKEY", "gemini_model": "gemini-2.5-flash"}

    def test_url_contains_model_and_key(self):
        url = GeminiProvider(self.cfg)._url()
        self.assertIn("gemini-2.5-flash", url)
        self.assertIn("FAKEKEY", url)

    @patch("jobhunter.ai.gemini.requests.post")
    def test_generate_returns_text(self, mock_post):
        mock_post.return_value = _mock_response(text="hola")
        result = GeminiProvider(self.cfg).generate("prompt test")
        self.assertEqual(result, "hola")

    @patch("jobhunter.ai.gemini.requests.post")
    def test_generate_strips_markdown_fences(self, mock_post):
        mock_post.return_value = _mock_response(text='```json\n{"a":1}\n```')
        result = GeminiProvider(self.cfg).generate("prompt test")
        self.assertIn('"a":1', result)
        self.assertNotIn("```", result)

    @patch("jobhunter.ai.gemini.time.sleep")
    @patch("jobhunter.ai.gemini.requests.post")
    def test_retry_on_429(self, mock_post, mock_sleep):
        mock_post.side_effect = [_mock_response(429), _mock_response(429), _mock_response(text="ok")]
        result = GeminiProvider(self.cfg).generate("prompt")
        self.assertEqual(result, "ok")
        self.assertEqual(mock_post.call_count, 3)

    @patch("jobhunter.ai.gemini.time.sleep")
    @patch("jobhunter.ai.gemini.requests.post")
    def test_retry_on_5xx(self, mock_post, mock_sleep):
        mock_post.side_effect = [_mock_response(503), _mock_response(text="ok")]
        result = GeminiProvider(self.cfg).generate("prompt")
        self.assertEqual(result, "ok")

    @patch("jobhunter.ai.gemini.time.sleep")
    @patch("jobhunter.ai.gemini.requests.post")
    def test_max_retries_exceeded_raises(self, mock_post, mock_sleep):
        mock_post.return_value = _mock_response(429)
        with self.assertRaises(Exception):
            GeminiProvider(self.cfg).generate("prompt")

    @patch("jobhunter.ai.gemini.requests.post")
    def test_generate_vision_includes_inline_data(self, mock_post):
        mock_post.return_value = _mock_response(text="extracted")
        GeminiProvider(self.cfg).generate_vision("lee", "BASE64DATA", "application/pdf")
        payload = mock_post.call_args.kwargs["json"]
        parts = payload["contents"][0]["parts"]
        self.assertEqual(parts[0]["text"], "lee")
        self.assertEqual(parts[1]["inline_data"]["mime_type"], "application/pdf")
        self.assertEqual(parts[1]["inline_data"]["data"], "BASE64DATA")


class LegacyWrappersTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"gemini_api_key": "FAKEKEY", "gemini_model": "gemini-2.5-flash"}

    @patch("jobhunter.ai.gemini.requests.post")
    def test_call_gemini_wrapper(self, mock_post):
        mock_post.return_value = _mock_response(text="wrapper")
        self.assertEqual(call_gemini(self.cfg, "p"), "wrapper")

    @patch("jobhunter.ai.gemini.requests.post")
    def test_call_gemini_vision_wrapper(self, mock_post):
        mock_post.return_value = _mock_response(text="vwrapper")
        self.assertEqual(call_gemini_vision(self.cfg, "p", "B64"), "vwrapper")


if __name__ == "__main__":
    unittest.main()
