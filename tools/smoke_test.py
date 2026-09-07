"""Real loopback HTTP smoke test; no Meta account, .env, or external send needed."""
import hashlib
import hmac
import json
import sys
import tempfile
import threading
from pathlib import Path

import requests
from werkzeug.serving import WSGIRequestHandler, make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from config import Settings


class QuietHandler(WSGIRequestHandler):
    def log(self, *args, **kwargs):
        pass


def main():
    with tempfile.TemporaryDirectory() as directory:
        settings = Settings("local-verify-only", "local-secret-only", "12345",
                            frozenset({"819000000000"}), database_path=str(Path(directory) / "test.db"))
        server = make_server("127.0.0.1", 0, create_app(settings), request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        session = requests.Session()
        session.trust_env = False  # Never route dummy verification values via a system proxy.
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            health = session.get(base + "/health", timeout=3)
            assert health.json() == {"status": "ok", "mode": "dry-run"}
            verify = session.get(base + "/webhook", params={"hub.mode": "subscribe", "hub.verify_token": settings.verify_token, "hub.challenge": "local-check"}, timeout=3)
            assert verify.status_code == 200 and verify.text == "local-check"
            payload = {"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages", "value": {
                "metadata": {"phone_number_id": "12345"}, "messages": [{"id": "local-message", "from": "819000000000", "type": "text", "text": {"body": "test"}}]}}]}]}
            raw = json.dumps(payload).encode()
            signature = "sha256=" + hmac.new(settings.app_secret.encode(), raw, hashlib.sha256).hexdigest()
            reply = session.post(base + "/webhook", data=raw, headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature}, timeout=3)
            assert reply.status_code == 200
            rejected = session.post(base + "/webhook", json=payload, timeout=3)
            assert rejected.status_code == 403
            print("PASS: local HTTP health, verification, signed webhook, unsigned rejection")
            print("Mode: dry-run. No messages sent to WhatsApp. Temporary DB removed on exit.")
        finally:
            session.close()
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()


if __name__ == "__main__":
    main()
