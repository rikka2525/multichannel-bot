import logging

import requests

logger = logging.getLogger(__name__)


from adapters.base import DeliveryError


class DryRunSender:
    def send_text(self, recipient: str, text: str):
        logger.info("dry_run_reply_simulated")


class WhatsAppClient:
    def __init__(self, settings, session=None):
        self.token = settings.access_token
        self.url = f"https://graph.facebook.com/{settings.graph_api_version}/{settings.phone_number_id}/messages"
        self.session = session or requests.Session()

    def send_text(self, recipient: str, text: str):
        try:
            response = self.session.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}"},
                json={"messaging_product": "whatsapp", "to": recipient,
                      "type": "text", "text": {"body": text, "preview_url": False}},
                timeout=(3, 7), allow_redirects=False,
            )
        except requests.RequestException:
            raise DeliveryError("WhatsApp request failed") from None
        try:
            if not 200 <= response.status_code < 300:
                raise DeliveryError(f"WhatsApp HTTP {response.status_code}")
            try:
                data = response.json()
            except ValueError:
                raise DeliveryError("Invalid WhatsApp response") from None
            if not isinstance(data, dict) or not isinstance(data.get("messages"), list) or not any(
                isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
                for item in data["messages"]
            ):
                raise DeliveryError("WhatsApp response missing message ID")
        finally:
            response.close()
