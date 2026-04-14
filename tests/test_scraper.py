# -*- coding: utf-8 -*-
"""Tests limitados del scraper: partes controlables sin navegador real."""
import unittest
from unittest.mock import MagicMock, patch

from jobhunter.scraper import scrape_posts


class ScrapePostsTests(unittest.TestCase):
    def test_returns_empty_when_goto_fails(self):
        page = MagicMock()
        page.goto.side_effect = Exception("timeout")
        result = scrape_posts(page, "python dev", time_filter="24h")
        self.assertEqual(result, [])

    def test_time_filter_fallback(self):
        """Cualquier filtro invalido debe usar past-24h en la URL."""
        page = MagicMock()
        page.goto.side_effect = Exception("stop")
        # No importa el resultado, verificamos que no crashea
        scrape_posts(page, "q", time_filter="invalid")
        url = page.goto.call_args.args[0]
        self.assertIn("past-24h", url)

    def test_time_filter_week_applied(self):
        page = MagicMock()
        page.goto.side_effect = Exception("stop")
        scrape_posts(page, "q", time_filter="week")
        url = page.goto.call_args.args[0]
        self.assertIn("past-week", url)

    def test_query_url_encoded(self):
        page = MagicMock()
        page.goto.side_effect = Exception("stop")
        scrape_posts(page, "python dev", time_filter="24h")
        url = page.goto.call_args.args[0]
        self.assertIn("python%20dev", url)


if __name__ == "__main__":
    unittest.main()
