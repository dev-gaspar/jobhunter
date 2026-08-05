# -*- coding: utf-8 -*-
import io
import unittest
from unittest.mock import MagicMock, patch

from jobhunter.cli.apply import cmd_apply, is_url, read_pasted_text

POST = "x" * 30 + " Buscamos dev. Enviar CV a maria@simon.com con asunto Vacante. " + "y" * 30


def _cfg():
    return {"profile": {"name": "J"}}


class IsUrlTests(unittest.TestCase):
    def test_detects_links(self):
        self.assertTrue(is_url("https://lnkd.in/p/ddTxabDW"))
        self.assertTrue(is_url("http://linkedin.com/posts/x"))
        self.assertTrue(is_url("  https://x.com  "))

    def test_rejects_text(self):
        self.assertFalse(is_url("Buscamos desarrollador enviar CV"))
        self.assertFalse(is_url(""))
        self.assertFalse(is_url(None))


class ReadPastedTextTests(unittest.TestCase):
    @patch("jobhunter.cli.apply.console")
    @patch("jobhunter.cli.apply.sys.stdin", io.StringIO("hola\nmundo\n.\nignorado\n"))
    def test_stops_at_dot_sentinel(self, _c):
        self.assertEqual(read_pasted_text(), "hola\nmundo")

    @patch("jobhunter.cli.apply.console")
    @patch("jobhunter.cli.apply.sys.stdin", io.StringIO("solo una linea\n"))
    def test_eof_without_sentinel(self, _c):
        self.assertEqual(read_pasted_text(), "solo una linea")


class CmdApplyTests(unittest.TestCase):
    @patch("jobhunter.cli.apply.console")
    @patch("jobhunter.cli.apply.save_kb")
    @patch("jobhunter.cli.apply.apply_to_offer", return_value={"status": "sent", "record": {}, "preview_send_all": False})
    @patch("jobhunter.cli.apply.agent_filter")
    @patch("jobhunter.cli.apply.load_kb", return_value={"applications": []})
    @patch("jobhunter.cli.apply.load_config", return_value=_cfg())
    @patch("jobhunter.cli.apply.is_configured", return_value=True)
    def test_text_flow_calls_apply_with_manual_mode(self, _ic, _lc, _lk, mock_filter, mock_apply, mock_save, _c):
        mock_filter.return_value = {
            "is_job": True, "is_relevant": True, "job_title": "Dev II",
            "company": "Simon", "contact_email": "maria@simon.com",
        }
        cmd_apply(POST)
        mock_apply.assert_called_once()
        self.assertEqual(mock_apply.call_args.kwargs.get("mode"), "manual")
        mock_save.assert_called_once()

    @patch("jobhunter.cli.apply.console")
    @patch("jobhunter.cli.apply.Confirm")
    @patch("jobhunter.cli.apply.apply_to_offer")
    @patch("jobhunter.cli.apply.agent_filter")
    @patch("jobhunter.cli.apply.load_kb", return_value={"applications": []})
    @patch("jobhunter.cli.apply.load_config", return_value=_cfg())
    @patch("jobhunter.cli.apply.is_configured", return_value=True)
    def test_not_relevant_and_user_declines(self, _ic, _lc, _lk, mock_filter, mock_apply, mock_confirm, _c):
        mock_filter.return_value = {
            "is_job": True, "is_relevant": False, "relevance_reason": "no encaja",
            "job_title": "X", "company": "Y", "contact_email": "a@b.com",
        }
        mock_confirm.ask.return_value = False
        cmd_apply(POST)
        mock_apply.assert_not_called()

    @patch("jobhunter.cli.apply.console")
    @patch("jobhunter.cli.apply.Prompt")
    @patch("jobhunter.cli.apply.save_kb")
    @patch("jobhunter.cli.apply.apply_to_offer", return_value={"status": "sent", "record": {}, "preview_send_all": False})
    @patch("jobhunter.cli.apply.agent_filter")
    @patch("jobhunter.cli.apply.load_kb", return_value={"applications": []})
    @patch("jobhunter.cli.apply.load_config", return_value=_cfg())
    @patch("jobhunter.cli.apply.is_configured", return_value=True)
    def test_missing_email_prompts_with_extracted_default(self, _ic, _lc, _lk, mock_filter, mock_apply, _save, mock_prompt, _c):
        mock_filter.return_value = {
            "is_job": True, "is_relevant": True, "job_title": "Dev",
            "company": "Simon", "contact_email": None,
        }
        mock_prompt.ask.return_value = "maria@simon.com"
        cmd_apply(POST)
        self.assertEqual(mock_prompt.ask.call_args_list[0].kwargs.get("default"), "maria@simon.com")
        job_sent = mock_apply.call_args.args[2]
        self.assertEqual(job_sent["contact_email"], "maria@simon.com")

    @patch("jobhunter.cli.apply.console")
    @patch("jobhunter.cli.apply.load_kb", return_value={"applications": []})
    @patch("jobhunter.cli.apply.load_config", return_value=_cfg())
    @patch("jobhunter.cli.apply.is_configured", return_value=True)
    def test_short_text_aborts(self, _ic, _lc, _lk, mock_console):
        cmd_apply("muy corto")
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("demasiado corto", printed)


if __name__ == "__main__":
    unittest.main()
