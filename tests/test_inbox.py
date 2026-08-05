# -*- coding: utf-8 -*-
import unittest
from datetime import datetime

from jobhunter.inbox import imap_date, reconcile

NOW = datetime(2026, 8, 5, 12, 0, 0)


def _app(email, date="2026-08-01T10:00:00", **kw):
    base = {"recruiter_email": email, "sent_to": email, "date": date,
            "job_title": "T", "company": "C", "mode": "run"}
    base.update(kw)
    return base


class ImapDateTests(unittest.TestCase):
    def test_format(self):
        self.assertEqual(imap_date(datetime(2026, 8, 5)), "05-Aug-2026")
        self.assertEqual(imap_date(datetime(2026, 1, 31)), "31-Jan-2026")


class ReconcileTests(unittest.TestCase):
    def test_reply_marks_replied(self):
        app = _app("r@x.com")
        headers = [{"from_email": "r@x.com", "date": datetime(2026, 8, 2, 9, 0), "subject": "Re: CV"}]
        summary = reconcile([app], headers, [], now=NOW)
        self.assertEqual(app["status"], "replied")
        self.assertEqual(app["reply_subject"], "Re: CV")
        self.assertEqual(summary["replied"], 1)

    def test_reply_before_send_does_not_count(self):
        app = _app("r@x.com", date="2026-08-03T10:00:00")
        headers = [{"from_email": "r@x.com", "date": datetime(2026, 8, 2, 9, 0), "subject": "viejo"}]
        reconcile([app], headers, [], now=NOW)
        self.assertEqual(app["status"], "no_reply")

    def test_bounce_detected_in_text(self):
        app = _app("dead@x.com")
        bounce = "Delivery incomplete ... The recipient DEAD@x.com was not found"
        summary = reconcile([app], [], [bounce], now=NOW)
        self.assertEqual(app["status"], "bounced")
        self.assertEqual(summary["bounced"], 1)

    def test_replied_wins_over_bounce(self):
        app = _app("r@x.com")
        headers = [{"from_email": "R@X.com", "date": datetime(2026, 8, 2), "subject": "hola"}]
        reconcile([app], headers, ["fallo a r@x.com"], now=NOW)
        self.assertEqual(app["status"], "replied")

    def test_reply_assigned_to_most_recent_prior_app(self):
        old = _app("r@x.com", date="2026-07-01T10:00:00")
        new = _app("r@x.com", date="2026-08-01T10:00:00")
        headers = [{"from_email": "r@x.com", "date": datetime(2026, 8, 2), "subject": "s"}]
        reconcile([old, new], headers, [], now=NOW)
        self.assertEqual(new["status"], "replied")
        self.assertEqual(old["status"], "no_reply")

    def test_no_reply_sets_checked_at(self):
        app = _app("r@x.com")
        summary = reconcile([app], [], [], now=NOW)
        self.assertEqual(app["status"], "no_reply")
        self.assertEqual(app["status_checked_at"], NOW.isoformat())
        self.assertEqual(summary["no_reply"], 1)

    def test_test_sends_are_skipped(self):
        app = _app("r@x.com", sent_to="yo@gmail.com")
        summary = reconcile([app], [], [], now=NOW)
        self.assertNotIn("status", app)
        self.assertEqual(summary["checked"], 0)


if __name__ == "__main__":
    unittest.main()
