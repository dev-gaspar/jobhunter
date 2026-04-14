import os
import tempfile
import unittest
from unittest.mock import patch

from jobhunter.browser import find_chrome, kill_playwright_zombies


class FindChromeTests(unittest.TestCase):
    @patch("jobhunter.browser.os.path.exists")
    def test_returns_first_existing_path(self, mock_exists):
        mock_exists.side_effect = lambda p: "Chrome" in p
        result = find_chrome()
        self.assertIsNotNone(result)
        self.assertIn("chrome.exe", result.lower())

    @patch("jobhunter.browser.shutil.which")
    @patch("jobhunter.browser.os.path.exists", return_value=False)
    def test_falls_back_to_path_which(self, _exists, mock_which):
        mock_which.side_effect = ["/usr/bin/chrome", None]
        result = find_chrome()
        self.assertEqual(result, "/usr/bin/chrome")

    @patch("jobhunter.browser.shutil.which", return_value=None)
    @patch("jobhunter.browser.os.path.exists", return_value=False)
    def test_returns_none_when_nothing_found(self, _exists, _which):
        self.assertIsNone(find_chrome())


class KillZombiesTests(unittest.TestCase):
    def test_removes_singleton_lock_when_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "SingletonLock")
            with open(lock, "w") as f:
                f.write("x")
            with patch("jobhunter.browser.SESSION_DIR", tmp), \
                 patch("jobhunter.browser.time.sleep"):
                kill_playwright_zombies()
            self.assertFalse(os.path.exists(lock))

    def test_noop_when_lock_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("jobhunter.browser.SESSION_DIR", tmp), \
                 patch("jobhunter.browser.time.sleep") as mock_sleep:
                kill_playwright_zombies()
                mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
