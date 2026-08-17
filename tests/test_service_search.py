# -*- coding: utf-8 -*-
"""Tests de service.search_offers: eventos, filtros y paridad con el pipeline."""
import unittest
from unittest.mock import MagicMock, patch

from jobhunter.service import search_offers

CFG = {
    "gemini_api_key": "k",
    "smtp_email": "yo@gmail.com",
    "smtp_password": "apppassword123456",
    "profile": {"name": "Jose"},
    "search_queries": ["query uno", "query dos"],
}


def _kb(**over):
    kb = {"runs": [], "applications": [], "rejected_companies": []}
    kb.update(over)
    return kb


def _post(text, emails, index=0, url="https://lnkd.in/x"):
    return {
        "text": text,
        "emails_found": emails,
        "index": index,
        "author_url": None,
        "author_name": None,
        "post_url": url,
    }


def _offer_answer(**over):
    a = {
        "is_job": True,
        "job_title": "Backend Dev",
        "company": "TechCo",
        "description": "d",
        "requirements": "r",
        "contact_email": "hr@techco.com",
        "contact_name": "HR",
        "location": "Remote",
        "work_mode": "remote",
        "salary": None,
        "language": "es",
        "is_relevant": True,
        "relevance_reason": "match",
    }
    a.update(over)
    return a


def _fake_playwright(page_url="https://www.linkedin.com/feed/"):
    """Construye el mock del context manager sync_playwright()."""
    page = MagicMock()
    page.url = page_url
    page.query_selector_all.return_value = []
    browser = MagicMock()
    browser.pages = [page]
    p = MagicMock()
    p.chromium.launch_persistent_context.return_value = browser
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=p)
    cm.__exit__ = MagicMock(return_value=False)
    return cm, page


class SearchBase(unittest.TestCase):
    def setUp(self):
        self.events = []
        patches = [
            patch("jobhunter.service.kill_playwright_zombies"),
            patch("jobhunter.service.find_chrome", return_value="C:/chrome.exe"),
            patch("jobhunter.service.os.path.exists", return_value=True),
        ]
        for pt in patches:
            pt.start()
            self.addCleanup(pt.stop)

    def on_event(self, name, payload):
        self.events.append((name, payload))

    def names(self):
        return [n for n, _ in self.events]

    def run_search(self, cfg=None, kb=None, scrape_side_effect=None,
                   filter_side_effect=None, page_url="https://www.linkedin.com/feed/"):
        cm, page = _fake_playwright(page_url)
        with patch("jobhunter.service.sync_playwright", return_value=cm), \
             patch("jobhunter.service.scrape_posts", side_effect=scrape_side_effect or [[], []]), \
             patch("jobhunter.service.agent_filter", side_effect=filter_side_effect or []):
            return search_offers(cfg or CFG, kb or _kb(), on_event=self.on_event, pace=False)


class TestGuards(SearchBase):
    def test_not_configured(self):
        res = search_offers({"profile": {}}, _kb(), on_event=self.on_event, pace=False)
        self.assertEqual(res["error"]["kind"], "not_configured")
        self.assertNotIn("phase", self.names())

    def test_no_session(self):
        with patch("jobhunter.service.os.path.exists", return_value=False):
            res = search_offers(CFG, _kb(), on_event=self.on_event, pace=False)
        self.assertEqual(res["error"]["kind"], "no_session")

    def test_session_expired(self):
        res = self.run_search(page_url="https://www.linkedin.com/login")
        self.assertEqual(res["error"]["kind"], "session_expired")

    def test_no_posts_with_email(self):
        res = self.run_search(scrape_side_effect=[[_post("x" * 60, [])], []])
        self.assertEqual(res["error"]["kind"], "no_posts")
        self.assertEqual(res["stats"]["posts_scraped"], 1)


class TestHappyPath(SearchBase):
    def test_full_flow(self):
        p1 = _post("oferta real con email " + "a" * 100, ["hr@techco.com"], index=0)
        p2 = _post("texto sin email " + "b" * 60, [], index=1)
        p3 = _post("oferta irrelevante " + "c" * 100, ["x@y.com"], index=2)
        dup = dict(p1)
        res = self.run_search(
            scrape_side_effect=[[p1, p2], [dup, p3]],
            filter_side_effect=[
                _offer_answer(),
                _offer_answer(is_relevant=False, relevance_reason="otro rubro",
                              company="OtraCo", contact_email="x@y.com"),
            ],
        )
        self.assertIsNone(res["error"])
        self.assertEqual(len(res["offers"]), 1)
        offer = res["offers"][0]
        self.assertEqual(offer["company"], "TechCo")
        self.assertEqual(offer["post_url"], p1["post_url"])
        self.assertEqual(offer["query"], "query uno")
        self.assertEqual(res["stats"]["posts_scraped"], 3)
        self.assertEqual(res["stats"]["posts_with_emails"], 2)
        self.assertEqual(res["stats"]["filter_accepted"], 1)
        self.assertEqual(len(res["decisions"]), 2)
        names = self.names()
        phases = [(p["phase"], p["status"]) for n, p in self.events if n == "phase"]
        self.assertEqual(phases, [
            ("scrape", "start"), ("scrape", "done"),
            ("analyze", "start"), ("analyze", "done"),
            ("dedupe", "start"), ("dedupe", "done"),
        ])
        self.assertIn("progress", names)
        self.assertIn("decision", names)

    def test_short_text_skipped(self):
        p1 = _post("corto", ["a@b.com"])
        res = self.run_search(scrape_side_effect=[[p1], []], filter_side_effect=[])
        self.assertEqual(len(res["offers"]), 0)
        self.assertEqual(len(res["decisions"]), 1)
        self.assertIn("skipped", res["decisions"][0]["relevance_reason"])

    def test_invalid_email_cleaned(self):
        p1 = _post("oferta " + "a" * 100, ["hr@techco.com"])
        res = self.run_search(
            scrape_side_effect=[[p1], []],
            filter_side_effect=[_offer_answer(contact_email="null")],
        )
        self.assertEqual(len(res["offers"]), 0)
        self.assertEqual(res["stats"]["offers_no_email"], 1)


class TestFilters(SearchBase):
    def test_blacklist_excludes(self):
        p1 = _post("oferta " + "a" * 100, ["hr@techco.com"])
        res = self.run_search(
            kb=_kb(rejected_companies=["techco"]),
            scrape_side_effect=[[p1], []],
            filter_side_effect=[_offer_answer()],
        )
        self.assertEqual(len(res["offers"]), 0)
        self.assertEqual(res["stats"]["blacklisted"], 1)

    def test_cooldown_excludes(self):
        from datetime import datetime
        p1 = _post("oferta " + "a" * 100, ["hr@techco.com"])
        apps = [{"date": datetime.now().isoformat(), "company": "TechCo",
                 "job_title": "Backend Dev"}]
        res = self.run_search(
            kb=_kb(applications=apps),
            scrape_side_effect=[[p1], []],
            filter_side_effect=[_offer_answer()],
        )
        self.assertEqual(len(res["offers"]), 0)
        self.assertEqual(res["stats"]["already_applied"], 1)

    def test_batch_dedupe(self):
        p1 = _post("oferta uno " + "a" * 100, ["hr@techco.com"])
        p2 = _post("oferta dos " + "b" * 100, ["hr@techco.com"])
        res = self.run_search(
            scrape_side_effect=[[p1, p2], []],
            filter_side_effect=[_offer_answer(), _offer_answer()],
        )
        self.assertEqual(len(res["offers"]), 1)
        self.assertEqual(res["stats"]["batch_dupes"], 1)


if __name__ == "__main__":
    unittest.main()
