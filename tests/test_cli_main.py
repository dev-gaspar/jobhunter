# -*- coding: utf-8 -*-
import sys
import unittest
from unittest.mock import patch

from jobhunter.cli.main import main, parse_time_filter


class ParseTimeFilterTests(unittest.TestCase):
    def test_default_24h(self):
        self.assertEqual(parse_time_filter(["jobhunter", "run"]), "24h")

    def test_week(self):
        self.assertEqual(parse_time_filter(["jobhunter", "run", "--time", "week"]), "week")

    def test_month(self):
        self.assertEqual(parse_time_filter(["jobhunter", "run", "--time", "month"]), "month")

    @patch("jobhunter.cli.main.console")
    def test_invalid_exits(self, _console):
        with self.assertRaises(SystemExit) as ctx:
            parse_time_filter(["jobhunter", "run", "--time", "year"])
        self.assertEqual(ctx.exception.code, 1)


class MainDispatcherTests(unittest.TestCase):
    @patch("jobhunter.cli.main.check_for_updates")
    @patch("jobhunter.cli.main.cmd_setup")
    @patch("jobhunter.cli.main.is_configured", return_value=False)
    def test_no_args_unconfigured_runs_setup(self, _ic, mock_setup, _check):
        with patch.object(sys, "argv", ["jobhunter"]):
            main()
        mock_setup.assert_called_once()

    @patch("jobhunter.cli.main.check_for_updates")
    @patch("jobhunter.cli.main.cmd_help")
    @patch("jobhunter.cli.main.is_configured", return_value=True)
    def test_no_args_configured_shows_help(self, _ic, mock_help, _check):
        with patch.object(sys, "argv", ["jobhunter"]):
            main()
        mock_help.assert_called_once()

    @patch("jobhunter.cli.main.check_for_updates")
    @patch("jobhunter.cli.main.cmd_status")
    def test_status_dispatch(self, mock_status, _check):
        with patch.object(sys, "argv", ["jobhunter", "status"]):
            main()
        mock_status.assert_called_once()

    @patch("jobhunter.cli.main.check_for_updates")
    @patch("jobhunter.cli.main.cmd_run")
    def test_run_passes_flags(self, mock_run, _check):
        with patch.object(sys, "argv", ["jobhunter", "run", "--auto", "--dry", "--time", "week"]):
            main()
        kwargs = mock_run.call_args.kwargs
        self.assertTrue(kwargs["auto_apply"])
        self.assertTrue(kwargs["dry_run"])
        self.assertEqual(kwargs["time_filter"], "week")

    @patch("jobhunter.cli.main.check_for_updates")
    @patch("jobhunter.cli.main.cmd_run")
    def test_test_mode_passes_email(self, mock_run, _check):
        with patch.object(sys, "argv", ["jobhunter", "--test", "me@test.com"]):
            main()
        kwargs = mock_run.call_args.kwargs
        self.assertEqual(kwargs["test_email"], "me@test.com")

    @patch("jobhunter.cli.main.check_for_updates")
    @patch("jobhunter.cli.main.cmd_history")
    def test_history_parses_filters(self, mock_history, _check):
        with patch.object(sys, "argv", [
            "jobhunter", "history", "--last", "5", "--company", "Acme", "--since", "2026-01-01", "--all"
        ]):
            main()
        kwargs = mock_history.call_args.kwargs
        self.assertEqual(kwargs["last"], 5)
        self.assertEqual(kwargs["company_filter"], "Acme")
        self.assertEqual(kwargs["since"], "2026-01-01")
        self.assertTrue(kwargs["show_all"])

    @patch("jobhunter.cli.main.check_for_updates")
    @patch("jobhunter.cli.main.cmd_blacklist")
    def test_blacklist_add(self, mock_bl, _check):
        with patch.object(sys, "argv", ["jobhunter", "blacklist", "add", "BadCorp"]):
            main()
        mock_bl.assert_called_once_with("add", "BadCorp")

    @patch("jobhunter.cli.main.console")
    @patch("jobhunter.cli.main.check_for_updates")
    def test_unknown_command_shows_hint(self, _check, mock_console):
        with patch.object(sys, "argv", ["jobhunter", "bogus"]):
            main()
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("Comando desconocido", printed)


if __name__ == "__main__":
    unittest.main()
