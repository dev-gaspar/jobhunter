# -*- coding: utf-8 -*-
import imaplib
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from jobhunter.cli.sync import cmd_sync


def _cfg():
    return {"smtp_email": "yo@gmail.com", "smtp_password": "app-pass", "profile": {"name": "J"}}


def _recent(days_ago=2):
    return (datetime.now() - timedelta(days=days_ago)).isoformat()


def _kb():
    return {
        "runs": [],
        "applications": [
            {"date": _recent(2), "job_title": "A", "company": "C1",
             "recruiter_email": "r1@x.com", "sent_to": "r1@x.com", "mode": "run"},
            {"date": _recent(3), "job_title": "B", "company": "C2",
             "recruiter_email": "r2@x.com", "sent_to": "r2@x.com", "mode": "run",
             "status": "replied", "reply_date": _recent(1)},
            {"date": "2020-01-01T00:00:00", "job_title": "Vieja", "company": "C3",
             "recruiter_email": "r3@x.com", "sent_to": "r3@x.com", "mode": "run"},
        ],
    }


class CmdSyncTests(unittest.TestCase):
    @patch("jobhunter.cli.sync.console")
    @patch("jobhunter.cli.sync.save_kb")
    @patch("jobhunter.cli.sync.fetch_inbox")
    @patch("jobhunter.cli.sync.load_kb")
    @patch("jobhunter.cli.sync.load_config", return_value=_cfg())
    def test_reconciles_pending_and_saves(self, _lc, mock_lk, mock_fetch, mock_save, _c):
        kb = _kb()
        mock_lk.return_value = kb
        mock_fetch.return_value = (
            [{"from_email": "r1@x.com", "date": datetime.now(), "subject": "Re: CV"}], [],
        )
        cmd_sync(days=60)
        self.assertEqual(kb["applications"][0]["status"], "replied")
        self.assertNotIn("status", kb["applications"][2])  # fuera de ventana
        mock_save.assert_called_once_with(kb)
        # la app terminal previa no se re-chequea: la ventana arranca en la pendiente
        since = mock_fetch.call_args.args[1]
        self.assertGreater(since, datetime.now() - timedelta(days=10))

    @patch("jobhunter.cli.sync.console")
    @patch("jobhunter.cli.sync.save_kb")
    @patch("jobhunter.cli.sync.fetch_inbox", side_effect=imaplib.IMAP4.error("auth"))
    @patch("jobhunter.cli.sync.load_kb")
    @patch("jobhunter.cli.sync.load_config", return_value=_cfg())
    def test_imap_auth_error_message(self, _lc, mock_lk, _fetch, mock_save, mock_console):
        mock_lk.return_value = _kb()
        cmd_sync(days=60)
        mock_save.assert_not_called()
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("IMAP", printed)

    @patch("jobhunter.cli.sync.console")
    @patch("jobhunter.cli.sync.load_kb", return_value={"runs": [], "applications": []})
    @patch("jobhunter.cli.sync.load_config", return_value=_cfg())
    def test_nothing_pending(self, _lc, _lk, mock_console):
        cmd_sync(days=60)
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("Nada que conciliar", printed)


if __name__ == "__main__":
    unittest.main()
