"""Transport-free orchestration; commit only after successful delivery."""
from threading import Lock
from conversation import build_reply

class BotCore:
    def __init__(self, repository):
        self.repository = repository
        self.lock = Lock()

    def handle(self, message, sender, *, channel, mode="live", scope=None):
        # Preserve legacy WhatsApp database keys. Other channels are namespaced.
        identity = message.sender if channel == "whatsapp" else f"{channel}:{scope or message.sender}:{message.sender}"
        message_id = message.message_id if channel == "whatsapp" else f"{channel}:{message.message_id}"
        with self.lock:
            key = self.repository.key(message_id, mode)
            if self.repository.contains(key):
                return None
            result = build_reply(message.text, self.repository.state(identity))
            sender.send_text(scope or message.sender, result.reply)
            self.repository.apply(key, identity, result)
            return result.reply
