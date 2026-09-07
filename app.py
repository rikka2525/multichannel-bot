import logging

from flask import Flask

from config import load_settings
from database import ProcessedMessages
from services.whatsapp_client import DryRunSender, WhatsAppClient
from webhook import create_webhook


def create_app(settings=None, sender=None):
    settings = settings or load_settings()
    settings.validate()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 256 * 1024
    repository = ProcessedMessages(settings.database_path)
    if sender is None:
        sender = DryRunSender() if settings.dry_run else WhatsAppClient(settings)
    app.register_blueprint(create_webhook(settings, repository, sender))

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "dry-run" if settings.dry_run else "live"}

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Werkzeug access logs include the GET verification token in the query string.
    logging.getLogger("werkzeug").disabled = True
    create_app().run(host="127.0.0.1", port=8000, debug=False, use_reloader=False)
