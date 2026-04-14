import unittest
from unittest.mock import patch

from jobhunter.banner import get_banner
from jobhunter.constants import VERSION


class BannerTests(unittest.TestCase):
    @patch("jobhunter.banner.shutil.get_terminal_size")
    def test_large_banner_when_wide(self, mock_size):
        mock_size.return_value = type("T", (), {"columns": 120})
        b = get_banner()
        self.assertIn("Busqueda de empleo", b)
        self.assertIn(VERSION, b)

    @patch("jobhunter.banner.shutil.get_terminal_size")
    def test_small_banner_when_narrow(self, mock_size):
        mock_size.return_value = type("T", (), {"columns": 60})
        b = get_banner()
        self.assertNotIn("Busqueda de empleo", b)
        self.assertIn(VERSION, b)


class ConstantsTests(unittest.TestCase):
    def test_time_filters_contains_expected_keys(self):
        from jobhunter.constants import TIME_FILTERS
        self.assertEqual(TIME_FILTERS["24h"], "past-24h")
        self.assertEqual(TIME_FILTERS["week"], "past-week")
        self.assertEqual(TIME_FILTERS["month"], "past-month")

    def test_base_dir_points_to_project_root(self):
        from jobhunter.constants import BASE_DIR
        import os
        self.assertTrue(os.path.isfile(os.path.join(BASE_DIR, "job.py")))


if __name__ == "__main__":
    unittest.main()
