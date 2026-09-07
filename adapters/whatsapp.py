from core.bot import BotCore

class WhatsAppAdapter:
    def __init__(self, settings, repository, sender):
        self.settings, self.sender = settings, sender
        self.core = BotCore(repository)

    def receive(self, message):
        if message.sender not in self.settings.allowed_senders:
            return None
        return self.core.handle(message, self.sender, channel="whatsapp",
                                mode="dry" if self.settings.dry_run else "live")
