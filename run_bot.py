"""Run one adapter per process. WhatsApp retains app.py compatibility."""
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv
from config import ROOT
from core.bot import BotCore
from database import ProcessedMessages

ADMIN_CHANNELS = {"mock", "telegram", "discord"}

def required(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Set {name} in .env")
    return value

def users(name):
    result = {x.strip() for x in required(name).split(",") if x.strip()}
    if not result or not all(x.isdecimal() for x in result):
        raise ValueError(f"{name} must contain numeric IDs")
    return result

def admins():
    """Optional ADMIN_USERS: comma-separated "channel:user_id" entries."""
    result = frozenset(x.strip() for x in os.getenv("ADMIN_USERS", "").split(",") if x.strip())
    for entry in result:
        channel, _, user_id = entry.partition(":")
        if channel not in ADMIN_CHANNELS or not user_id.strip():
            raise ValueError("ADMIN_USERS entries must be channel:user_id (mock, telegram, discord)")
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("channel", choices=["mock", "whatsapp", "telegram", "discord"])
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    if args.channel == "whatsapp":
        from app import create_app
        import logging
        logging.getLogger("werkzeug").disabled = True
        create_app().run(host="127.0.0.1", port=8000, debug=False, use_reloader=False)
        return
    path = Path(os.getenv(args.channel.upper() + "_DATABASE_PATH", f"data/{args.channel}.db"))
    core = BotCore(ProcessedMessages(str(path if path.is_absolute() else ROOT / path)),
                   admins=admins(), active_adapters=[args.channel])
    if args.channel == "mock":
        from adapters.mock import MockAdapter
        bot = MockAdapter(core)
        print("Mock: reset → 2 → 5 → comment; /quit to exit")
        while True:
            try:
                text = input("> ")
            except EOFError:
                break
            if text == "/quit":
                break
            print(bot.receive(text))
    elif args.channel == "telegram":
        from adapters.telegram import TelegramAdapter
        TelegramAdapter(core, required("TELEGRAM_BOT_TOKEN"), users("TELEGRAM_ALLOWED_USERS")).run()
    else:
        from adapters.discord import run
        run(core, required("DISCORD_BOT_TOKEN"), users("DISCORD_ALLOWED_USERS"), users("DISCORD_ALLOWED_CHANNELS"))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
