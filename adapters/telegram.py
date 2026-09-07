import requests
from adapters.base import DeliveryError
from models import IncomingMessage

class TelegramAdapter:
    def __init__(self, core, token, allowed_users, session=None):
        self.core, self.token = core, token
        self.allowed_users = allowed_users
        self.session = session or requests.Session()

    def api(self, method, payload):
        try:
            with self.session.post(f"https://api.telegram.org/bot{self.token}/{method}",
                    json=payload, timeout=(3, 40), allow_redirects=False) as response:
                if response.status_code != 200:
                    raise DeliveryError("Telegram HTTP failure")
                data = response.json()
                if not isinstance(data, dict) or data.get("ok") is not True:
                    raise DeliveryError("Telegram API failure")
                return data.get("result")
        except (requests.RequestException, ValueError):
            raise DeliveryError("Telegram request failed") from None

    def send_text(self, recipient, text):
        result = self.api("sendMessage", {"chat_id": recipient, "text": text})
        if not isinstance(result, dict) or "message_id" not in result:
            raise DeliveryError("Telegram response missing message ID")

    def receive(self, update):
        msg = update.get("message", {})
        user = msg.get("from", {})
        chat = msg.get("chat", {})
        # Private chats only: avoids exposing questionnaire answers in groups.
        if chat.get("type") != "private" or user.get("is_bot") or str(user.get("id")) not in self.allowed_users:
            return None
        text = msg.get("text")
        if text == "/start":
            text = "reset"
        return self.core.handle(IncomingMessage(str(update["update_id"]), str(user["id"]), text),
                                self, channel="telegram", scope=str(chat["id"]))

    def run(self):
        offset = None
        while True:
            updates = self.api("getUpdates", {"offset": offset, "timeout": 30, "allowed_updates": ["message"]})
            if not isinstance(updates, list):
                raise DeliveryError("Invalid Telegram updates")
            for update in updates:
                self.receive(update)
                offset = update["update_id"] + 1
