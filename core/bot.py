"""Transport-free orchestration; commit only after successful delivery."""
import logging
from threading import Lock
from conversation import ConversationResult, build_reply
from status import FAILED, build_status

class BotCore:
    def __init__(self, repository, admins=frozenset(), active_adapters=()):
        # admins: "channel:user_id" entries allowed to run "status".
        self.repository = repository
        self.admins = frozenset(admins)
        self.active_adapters = (active_adapters,) if isinstance(active_adapters, str) else tuple(active_adapters)
        self.lock = Lock()

    def handle(self, message, sender, *, channel, mode="live", scope=None):
        # Preserve legacy WhatsApp database keys. Other channels are namespaced.
        identity = message.sender if channel == "whatsapp" else f"{channel}:{scope or message.sender}:{message.sender}"
        message_id = message.message_id if channel == "whatsapp" else f"{channel}:{message.message_id}"
        is_status = self.is_status_request(message, channel)
        with self.lock:
            key = self.repository.key(message_id, mode)
            try:
                if self.repository.contains(key):
                    return None
                state = self.repository.state(identity)
            except Exception as error:
                if not is_status:
                    raise
                # DB unusable: still answer admin status, without dedup/apply (nothing can be persisted).
                logging.error("Status request handled without DB (%s)", type(error).__name__)
                reply = self.status_text(db_unavailable=True)
                sender.send_text(scope or message.sender, reply)
                return reply
            if is_status:
                result = ConversationResult(self.status_text(), state)
            else:
                result = build_reply(message.text, state)
            sender.send_text(scope or message.sender, result.reply)
            self.repository.apply(key, identity, result)
            return result.reply

    def is_status_request(self, message, channel):
        # Non-admins fall through to normal handling so the command is not revealed.
        return (bool(message.sender) and isinstance(message.text, str) and message.text.strip().lower() in {"status", "/status"}
                and f"{channel}:{message.sender}" in self.admins)

    def status_text(self, db_unavailable=False):
        try:
            return build_status(self.repository, self.active_adapters, db_unavailable=db_unavailable)
        except Exception:
            return "[status]\n" + FAILED
