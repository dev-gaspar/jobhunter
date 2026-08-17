# -*- coding: utf-8 -*-
"""Tests del puente desktop (Bridge) sin webview: estado, busqueda, envio."""
import unittest
from unittest.mock import MagicMock, patch

from desktop.api import Bridge

CFG = {
    "gemini_api_key": "AIzaXYZ123",
    "smtp_email": "yo@gmail.com",
    "smtp_password": "apppassword123456",
    "profile": {"name": "Jose", "portfolio": "", "linkedin": ""},
    "gemini_model": "gemini-2.5-flash",
    "cv_template": "modern",
    "search_queries": ["q1"],
    "job_types_raw": "backend developer",
    "search_languages": "3",
    "user_languages": [{"language": "Espanol", "level": "Nativo"}],
    "work_mode": "4",
    "work_mode_label": "Cualquiera",
    "user_location": "",
    "cv_path": "C:/cv.pdf",
}

OFFER = {
    "job_title": "Backend Dev",
    "company": "TechCo",
    "contact_email": "hr@techco.com",
    "contact_name": "Ana",
    "language": "es",
    "work_mode": "remote",
    "location": "Remote",
    "salary": None,
    "post_url": "https://lnkd.in/x",
    "query": "backend",
    "author_url": None,
    "author_name": None,
}


def make_bridge(cfg=None):
    events = []
    bridge = Bridge(emit=lambda n, p: events.append((n, p)), file_dialog=None, sync=True)
    return bridge, events


class TestState(unittest.TestCase):
    @patch("desktop.api.load_config", return_value={})
    def test_state_unconfigured(self, m_cfg):
        bridge, _ = make_bridge()
        res = bridge.get_state()
        self.assertTrue(res["ok"])
        self.assertFalse(res["data"]["configured"])
        self.assertFalse(res["data"]["onboarding"]["has_key"])

    @patch("desktop.api.service.has_linkedin_session", return_value=True)
    @patch("desktop.api.load_config", return_value=CFG)
    def test_state_configured_masks_secrets(self, m_cfg, m_sess):
        bridge, _ = make_bridge()
        res = bridge.get_state()
        data = res["data"]
        self.assertTrue(data["configured"])
        self.assertEqual(data["profile_name"], "Jose")
        self.assertNotIn("smtp_password", str(data))
        self.assertNotIn("AIzaXYZ123", str(data))
        self.assertTrue(data["gemini_key_masked"].startswith("AIza"))
        self.assertTrue(data["onboarding"]["has_smtp"])


class TestSearch(unittest.TestCase):
    @patch("desktop.api.load_kb", return_value={"runs": [], "applications": [], "rejected_companies": []})
    @patch("desktop.api.load_config", return_value=CFG)
    @patch("desktop.api.service.search_offers")
    def test_search_done_assigns_ids(self, m_search, m_cfg, m_kb):
        m_search.return_value = {"offers": [dict(OFFER)], "stats": {"posts_scraped": 5},
                                 "decisions": [], "error": None}
        bridge, events = make_bridge()
        res = bridge.start_search("24h")
        self.assertTrue(res["ok"])
        done = [p for n, p in events if n == "search_done"]
        self.assertEqual(len(done), 1)
        self.assertEqual(done[0]["offers"][0]["id"], 1)
        self.assertEqual(done[0]["offers"][0]["company"], "TechCo")

    @patch("desktop.api.load_kb", return_value={"runs": [], "applications": [], "rejected_companies": []})
    @patch("desktop.api.load_config", return_value=CFG)
    @patch("desktop.api.service.search_offers")
    def test_search_error_event(self, m_search, m_cfg, m_kb):
        m_search.return_value = {"offers": [], "stats": {}, "decisions": [],
                                 "error": {"kind": "session_expired", "message": "exp"}}
        bridge, events = make_bridge()
        bridge.start_search("24h")
        errs = [p for n, p in events if n == "search_error"]
        self.assertEqual(errs[0]["kind"], "session_expired")


class TestSendFlow(unittest.TestCase):
    def _bridge_with_offer(self):
        bridge, events = make_bridge()
        with patch("desktop.api.load_config", return_value=CFG), \
             patch("desktop.api.load_kb", return_value={"runs": [], "applications": [],
                                                        "rejected_companies": []}), \
             patch("desktop.api.service.search_offers") as m_search:
            m_search.return_value = {"offers": [dict(OFFER)], "stats": {"posts_scraped": 1},
                                     "decisions": [], "error": None}
            bridge.start_search("24h", test_email=None)
        return bridge, events

    @patch("desktop.api.service.prepare_application")
    def test_prepare_emits_preview(self, m_prep):
        m_prep.return_value = {"ok": True, "cv_data": {}, "cv_path": "C:/out/cv.pdf",
                               "subject": "Asunto", "body": "Cuerpo", "error": None}
        bridge, events = self._bridge_with_offer()
        res = bridge.prepare_offer(1)
        self.assertTrue(res["ok"])
        previews = [p for n, p in events if n == "preview_ready"]
        self.assertEqual(previews[0]["subject"], "Asunto")

    @patch("desktop.api.service.send_application")
    @patch("desktop.api.service.check_recipient", return_value=True)
    @patch("desktop.api.service.prepare_application")
    def test_send_ok(self, m_prep, m_mx, m_send):
        m_prep.return_value = {"ok": True, "cv_data": {}, "cv_path": "C:/out/cv.pdf",
                               "subject": "Asunto", "body": "Cuerpo", "error": None}
        m_send.return_value = {"status": "sent", "error": None,
                               "entry": {"company": "TechCo"}}
        bridge, events = self._bridge_with_offer()
        bridge.prepare_offer(1)
        res = bridge.send_offer(1, subject="Editado")
        self.assertTrue(res["ok"])
        sent = [p for n, p in events if n == "send_result"]
        self.assertEqual(sent[0]["status"], "sent")
        # el asunto editado viaja al envio
        self.assertEqual(m_send.call_args.args[3]["subject"], "Editado")

    @patch("desktop.api.service.check_recipient", return_value=False)
    @patch("desktop.api.service.prepare_application")
    def test_send_mx_fail_asks_alt(self, m_prep, m_mx):
        m_prep.return_value = {"ok": True, "cv_data": {}, "cv_path": None,
                               "subject": "A", "body": "B", "error": None}
        bridge, events = self._bridge_with_offer()
        bridge.prepare_offer(1)
        res = bridge.send_offer(1)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "mx")

    @patch("desktop.api.service.record_run")
    @patch("desktop.api.service.write_run_log", return_value="log.json")
    def test_finish_run_summary(self, m_log, m_rec):
        bridge, events = self._bridge_with_offer()
        bridge.skip_offer(1)
        res = bridge.finish_run()
        self.assertTrue(res["ok"])
        self.assertEqual(res["data"]["skipped"], 1)
        m_rec.assert_called_once()


class TestHistory(unittest.TestCase):
    @patch("desktop.api.load_kb")
    def test_history_sorted_and_filtered(self, m_kb):
        m_kb.return_value = {"applications": [
            {"date": "2026-08-01T10:00:00", "company": "A", "job_title": "x",
             "sent_to": "a@a.com", "mode": "run"},
            {"date": "2026-08-10T10:00:00", "company": "B", "job_title": "y",
             "sent_to": "b@b.com", "mode": "test"},
        ]}
        bridge, _ = make_bridge()
        res = bridge.get_history()
        self.assertEqual(res["data"][0]["company"], "B")
        res2 = bridge.get_history(company="a")
        self.assertEqual(len(res2["data"]), 1)


class TestBusy(unittest.TestCase):
    @patch("desktop.api.load_kb", return_value={"runs": [], "applications": [], "rejected_companies": []})
    @patch("desktop.api.load_config", return_value=CFG)
    @patch("desktop.api.service.search_offers")
    def test_busy_rejects_concurrent(self, m_search, m_cfg, m_kb):
        bridge, events = make_bridge()

        def slow_search(*a, **k):
            # simula reentrada durante la busqueda
            inner = bridge.start_search("24h")
            self.assertFalse(inner["ok"])
            return {"offers": [], "stats": {}, "decisions": [],
                    "error": {"kind": "no_posts", "message": "x"}}

        m_search.side_effect = slow_search
        bridge.start_search("24h")


if __name__ == "__main__":
    unittest.main()
