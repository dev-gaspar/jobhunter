import subprocess
import unittest
from unittest.mock import MagicMock, patch

from jobhunter.updater import check_for_updates, cmd_update


def _completed(returncode=0, stdout="", stderr=""):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


class CheckForUpdatesTests(unittest.TestCase):
    @patch("jobhunter.updater.console")
    @patch("jobhunter.updater.subprocess.run")
    def test_prints_when_remote_has_changes(self, mock_run, mock_console):
        mock_run.return_value = _completed(stderr="From origin\n  abc..def main")
        check_for_updates()
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("nueva version", printed.lower())

    @patch("jobhunter.updater.console")
    @patch("jobhunter.updater.subprocess.run")
    def test_silent_when_no_changes(self, mock_run, mock_console):
        mock_run.return_value = _completed(stderr="")
        check_for_updates()
        mock_console.print.assert_not_called()

    @patch("jobhunter.updater.console")
    @patch("jobhunter.updater.subprocess.run", side_effect=Exception("no git"))
    def test_swallows_exceptions(self, _run, mock_console):
        check_for_updates()
        mock_console.print.assert_not_called()


class CmdUpdateTests(unittest.TestCase):
    @patch("jobhunter.updater.console")
    @patch("jobhunter.updater.subprocess.run")
    def test_already_up_to_date(self, mock_run, mock_console):
        mock_run.side_effect = [
            _completed(stdout="Already up to date."),
            _completed(stdout=""),
        ]
        cmd_update()
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("ultima version", printed)

    @patch("jobhunter.updater.console")
    @patch("jobhunter.updater.subprocess.run")
    def test_updated_successfully(self, mock_run, mock_console):
        mock_run.side_effect = [
            _completed(stdout="Updating abc..def\n job.py | 1 +"),
            _completed(stdout=""),
        ]
        cmd_update()
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("Actualizado", printed)

    @patch("jobhunter.updater.console")
    @patch("jobhunter.updater.subprocess.run")
    def test_error_returncode(self, mock_run, mock_console):
        mock_run.return_value = _completed(returncode=1, stderr="conflict")
        cmd_update()
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("Error", printed)

    @patch("jobhunter.updater.console")
    @patch("jobhunter.updater.subprocess.run", side_effect=FileNotFoundError())
    def test_git_not_installed(self, _run, mock_console):
        cmd_update()
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("git no esta instalado", printed)


if __name__ == "__main__":
    unittest.main()
