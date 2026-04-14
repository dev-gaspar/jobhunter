# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from jobhunter.cli.status import cmd_status


CFG = {
    "profile": {"name": "Jose"},
    "smtp_email": "jose@gmail.com",
    "gemini_api_key": "AIzaKEY",
    "smtp_password": "pass",
    "gemini_model": "gemini-2.5-flash",
    "cv_path": "/tmp/cv.pdf",
    "job_types_raw": "backend developer",
    "search_queries": ["q1", "q2", "q3"],
}

KB = {
    "runs": [{"date": "2026-04-10T10:00:00"}],
    "applications": [{"mode": "run"}, {"mode": "run"}, {"mode": "test"}],
}


class CmdStatusTests(unittest.TestCase):
    @patch("jobhunter.cli.status.console")
    @patch("jobhunter.cli.status.os.path.exists", return_value=True)
    @patch("jobhunter.cli.status.load_kb", return_value=KB)
    @patch("jobhunter.cli.status.load_config", return_value=CFG)
    def test_status_prints_info(self, _cfg, _kb, _exists, mock_console):
        cmd_status()
        # Al menos debe haber llamado print varias veces
        self.assertGreater(mock_console.print.call_count, 2)

    @patch("jobhunter.cli.status.console")
    @patch("jobhunter.cli.status.os.path.exists", return_value=True)
    @patch("jobhunter.cli.status.load_kb", return_value={"runs": [], "applications": []})
    @patch("jobhunter.cli.status.load_config", return_value={})
    def test_status_with_empty_config(self, _cfg, _kb, _exists, mock_console):
        cmd_status()
        # No debe crashear con config vacia
        self.assertGreater(mock_console.print.call_count, 0)


if __name__ == "__main__":
    unittest.main()
