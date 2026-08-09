# -*- coding: utf-8 -*-
"""Smoke tests del console singleton de Rich.

Ui/ es un singleton; lo importante es que el modulo importe limpio en
cualquier plataforma (Windows legacy / no es que), que el console se cree,
y que el helper de VT no reviente ante fallos del sistema.
"""
import os
import sys
import unittest
from unittest.mock import patch

from jobhunter import ui
from jobhunter.ui import console


class ConsoleSingletonTests(unittest.TestCase):
    def test_console_is_rich_console(self):
        from rich.console import Console

        self.assertIsInstance(console, Console)

    def test_console_can_print_simple_markup(self):
        import io

        from rich.console import Console

        fake = io.StringIO()
        c = Console(file=fake, force_terminal=True)
        c.print("  [cyan]test[/cyan]")
        self.assertIn("test", fake.getvalue())


class EnableWindowsVtTests(unittest.TestCase):
    def test_noop_on_non_windows(self):
        with patch("jobhunter.ui.os.name", "posix"):
            self.assertIsNone(ui._enable_windows_vt())

    def test_does_not_raise_when_ctypes_unavailable(self):
        real = sys.modules.get("ctypes")
        sys.modules["ctypes"] = None
        try:
            with patch("jobhunter.ui.os.name", "nt"):
                self.assertIsNone(ui._enable_windows_vt())
        finally:
            if real is not None:
                sys.modules["ctypes"] = real
            else:
                del sys.modules["ctypes"]

    def test_silences_failures_from_kernel32(self):
        import ctypes as _ctypes

        class _BadDll:
            def GetStdHandle(self, _hid):
                raise OSError("no console")

            SetConsoleMode = GetStdHandle

        real_kernel32 = _ctypes.windll.kernel32
        _ctypes.windll.kernel32 = _BadDll()
        try:
            with patch("jobhunter.ui.os.name", "nt"):
                self.assertIsNone(ui._enable_windows_vt())
        finally:
            _ctypes.windll.kernel32 = real_kernel32


if __name__ == "__main__":
    unittest.main()