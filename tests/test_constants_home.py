# -*- coding: utf-8 -*-
"""BASE_DIR debe respetar JOBHUNTER_HOME y el modo frozen (PyInstaller)."""
import importlib
import os
import sys
import tempfile
import unittest


def _reload_constants():
    import jobhunter.constants as c
    return importlib.reload(c)


class TestConstantsHome(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("JOBHUNTER_HOME", None)
        if hasattr(sys, "frozen"):
            del sys.frozen
        _reload_constants()

    def test_default_base_dir_is_repo_root(self):
        c = _reload_constants()
        self.assertTrue(os.path.exists(os.path.join(c.BASE_DIR, "jobhunter")))

    def test_env_var_overrides(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["JOBHUNTER_HOME"] = td
            c = _reload_constants()
            self.assertEqual(c.BASE_DIR, td)
            self.assertEqual(c.CONFIG_PATH, os.path.join(td, "config.json"))
            self.assertEqual(c.SESSION_DIR, os.path.join(td, ".session"))
            self.assertEqual(c.KB_PATH, os.path.join(td, "knowledge.json"))

    def test_frozen_uses_home_dotjobhunter(self):
        sys.frozen = True
        c = _reload_constants()
        expected = os.path.join(os.path.expanduser("~"), ".jobhunter")
        self.assertEqual(c.BASE_DIR, expected)

    def test_env_var_wins_over_frozen(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["JOBHUNTER_HOME"] = td
            sys.frozen = True
            c = _reload_constants()
            self.assertEqual(c.BASE_DIR, td)


if __name__ == "__main__":
    unittest.main()
