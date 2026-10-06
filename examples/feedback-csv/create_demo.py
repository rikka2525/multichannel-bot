"""Create an entirely fictional DB. No network, credentials, or Bot startup.

Run from this folder: python create_demo.py
Refuses to overwrite an existing DB. Schema matches upstream database.py.
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
db_path = ROOT / "fictional-feedback.db"
rows = json.loads((ROOT / "fictional-input.json").read_text(encoding="utf-8"))
# Exclusive reservation prevents accidentally opening an existing DB.
with db_path.open("xb"):
    pass
with sqlite3.connect(db_path) as db:
    db.execute("CREATE TABLE survey_answers (sender_key TEXT PRIMARY KEY, rating INTEGER, comment TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    db.executemany(
        "INSERT INTO survey_answers VALUES (?, ?, ?, ?)",
        [(f"fictional-{i:03d}", r["rating"], r["comment"], r["updated_at"]) for i, r in enumerate(rows, 1)],
    )
print(f"Created fictional DB with {len(rows)} rows: {db_path.name}")
