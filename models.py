from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    sender: str
    text: str | None


class ReplySender(Protocol):
    def send_text(self, recipient: str, text: str) -> None: ...
