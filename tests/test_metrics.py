# -*- coding: utf-8 -*-
import unittest
from datetime import datetime

from jobhunter.metrics import app_status, build_dashboard_data

NOW = datetime(2026, 8, 5, 12, 0, 0)


def _kb():
    return {
        "runs": [
            {"date": "2026-08-01T10:00:00", "mode": "run", "posts": 100, "offers": 5, "sent": 3},
        ],
        "applications": [
            {"date": "2026-08-01T10:00:00", "job_title": "A", "company": "C1",
             "recruiter_email": "r1@x.com", "sent_to": "r1@x.com", "mode": "run",
             "status": "replied", "reply_date": "2026-08-02T09:00:00"},
            {"date": "2026-08-01T11:00:00", "job_title": "B", "company": "C2",
             "recruiter_email": "r2@x.com", "sent_to": "r2@x.com", "mode": "run",
             "status": "bounced"},
            {"date": "2026-08-02T10:00:00", "job_title": "C", "company": "C3",
             "recruiter_email": "r3@x.com", "sent_to": "r3@x.com", "mode": "run",
             "status": "no_reply"},
            {"date": "2026-08-03T10:00:00", "job_title": "D", "company": "C4",
             "recruiter_email": "r4@x.com", "sent_to": "r4@x.com", "mode": "run"},
            {"date": "2026-08-03T11:00:00", "job_title": "E", "company": "C5",
             "recruiter_email": "r5@x.com", "sent_to": "yo@gmail.com", "mode": "test"},
        ],
    }


class AppStatusTests(unittest.TestCase):
    def test_test_send_detected_by_recipient_mismatch(self):
        self.assertEqual(app_status({"recruiter_email": "a@b.com", "sent_to": "me@x.com"}), "test")

    def test_defaults_to_unknown(self):
        self.assertEqual(app_status({"recruiter_email": "a@b.com", "sent_to": "a@b.com"}), "unknown")

    def test_persisted_status_wins(self):
        self.assertEqual(app_status({"recruiter_email": "a@b.com", "sent_to": "a@b.com", "status": "replied"}), "replied")


class BuildDashboardDataTests(unittest.TestCase):
    def test_totals_exclude_test_sends(self):
        d = build_dashboard_data(_kb(), now=NOW)
        self.assertEqual(d["totals"], {"sent": 4, "replied": 1, "bounced": 1, "no_reply": 1, "unknown": 1})

    def test_rates(self):
        d = build_dashboard_data(_kb(), now=NOW)
        self.assertEqual(d["reply_rate"], 33.3)   # 1 respondida / 3 entregadas (4 enviadas - 1 rebote)
        self.assertEqual(d["bounce_rate"], 25.0)  # 1 / 4

    def test_weeks_are_12_and_count_sends(self):
        d = build_dashboard_data(_kb(), now=NOW)
        self.assertEqual(len(d["weeks"]), 12)
        this_week = [w for w in d["weeks"] if w["week"] == "2026-W32"]
        self.assertEqual(this_week[0]["sent"], 1)  # solo D (3-ago, ISO W32); E es test y se excluye
        prev_week = [w for w in d["weeks"] if w["week"] == "2026-W31"]
        self.assertEqual(prev_week[0]["sent"], 3)  # A y B (1-ago) + C (2-ago, domingo, aun W31)

    def test_applications_newest_first_with_days(self):
        d = build_dashboard_data(_kb(), now=NOW)
        self.assertEqual(len(d["applications"]), 4)
        self.assertEqual(d["applications"][0]["job_title"], "D")
        self.assertEqual(d["applications"][0]["days_since_sent"], 2)
        self.assertEqual(d["applications"][0]["status"], "unknown")

    def test_runs_passthrough(self):
        d = build_dashboard_data(_kb(), now=NOW)
        self.assertEqual(d["runs"][0]["posts"], 100)

    def test_empty_kb(self):
        d = build_dashboard_data({"runs": [], "applications": []}, now=NOW)
        self.assertEqual(d["totals"]["sent"], 0)
        self.assertEqual(d["reply_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
