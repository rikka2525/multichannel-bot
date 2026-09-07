import hashlib
import hmac
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import requests

from app import create_app
from config import Settings
from conversation import build_reply
from database import ProcessedMessages
from services.whatsapp_client import DeliveryError, WhatsAppClient


class MVPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = Settings("test-verify", "test-secret", "12345", frozenset({"819000000000"}),
                                 database_path=str(Path(self.temp.name) / "test.db"))
        self.sender = Mock()
        self.client = create_app(self.settings, self.sender).test_client()

    def payload(self, message_id="m1", kind="text", body="こんにちは"):
        return {"object": "whatsapp_business_account", "entry": [{"changes": [{
            "field": "messages", "value": {"metadata": {"phone_number_id": "12345"},
            "messages": [{"id": message_id, "from": "819000000000", "type": kind,
                          "text": {"body": body}}]}}]}]}

    def post(self, payload, client=None):
        raw = json.dumps(payload, ensure_ascii=False).encode()
        signature = "sha256=" + hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()
        return (client or self.client).post("/webhook", data=raw, content_type="application/json",
                                           headers={"X-Hub-Signature-256": signature})

    def test_verification(self):
        r = self.client.get("/webhook", query_string={"hub.mode": "subscribe", "hub.verify_token": "test-verify", "hub.challenge": "123"})
        self.assertEqual((r.status_code, r.text), (200, "123"))

    def test_bad_verification(self):
        self.assertEqual(self.client.get("/webhook?hub.mode=subscribe&hub.verify_token=wrong").status_code, 403)

    def test_missing_challenge(self):
        self.assertEqual(self.client.get("/webhook?hub.mode=subscribe&hub.verify_token=test-verify").status_code, 400)

    def test_unsigned_rejected(self):
        self.assertEqual(self.client.post("/webhook", json=self.payload()).status_code, 403)
        self.sender.send_text.assert_not_called()

    def test_tampered_body_rejected(self):
        self.assertEqual(self.client.post("/webhook", data=b"{}", headers={"X-Hub-Signature-256": "sha256=bad"}).status_code, 403)

    def test_reply_and_duplicate(self):
        self.assertEqual(self.post(self.payload()).status_code, 200)
        self.assertEqual(self.post(self.payload()).status_code, 200)
        self.assertIn("1：お問い合わせ", self.sender.send_text.call_args.args[1])

    def test_dedup_survives_restart(self):
        self.post(self.payload())
        second = create_app(self.settings, self.sender).test_client()
        self.assertEqual(self.post(self.payload(), second).status_code, 200)
        self.assertEqual(self.sender.send_text.call_count, 1)

    def test_no_personal_data_saved(self):
        self.post(self.payload())
        raw = Path(self.settings.database_path).read_bytes()
        self.assertNotIn(b"819000000000", raw)
        self.assertNotIn("こんにちは".encode(), raw)

    def test_status_ignored(self):
        p = self.payload()
        value = p["entry"][0]["changes"][0]["value"]
        value.pop("messages")
        value["statuses"] = [{"status": "delivered"}]
        self.assertEqual(self.post(p).status_code, 200)
        self.sender.send_text.assert_not_called()

    def test_wrong_phone_id_ignored(self):
        p = self.payload()
        p["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = "999"
        self.assertEqual(self.post(p).status_code, 200)
        self.sender.send_text.assert_not_called()

    def test_unknown_sender_ignored(self):
        p = self.payload()
        p["entry"][0]["changes"][0]["value"]["messages"][0]["from"] = "819111111111"
        self.assertEqual(self.post(p).status_code, 200)
        self.sender.send_text.assert_not_called()

    def test_non_text_guidance(self):
        self.assertEqual(self.post(self.payload(kind="image")).status_code, 200)
        self.assertIn("テキスト", self.sender.send_text.call_args.args[1])

    def test_empty_text_guidance(self):
        self.assertIn("テキスト", build_reply("  ").reply)

    def test_inquiry_flow(self):
        self.post(self.payload("i1", body="1"))
        self.post(self.payload("i2", body="料金について知りたい"))
        replies = [call.args[1] for call in self.sender.send_text.call_args_list]
        self.assertIn("お問い合わせ内容", replies[0])
        self.assertIn("受け付けました", replies[1])

    def test_survey_flow_and_storage(self):
        self.post(self.payload("s1", body="2"))
        self.post(self.payload("s2", body="5"))
        self.post(self.payload("s3", body="使いやすかった"))
        with closing(sqlite3.connect(self.settings.database_path)) as db:
            row = db.execute("SELECT rating, comment FROM survey_answers").fetchone()
        self.assertEqual(row, (5, "使いやすかった"))

    def test_invalid_rating_keeps_state(self):
        self.post(self.payload("r1", body="2"))
        self.post(self.payload("r2", body="9"))
        store = ProcessedMessages(self.settings.database_path)
        self.assertEqual(store.state("819000000000"), "survey_rating")
        self.assertIn("1〜5", self.sender.send_text.call_args.args[1])

    def test_reset_clears_draft_and_returns_menu(self):
        self.post(self.payload("x1", body="2"))
        self.post(self.payload("x2", body="4"))
        self.post(self.payload("x3", body="reset"))
        store = ProcessedMessages(self.settings.database_path)
        self.assertEqual(store.state("819000000000"), "menu")
        with closing(sqlite3.connect(self.settings.database_path)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM survey_answers").fetchone()[0], 0)

    def test_state_survives_restart(self):
        self.post(self.payload("p1", body="1"))
        second = create_app(self.settings, self.sender).test_client()
        self.post(self.payload("p2", body="再起動後の問い合わせ",), second)
        self.assertIn("受け付けました", self.sender.send_text.call_args.args[1])

    def test_malformed_payload(self):
        for value in [None, [], {"object": "whatsapp_business_account", "entry": None}]:
            with self.subTest(value=value):
                self.assertEqual(self.post(value).status_code, 400)

    def test_failure_can_retry(self):
        self.sender.send_text.side_effect = DeliveryError("test")
        self.assertEqual(self.post(self.payload()).status_code, 503)
        self.sender.send_text.side_effect = None
        self.assertEqual(self.post(self.payload()).status_code, 200)
        self.assertEqual(self.sender.send_text.call_count, 2)

    def test_live_requires_credentials(self):
        with self.assertRaises(ValueError):
            create_app(replace(self.settings, dry_run=False))

    def test_dry_run_never_posts(self):
        from unittest.mock import patch
        with patch("requests.Session.post") as post:
            client = create_app(self.settings).test_client()
            self.assertEqual(self.post(self.payload(), client).status_code, 200)
            post.assert_not_called()

    def test_health(self):
        self.assertEqual(self.client.get("/health").json, {"status": "ok", "mode": "dry-run"})


class ClientTests(unittest.TestCase):
    def setUp(self):
        settings = Settings("x", "y", "12345", frozenset({"819000000000"}), "fake-token", "v99.0", False)
        self.session = Mock()
        self.response = self.session.post.return_value
        self.response.status_code = 200
        self.response.json.return_value = {"messages": [{"id": "response-id"}]}
        self.client = WhatsAppClient(settings, self.session)

    def test_request_shape(self):
        self.client.send_text("819000000000", "hello")
        args, kwargs = self.session.post.call_args
        self.assertEqual(args[0], "https://graph.facebook.com/v99.0/12345/messages")
        self.assertEqual(kwargs["json"]["text"]["body"], "hello")
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["timeout"], (3, 7))
        self.response.close.assert_called_once()

    def test_http_failure(self):
        for status in (302, 401, 429, 500):
            self.response.status_code = status
            with self.subTest(status=status), self.assertRaises(DeliveryError):
                self.client.send_text("819000000000", "hi")

    def test_timeout_sanitized(self):
        self.session.post.side_effect = requests.Timeout("secret-response-content")
        with self.assertRaises(DeliveryError) as caught:
            self.client.send_text("819000000000", "hi")
        self.assertNotIn("secret-response-content", str(caught.exception))

    def test_malformed_response(self):
        self.response.json.return_value = {"messages": []}
        with self.assertRaises(DeliveryError):
            self.client.send_text("819000000000", "hi")


if __name__ == "__main__":
    unittest.main()
