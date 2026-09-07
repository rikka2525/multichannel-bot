"""WhatsApp-specific event parsing and signature validation."""
import hashlib
import hmac
import json
import logging
import sqlite3
from adapters.whatsapp import WhatsAppAdapter

from flask import Blueprint, Response, request

from models import IncomingMessage, ReplySender
from services.whatsapp_client import DeliveryError

logger = logging.getLogger(__name__)


def valid_signature(raw: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), signature.encode())


def parse_messages(payload, phone_number_id: str):
    if not isinstance(payload, dict):
        raise ValueError("Expected object")
    if payload.get("object") != "whatsapp_business_account":
        return []
    result = []
    entries = payload.get("entry", [])
    if not isinstance(entries, list):
        raise ValueError("Invalid entries")
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("changes", []), list):
            raise ValueError("Invalid entry")
        for change in entry.get("changes", []):
            if not isinstance(change, dict):
                raise ValueError("Invalid change")
            if change.get("field") != "messages":
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                raise ValueError("Invalid value")
            metadata = value.get("metadata", {})
            if not isinstance(metadata, dict) or metadata.get("phone_number_id") != phone_number_id:
                continue
            messages = value.get("messages", [])
            if not isinstance(messages, list):
                raise ValueError("Invalid messages")
            for msg in messages:
                if not isinstance(msg, dict) or not all(isinstance(msg.get(k), str) and msg[k] for k in ("id", "from")):
                    raise ValueError("Invalid message")
                text = None
                if msg.get("type") == "text":
                    body = msg.get("text")
                    if not isinstance(body, dict) or not isinstance(body.get("body"), str):
                        raise ValueError("Invalid text")
                    text = body["body"]
                result.append(IncomingMessage(msg["id"], msg["from"], text))
    return result


def create_webhook(settings, repository, sender: ReplySender):
    bp = Blueprint("webhook", __name__)
    adapter = WhatsAppAdapter(settings, repository, sender)

    @bp.get("/webhook")
    def verify():
        token = request.args.get("hub.verify_token", "")
        if (request.args.get("hub.mode") != "subscribe"
                or not hmac.compare_digest(token.encode(), settings.verify_token.encode())):
            return Response("Forbidden", status=403)
        challenge = request.args.get("hub.challenge")
        if challenge is None:
            return Response("Missing challenge", status=400)
        return Response(challenge, mimetype="text/plain")

    @bp.post("/webhook")
    def receive():
        raw = request.get_data()
        if not valid_signature(raw, request.headers.get("X-Hub-Signature-256", ""), settings.app_secret):
            logger.warning("signature_rejected")
            return Response("Forbidden", status=403)
        try:
            messages = parse_messages(json.loads(raw), settings.phone_number_id)
        except (ValueError, UnicodeError):
            return Response("Invalid payload", status=400)
        try:
            for msg in messages:
                adapter.receive(msg)
        except (DeliveryError, sqlite3.Error):
            logger.error("reply_processing_failed")
            return Response("Temporary failure", status=503)
        # Includes delivery-status events: never reply to those.
        return Response("EVENT_RECEIVED", status=200)

    return bp
