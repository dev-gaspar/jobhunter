# -*- coding: utf-8 -*-
"""Entry point de JobHunter Desktop: ventana pywebview + puente Bridge.

Uso:
  python -m desktop.app             # desarrollo
  JobHunter.exe                     # congelado (PyInstaller)
  JobHunter.exe --selftest          # smoke test sin abrir ventana
"""
import json
import os
import sys
import tempfile


def resource_path(rel):
    """Ruta a recursos empaquetados (ui/) en dev y en PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def selftest():
    """Verifica imports, rutas de datos y recursos. Exit 0 si todo esta bien."""
    problems = []
    try:
        from jobhunter.constants import BASE_DIR, VERSION  # noqa: F401
        from jobhunter import service  # noqa: F401
        from desktop.api import Bridge  # noqa: F401
        if not os.path.isdir(BASE_DIR):
            problems.append("BASE_DIR no existe: " + BASE_DIR)
    except Exception as e:
        problems.append("import: " + str(e))
    ui_index = resource_path(os.path.join("ui", "index.html"))
    if not os.path.exists(ui_index):
        problems.append("ui/index.html no encontrado: " + ui_index)
    out = os.path.join(tempfile.gettempdir(), "jobhunter_selftest.txt")
    with open(out, "w", encoding="utf-8") as f:
        if problems:
            f.write("FAIL\n" + "\n".join(problems))
        else:
            f.write("OK")
    return 0 if not problems else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())

    import webview
    from desktop.api import Bridge

    window_holder = {}

    def emit(name, payload):
        w = window_holder.get("w")
        if w is None:
            return
        try:
            code = ("window.bus && window.bus._recv(" + json.dumps(name) + "," +
                    json.dumps(payload, ensure_ascii=False, default=str) + ")")
            w.evaluate_js(code)
        except Exception:
            pass

    def file_dialog():
        w = window_holder.get("w")
        if w is None:
            return None
        result = w.create_file_dialog(webview.OPEN_DIALOG,
                                      file_types=("PDF (*.pdf)",))
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else result

    def quit_app():
        w = window_holder.get("w")
        if w is not None:
            try:
                w.destroy()
            except Exception:
                pass

    bridge = Bridge(emit=emit, file_dialog=file_dialog, quit_app=quit_app)
    window = webview.create_window(
        "JobHunter",
        url=resource_path(os.path.join("ui", "index.html")),
        width=1140,
        height=760,
        min_size=(980, 640),
        background_color="#000000",
        js_api=bridge,
    )
    window_holder["w"] = window
    webview.start(debug="--debug" in sys.argv)


if __name__ == "__main__":
    main()
