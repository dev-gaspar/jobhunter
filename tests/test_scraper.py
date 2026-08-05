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


class FakeEl:
    def __init__(self, text):
        self._text = text

    def inner_text(self):
        return self._text

    def click(self):
        pass


class FakePage:
    def __init__(self, mapping, main_text=""):
        self.mapping = mapping
        self.main_text = main_text

    def query_selector(self, sel):
        return self.mapping.get(sel)

    def wait_for_timeout(self, ms):
        pass

    def inner_text(self, sel):
        return self.main_text


class CollectPostUrlsTests(unittest.TestCase):
    def test_keeps_only_valid_http_values(self):
        from jobhunter.scraper import collect_post_urls
        page = MagicMock()
        page.evaluate.return_value = {
            "post uno texto": "https://lnkd.in/p/abc",
            "post dos texto": "not-a-url",
            "post tres texto": None,
            "post cuatro texto": 123,
            "post cinco texto": "  https://lnkd.in/p/xyz  ",
        }
        urls = collect_post_urls(page)
        self.assertEqual(urls, {
            "post uno texto": "https://lnkd.in/p/abc",
            "post cinco texto": "https://lnkd.in/p/xyz",
        })

    def test_survives_evaluate_errors(self):
        from jobhunter.scraper import collect_post_urls
        page = MagicMock()
        page.evaluate.side_effect = RuntimeError("boom")
        self.assertEqual(collect_post_urls(page), {})

    def test_non_dict_result_is_empty(self):
        from jobhunter.scraper import collect_post_urls
        page = MagicMock()
        page.evaluate.return_value = ["https://x"]
        self.assertEqual(collect_post_urls(page), {})


class ExtractPostTextTests(unittest.TestCase):
    def test_prefers_expandable_text_box(self):
        from jobhunter.scraper import extract_post_text
        page = FakePage({'span[data-testid="expandable-text-box"]': FakeEl("Oferta de trabajo " + "x" * 60)})
        self.assertTrue(extract_post_text(page).startswith("Oferta de trabajo"))

    def test_falls_back_to_article(self):
        from jobhunter.scraper import extract_post_text
        page = FakePage({"article": FakeEl("Texto del articulo " + "y" * 60)})
        self.assertTrue(extract_post_text(page).startswith("Texto del articulo"))

    def test_last_resort_main_text(self):
        from jobhunter.scraper import extract_post_text
        page = FakePage({}, main_text="Contenido main de respaldo " + "z" * 60)
        self.assertIn("Contenido main", extract_post_text(page))

    def test_short_candidates_are_skipped(self):
        from jobhunter.scraper import extract_post_text
        page = FakePage(
            {'span[data-testid="expandable-text-box"]': FakeEl("corto")},
            main_text="Respaldo largo " + "w" * 60,
        )
        self.assertIn("Respaldo largo", extract_post_text(page))


if __name__ == "__main__":
    unittest.main()
