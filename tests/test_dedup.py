import unittest

from jobhunter.offers import deduplicate_offers_by_title_company


class DeduplicationTests(unittest.TestCase):
    def test_keeps_same_title_for_different_companies(self):
        offers = [
            {"job_title": "Backend Developer", "company": "Acme"},
            {"job_title": "Backend Developer", "company": "Globex"},
        ]

        result = deduplicate_offers_by_title_company(offers)

        self.assertEqual(len(result), 2)

    def test_deduplicates_same_title_same_company(self):
        offers = [
            {"job_title": "Backend Developer", "company": "Acme"},
            {"job_title": "Backend Developer", "company": "Acme"},
        ]

        result = deduplicate_offers_by_title_company(offers)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["company"], "Acme")

    def test_deduplicates_with_normalized_values(self):
        offers = [
            {"job_title": "Backend Developer!!", "company": "ACME Inc."},
            {"job_title": " backend developer ", "company": "acme-inc"},
        ]

        result = deduplicate_offers_by_title_company(offers)

        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
