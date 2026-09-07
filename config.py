"""Environment configuration. No credentials are printed or stored in code."""
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    verify_token: str
    app_secret: str
    phone_number_id: str
    allowed_senders: frozenset[str]
    access_token: str = ""
    graph_api_version: str = ""
    dry_run: bool = True
    database_path: str = str(ROOT / "data" / "messages.db")

    def validate(self):
        if not self.verify_token or not self.app_secret:
            raise ValueError("Set VERIFY_TOKEN and META_APP_SECRET locally in .env")
        if not re.fullmatch(r"[0-9]+", self.phone_number_id):
            raise ValueError("WHATSAPP_PHONE_NUMBER_ID must be numeric")
        if not self.allowed_senders or any(
            not re.fullmatch(r"[0-9]{6,15}", x) for x in self.allowed_senders
        ):
            raise ValueError("Set TEST_ALLOWED_SENDERS to international digits without +")
        if not self.dry_run and (
            not self.access_token or not re.fullmatch(r"v[0-9]+\.0", self.graph_api_version)
        ):
            raise ValueError("Live mode requires WHATSAPP_ACCESS_TOKEN and GRAPH_API_VERSION")


def load_settings():
    load_dotenv(ROOT / ".env", override=False)
    mode = os.getenv("DRY_RUN", "true").lower()
    if mode not in {"true", "false"}:
        raise ValueError("DRY_RUN must be true or false")
    path = Path(os.getenv("DATABASE_PATH", "data/messages.db"))
    return Settings(
        verify_token=os.getenv("VERIFY_TOKEN", "").strip(),
        app_secret=os.getenv("META_APP_SECRET", "").strip(),
        phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip(),
        allowed_senders=frozenset(x.strip() for x in os.getenv("TEST_ALLOWED_SENDERS", "").split(",") if x.strip()),
        access_token=os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip(),
        graph_api_version=os.getenv("GRAPH_API_VERSION", "").strip(),
        dry_run=mode == "true",
        database_path=str(path if path.is_absolute() else ROOT / path),
    )
