import os
import tempfile
import unittest
from unittest.mock import patch


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.kb_path = os.path.join(self.tmpdir, "knowledge.json")
        self.patcher = patch("jobhunter.storage.KB_PATH", self.kb_path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        if os.path.exists(self.kb_path):
            os.remove(self.kb_path)
        os.rmdir(self.tmpdir)

    def test_load_empty_returns_default_structure(self):
        from jobhunter.storage import load_kb
        kb = load_kb()
        self.assertEqual(kb, {"runs": [], "applications": [], "rejected_companies": []})

    def test_roundtrip_save_load(self):
        from jobhunter.storage import load_kb, save_kb
        data = {
            "runs": [{"date": "2026-01-01", "posts": 10}],
            "applications": [{"company": "Acme"}],
            "rejected_companies": ["Badco"],
        }
        save_kb(data)
        self.assertEqual(load_kb(), data)


if __name__ == "__main__":
    unittest.main()
