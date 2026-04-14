import json
import os
import tempfile
import unittest
from unittest.mock import patch


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cfg_path = os.path.join(self.tmpdir, "config.json")
        self.patcher = patch("jobhunter.config.CONFIG_PATH", self.cfg_path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        if os.path.exists(self.cfg_path):
            os.remove(self.cfg_path)
        os.rmdir(self.tmpdir)

    def test_load_returns_empty_when_no_file(self):
        from jobhunter.config import load_config
        self.assertEqual(load_config(), {})

    def test_roundtrip_save_load(self):
        from jobhunter.config import load_config, save_config
        save_config({"a": 1, "b": "x"})
        self.assertEqual(load_config(), {"a": 1, "b": "x"})

    def test_is_configured_requires_all_fields(self):
        from jobhunter.config import is_configured, save_config
        save_config({})
        self.assertFalse(is_configured())
        save_config({
            "gemini_api_key": "k",
            "smtp_email": "e@e.com",
            "smtp_password": "p",
            "profile": {"name": "x"},
        })
        self.assertTrue(is_configured())

    def test_is_configured_fails_missing_one(self):
        from jobhunter.config import is_configured, save_config
        save_config({
            "gemini_api_key": "k",
            "smtp_email": "e@e.com",
            "smtp_password": "p",
            # profile missing
        })
        self.assertFalse(is_configured())

    def test_roundtrip_preserves_unicode(self):
        from jobhunter.config import load_config, save_config
        save_config({"name": "Jose Gaspar", "city": "Bogota"})
        loaded = load_config()
        self.assertEqual(loaded["name"], "Jose Gaspar")
        self.assertEqual(loaded["city"], "Bogota")


if __name__ == "__main__":
    unittest.main()
