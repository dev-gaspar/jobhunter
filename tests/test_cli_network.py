# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from jobhunter.cli.network import build_network_queue, cmd_network


def _app(url, name="Rec", date="2026-08-01T10:00:00", company="Acme", title="Dev"):
    return {"author_url": url, "author_name": name, "date": date,
            "company": company, "job_title": title}


class BuildNetworkQueueTests(unittest.TestCase):
    def test_dedups_and_excludes_existing(self):
        apps = [
            _app("https://linkedin.com/in/ana", date="2026-08-03T10:00:00"),
            _app("https://linkedin.com/in/ana", date="2026-08-01T10:00:00"),
            _app("https://linkedin.com/in/luis", date="2026-08-02T10:00:00"),
            _app("https://linkedin.com/in/eva", date="2026-08-04T10:00:00"),
            {"date": "2026-08-05T10:00:00", "company": "SinAutor", "job_title": "X"},
        ]
        network = [{"profile_url": "https://linkedin.com/in/eva", "status": "invited"}]
        queue = build_network_queue(apps, network)
        self.assertEqual([q["profile_url"] for q in queue],
                         ["https://linkedin.com/in/ana", "https://linkedin.com/in/luis"])

    def test_empty_inputs(self):
        self.assertEqual(build_network_queue([], []), [])
        self.assertEqual(build_network_queue(None, None), [])


class CmdNetworkTests(unittest.TestCase):
    @patch("jobhunter.cli.network.console")
    @patch("jobhunter.cli.network.save_kb")
    @patch("jobhunter.cli.network.webbrowser")
    @patch("jobhunter.cli.network.Confirm")
    @patch("jobhunter.cli.network.Prompt")
    @patch("jobhunter.cli.network.load_kb")
    def test_open_confirm_then_quit(self, mock_lk, mock_prompt, mock_confirm, mock_wb, mock_save, _c):
        kb = {"applications": [
            _app("https://linkedin.com/in/ana"),
            _app("https://linkedin.com/in/luis"),
        ], "network": []}
        mock_lk.return_value = kb
        mock_prompt.ask.side_effect = ["a", "q"]
        mock_confirm.ask.return_value = True
        cmd_network()
        mock_wb.open.assert_called_once_with("https://linkedin.com/in/ana")
        self.assertEqual(len(kb["network"]), 1)
        self.assertEqual(kb["network"][0]["status"], "invited")
        mock_save.assert_called_once_with(kb)

    @patch("jobhunter.cli.network.console")
    @patch("jobhunter.cli.network.save_kb")
    @patch("jobhunter.cli.network.webbrowser")
    @patch("jobhunter.cli.network.Prompt")
    @patch("jobhunter.cli.network.load_kb")
    def test_skip_records_skipped(self, mock_lk, mock_prompt, mock_wb, mock_save, _c):
        kb = {"applications": [_app("https://linkedin.com/in/ana")], "network": []}
        mock_lk.return_value = kb
        mock_prompt.ask.side_effect = ["x"]
        cmd_network()
        mock_wb.open.assert_not_called()
        self.assertEqual(kb["network"][0]["status"], "skipped")

    @patch("jobhunter.cli.network.console")
    @patch("jobhunter.cli.network.load_kb", return_value={"applications": [], "network": []})
    def test_empty_queue_explains(self, _lk, mock_console):
        cmd_network()
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("Sin candidatos", printed)


if __name__ == "__main__":
    unittest.main()
