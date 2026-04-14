# -*- coding: utf-8 -*-
"""Tests del pipeline. Dada la complejidad de cmd_run (3 fases, interactivo,
Playwright), cubrimos el guard de configuracion y de sesion. La orquestacion
real se valida via smoke tests e2e."""
import os
import tempfile
import unittest
from unittest.mock import patch

from jobhunter.pipeline import cmd_run


class CmdRunGuardsTests(unittest.TestCase):
    @patch("jobhunter.pipeline.console")
    @patch("jobhunter.pipeline.is_configured", return_value=False)
    def test_aborts_when_not_configured(self, _cfg, mock_console):
        cmd_run()
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("Falta configuracion", printed)

    @patch("jobhunter.pipeline.console")
    @patch("jobhunter.pipeline.os.path.exists", return_value=False)
    @patch("jobhunter.pipeline.is_configured", return_value=True)
    @patch("jobhunter.pipeline.load_config", return_value={"profile": {"name": "x"}})
    @patch("jobhunter.pipeline.load_kb", return_value={"runs": [], "applications": []})
    def test_aborts_without_session(self, _kb, _cfg, _ic, _exists, mock_console):
        cmd_run()
        printed = " ".join(str(c.args[0]) if c.args else "" for c in mock_console.print.call_args_list)
        self.assertIn("Sin sesion", printed)


if __name__ == "__main__":
    unittest.main()
