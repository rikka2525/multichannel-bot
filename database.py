"""SQLite persistence using hashed sender and message identifiers."""
import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path


class ProcessedMessages:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS processed (key TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            db.execute("CREATE TABLE IF NOT EXISTS conversations (sender_key TEXT PRIMARY KEY, state TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS survey_answers (sender_key TEXT PRIMARY KEY, rating INTEGER, comment TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    @staticmethod
    def key(message_id: str, mode: str):
        return hashlib.sha256(f"{mode}:{message_id}".encode()).hexdigest()

    def contains(self, key: str) -> bool:
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute("SELECT 1 FROM processed WHERE key = ?", (key,)).fetchone() is not None

    @staticmethod
    def sender_key(sender: str):
        return hashlib.sha256(("sender:" + sender).encode()).hexdigest()

    def state(self, sender: str) -> str:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT state FROM conversations WHERE sender_key = ?", (self.sender_key(sender),)).fetchone()
            return row[0] if row else "menu"

    def apply(self, key: str, sender: str, result):
        sender_key = self.sender_key(sender)
        with closing(sqlite3.connect(self.path)) as db, db:
            if result.reset:
                db.execute("DELETE FROM survey_answers WHERE sender_key = ?", (sender_key,))
            if result.rating is not None:
                db.execute("INSERT INTO survey_answers(sender_key, rating) VALUES (?, ?) ON CONFLICT(sender_key) DO UPDATE SET rating=excluded.rating, comment=NULL, updated_at=CURRENT_TIMESTAMP", (sender_key, result.rating))
            if result.comment is not None:
                db.execute("UPDATE survey_answers SET comment = ?, updated_at=CURRENT_TIMESTAMP WHERE sender_key = ?", (result.comment, sender_key))
            db.execute("INSERT INTO conversations(sender_key, state) VALUES (?, ?) ON CONFLICT(sender_key) DO UPDATE SET state=excluded.state", (sender_key, result.next_state))
            db.execute("INSERT OR IGNORE INTO processed (key) VALUES (?)", (key,))

    def check(self) -> bool:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("PRAGMA quick_check").fetchone()
            return row == ("ok",)

    def mark(self, key: str):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR IGNORE INTO processed (key) VALUES (?)", (key,))
