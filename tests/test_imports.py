# -*- coding: utf-8 -*-
"""Smoke tests de imports: atrapa NameError por import faltante en modulos.

El refactor monolito -> paquete movio codigo y algunos imports de stdlib
se perdieron (ej. shutil, random). Con py_compile pasa la sintaxis pero
el NameError solo explota en runtime. Estos tests compilan los modulos
y hacen import real — cualquier nombre indefinido se detecta aqui."""
import compileall
import importlib
import io
import os
import unittest


PKG_ROOT = os.path.join(os.path.dirname(__file__), "..", "jobhunter")


def _walk_modules(pkg_root, prefix="jobhunter"):
    """Itera recursivamente los modulos .py del paquete (ignora __pycache__)."""
    for entry in os.listdir(pkg_root):
        if entry.startswith("__pycache__") or entry.startswith("."):
            continue
        full = os.path.join(pkg_root, entry)
        if os.path.isdir(full):
            sub_prefix = f"{prefix}.{entry}"
            yield sub_prefix
            yield from _walk_modules(full, sub_prefix)
        elif entry.endswith(".py") and entry != "__init__.py":
            yield f"{prefix}.{entry[:-3]}"


class ImportsSmokeTests(unittest.TestCase):
    def test_all_modules_import_cleanly(self):
        """Cada modulo del paquete se importa sin NameError ni ImportError."""
        failed = []
        for mod_name in _walk_modules(PKG_ROOT):
            try:
                importlib.import_module(mod_name)
            except Exception as e:
                failed.append(f"{mod_name}: {type(e).__name__}: {e}")
        self.assertEqual(failed, [], "Modulos que fallan al importar:\n" + "\n".join(failed))

    def test_compileall_pkg(self):
        """compileall del paquete sin errores (syntax check amplio)."""
        out = io.StringIO()
        ok = compileall.compile_dir(PKG_ROOT, quiet=1)
        self.assertTrue(ok, "compileall reporto errores")


if __name__ == "__main__":
    unittest.main()
