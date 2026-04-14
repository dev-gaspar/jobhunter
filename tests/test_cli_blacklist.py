# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from jobhunter.cli.blacklist import cmd_blacklist


class CmdBlacklistTests(unittest.TestCase):
    @patch("jobhunter.cli.blacklist.console")
    @patch("jobhunter.cli.blacklist.save_kb")
    @patch("jobhunter.cli.blacklist.load_kb", return_value={"rejected_companies": []})
    def test_add_new_company(self, _lkb, mock_save, mock_console):
        cmd_blacklist(action="add", company="BadCorp")
        mock_save.assert_called_once()
        saved = mock_save.call_args.args[0]
        self.assertIn("BadCorp", saved["rejected_companies"])

    @patch("jobhunter.cli.blacklist.console")
    @patch("jobhunter.cli.blacklist.save_kb")
    @patch("jobhunter.cli.blacklist.load_kb", return_value={"rejected_companies": ["badcorp"]})
    def test_add_duplicate_case_insensitive(self, _lkb, mock_save, mock_console):
        cmd_blacklist(action="add", company="BadCorp")
        mock_save.assert_not_called()
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("ya esta", printed)

    @patch("jobhunter.cli.blacklist.console")
    @patch("jobhunter.cli.blacklist.save_kb")
    @patch("jobhunter.cli.blacklist.load_kb", return_value={"rejected_companies": ["BadCorp", "OtherCo"]})
    def test_remove_existing(self, _lkb, mock_save, mock_console):
        cmd_blacklist(action="remove", company="badcorp")
        mock_save.assert_called_once()
        saved = mock_save.call_args.args[0]
        self.assertNotIn("BadCorp", saved["rejected_companies"])

    @patch("jobhunter.cli.blacklist.console")
    @patch("jobhunter.cli.blacklist.load_kb", return_value={"rejected_companies": ["A", "B"]})
    def test_list_shows_all(self, _lkb, mock_console):
        cmd_blacklist()
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("A", printed)
        self.assertIn("B", printed)


if __name__ == "__main__":
    unittest.main()
