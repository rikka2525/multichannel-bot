from uuid import uuid4
from models import IncomingMessage

class MockAdapter:
    def __init__(self, core):
        self.core = core
        self.replies = []

    def send_text(self, recipient, text):
        self.replies.append((recipient, text))

    def receive(self, text, user="local", message_id=None):
        return self.core.handle(IncomingMessage(message_id or uuid4().hex, user, text),
                                self, channel="mock", mode="dry")
