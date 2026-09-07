from models import IncomingMessage, ReplySender

class DeliveryError(RuntimeError):
    """Public error containing no transport credentials."""
