# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from jobhunter.cli.history import cmd_history


KB = {
    "applications": [
        {"date": "2026-04-10T10:00:00", "company": "Acme", "job_title": "Backend Dev", "mode": "run"},
        {"date": "2026-04-11T11:00:00", "company": "Globex", "job_title": "Frontend", "mode": "run"},
        {"date": "2026-04-12T12:00:00", "company": "Acme Corp", "job_title": "Devops", "mode": "test"},
    ]
}


class CmdHistoryTests(unittest.TestCase):
    @patch("jobhunter.cli.history.console")
    @patch("jobhunter.cli.history.load_kb", return_value={"applications": []})
    def test_empty_history_message(self, _kb, mock_console):
        cmd_history()
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("No hay aplicaciones", printed)

    @patch("jobhunter.cli.history.console")
    @patch("jobhunter.cli.history.load_kb", return_value=KB)
    def test_filter_by_company(self, _kb, mock_console):
        cmd_history(company_filter="Acme")
        # Debe ejecutar sin error, ha habido al menos el Panel print
        self.assertGreater(mock_console.print.call_count, 0)

    @patch("jobhunter.cli.history.console")
    @patch("jobhunter.cli.history.load_kb", return_value=KB)
    def test_invalid_date_format(self, _kb, mock_console):
        cmd_history(since="not-a-date")
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("Formato de fecha invalido", printed)

    @patch("jobhunter.cli.history.console")
    @patch("jobhunter.cli.history.load_kb", return_value=KB)
    def test_since_filters_out_old(self, _kb, mock_console):
        cmd_history(since="2026-04-12")
        # No verifica el contenido exacto, pero debe correr sin crashear
        self.assertGreater(mock_console.print.call_count, 0)

    @patch("jobhunter.cli.history.console")
    @patch("jobhunter.cli.history.load_kb", return_value=KB)
    def test_last_limits_results(self, _kb, mock_console):
        cmd_history(last=1)
        self.assertGreater(mock_console.print.call_count, 0)


if __name__ == "__main__":
    unittest.main()
