# -*- coding: utf-8 -*-
"""Comando dashboard: servidor local de historial y metricas."""
import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from jobhunter.metrics import build_dashboard_data
from jobhunter.storage import load_kb
from jobhunter.ui import console

ASSET = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "dashboard.html",
)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/data"):
            data = build_dashboard_data(load_kb())
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", payload)
        elif self.path in ("/", "/index.html"):
            with open(ASSET, "rb") as f:
                self._send(200, "text/html; charset=utf-8", f.read())
        else:
            self.send_response(404)
            self.end_headers()

    def _send(self, code, ctype, payload):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        pass


def cmd_dashboard(port=4090):
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    except OSError:
        console.print(f"  [red]✗[/red] Puerto {port} ocupado. Prueba: [cyan]jobhunter dashboard --port {port + 1}[/cyan]")
        return
    url = "http://127.0.0.1:" + str(port) + "/"
    console.print(f"  [green]✓[/green] Dashboard en [cyan]{url}[/cyan]  [dim](Ctrl+C para detener)[/dim]")
    threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n  [dim]Dashboard detenido.[/dim]")
    finally:
        server.server_close()
