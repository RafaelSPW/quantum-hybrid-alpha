"""
entrypoint.py — Wrapper para Cloud Run.
Cloud Run exige un proceso escuchando en PORT.
Levanta un health check HTTP en background y luego corre el procesador.
"""
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from main_processor import main


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *args):
        pass


def _start_health_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), _HealthHandler).serve_forever()


if __name__ == "__main__":
    t = threading.Thread(target=_start_health_server, daemon=True)
    t.start()
    print(f"[HEALTH] Servidor HTTP en puerto {os.environ.get('PORT', 8080)}")
    main()
