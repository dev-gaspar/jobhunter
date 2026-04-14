import unittest
from datetime import datetime, timedelta

from jobhunter.offers import extract_emails, was_already_applied


class UtilsTests(unittest.TestCase):
    def test_extract_emails_returns_unique_values(self):
        text = "Contacta a a@test.com o a@test.com y b@test.org"
        emails = extract_emails(text)
        self.assertEqual(set(emails), {"a@test.com", "b@test.org"})

    def test_was_already_applied_true_within_cooldown(self):
        applications = [
            {
                "company": "Acme",
                "job_title": "Backend Developer",
                "date": (datetime.now() - timedelta(days=5)).isoformat(),
            }
        ]
        self.assertTrue(
            was_already_applied(applications, "ACME", "backend developer", cooldown_days=30)
        )

    def test_was_already_applied_false_outside_cooldown(self):
        applications = [
            {
                "company": "Acme",
                "job_title": "Backend Developer",
                "date": (datetime.now() - timedelta(days=45)).isoformat(),
            }
        ]
        self.assertFalse(
            was_already_applied(applications, "Acme", "Backend Developer", cooldown_days=30)
        )


if __name__ == "__main__":
    unittest.main()
