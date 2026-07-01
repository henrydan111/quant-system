"""Silent localhost HTTP server for the dashboard.

Serves the project root on http://127.0.0.1:8799 so the dashboard's in-page
markdown viewer (which uses fetch) works. Runs safely under ``pythonw.exe``
(no console): the stock ``http.server`` writes request logs to stderr, which
does not exist under pythonw and throws on every request — so this handler
silences logging entirely. Bound to 127.0.0.1 only (not exposed on the LAN);
http.server sends no CORS headers, so other origins cannot read the files.

Used by the at-logon ``QuantDashboardServe`` scheduled task. Stdlib only — no
venv packages needed.
"""
import http.server
import socketserver
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[2])  # project root (E:\量化系统)
HOST, PORT = "127.0.0.1", 8799


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, *args):  # pythonw has no stderr — never write there
        pass


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((HOST, PORT), Handler) as httpd:
        httpd.serve_forever()
