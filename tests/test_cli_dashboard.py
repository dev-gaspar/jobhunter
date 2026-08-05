# -*- coding: utf-8 -*-
import json
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from jobhunter.cli.dashboard import DashboardHandler
from http.server import ThreadingHTTPServer


class DashboardHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path):
        url = "http://127.0.0.1:" + str(self.port) + path
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read()

    @patch("jobhunter.cli.dashboard.load_kb", return_value={"runs": [], "applications": []})
    def test_api_data_returns_json(self, _kb):
        status, body = self._get("/api/data")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("totals", data)
        self.assertIn("applications", data)
        self.assertIn("weeks", data)

    def test_index_serves_html(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"JobHunter", body)

    def test_unknown_path_404(self):
        try:
            status, _ = self._get("/nope")
        except urllib.error.HTTPError as e:
            status = e.code
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
