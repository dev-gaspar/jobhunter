# -*- coding: utf-8 -*-
"""Tests para helpers del setup wizard. El cmd_setup completo es interactivo
y se valida con smoke test manual; aqui cubrimos las piezas puras."""
import unittest
from unittest.mock import patch

from jobhunter.cli.setup import _ask, _ask_secret, _mask_secret


class MaskSecretTests(unittest.TestCase):
    def test_short_value_all_hidden(self):
        self.assertEqual(_mask_secret("abc"), "***")
        self.assertEqual(_mask_secret("abcd"), "***")

    def test_long_value_shows_first_four(self):
        self.assertEqual(_mask_secret("AIzaKEY123"), "AIza***")
        self.assertEqual(_mask_secret("sk-12345678"), "sk-1***")

    def test_empty_returns_empty(self):
        self.assertEqual(_mask_secret(""), "")
        self.assertEqual(_mask_secret(None), "")


class AskTests(unittest.TestCase):
    @patch("jobhunter.cli.setup.Prompt.ask")
    def test_returns_stripped_value(self, mock_ask):
        mock_ask.return_value = '  "hello"  '
        self.assertEqual(_ask("label"), "hello")

    @patch("jobhunter.cli.setup.Prompt.ask")
    def test_back_returns_none(self, mock_ask):
        mock_ask.return_value = "<"
        self.assertIsNone(_ask("label"))

    @patch("jobhunter.cli.setup.Prompt.ask")
    def test_back_with_quotes_still_navigates(self, mock_ask):
        mock_ask.return_value = '"<"'
        self.assertIsNone(_ask("label"))


class AskSecretTests(unittest.TestCase):
    @patch("jobhunter.cli.setup.Prompt.ask")
    def test_with_current_shows_masked_inline(self, mock_ask):
        mock_ask.return_value = "newsecret"
        result = _ask_secret("  Clave API", "AIzaOLDKEY")
        self.assertEqual(result, "newsecret")
        label = mock_ask.call_args.args[0]
        self.assertIn("AIza***", label)

    @patch("jobhunter.cli.setup.Prompt.ask")
    def test_enter_with_current_keeps_value(self, mock_ask):
        # Prompt returns the default when Enter pressed
        mock_ask.return_value = "AIzaOLDKEY"
        result = _ask_secret("  Clave", "AIzaOLDKEY")
        self.assertEqual(result, "AIzaOLDKEY")

    @patch("jobhunter.cli.setup.Prompt.ask")
    def test_back_returns_none(self, mock_ask):
        mock_ask.return_value = "<"
        self.assertIsNone(_ask_secret("  Clave", "old"))

    @patch("jobhunter.cli.setup.Prompt.ask")
    def test_without_current_no_label_decoration(self, mock_ask):
        mock_ask.return_value = "new"
        _ask_secret("  Clave", "")
        label = mock_ask.call_args.args[0]
        self.assertNotIn("***", label)


if __name__ == "__main__":
    unittest.main()
