"""Tests for tools/export_feedback.py (Issue #14: safe CSV export of survey answers)."""
import contextlib
import csv
import hashlib
import importlib.util
import io
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from database import ProcessedMessages

REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("export_feedback", REPO_ROOT / "tools" / "export_feedback.py")
ef = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ef)

SECRET = "SECRET-comment-トークン-xyz123"
BOM = b"\xef\xbb\xbf"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def master(path):
    with closing(sqlite3.connect(path)) as db:
        return db.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall()


class ExportFeedbackTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        self.db = self.tmp / "test.db"
        ProcessedMessages(str(self.db))

    # helpers -------------------------------------------------------------
    def insert(self, sender, rating, comment, updated_at, db=None):
        with closing(sqlite3.connect(db or self.db)) as conn, conn:
            conn.execute("INSERT INTO survey_answers(sender_key, rating, comment, updated_at) VALUES (?, ?, ?, ?)",
                         (ProcessedMessages.sender_key(sender), rating, comment, updated_at))

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ef.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def read_csv(self, path):
        with open(path, encoding="utf-8-sig", newline="") as handle:
            return list(csv.reader(handle))

    def assert_error(self, code, out, err, prefix):
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("Error:"), err)
        self.assertTrue(err.startswith(prefix), err)
        self.assertNotIn("Traceback", err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)

    def leftover_temp(self, directory):
        return [p for p in Path(directory).iterdir() if p.name.startswith(".feedback-") and p.name.endswith(".tmp")]

    # R1 / R2 --------------------------------------------------------------
    def test_multiple_rows_header_order_and_count(self):
        self.insert("telegram:1:1", 5, "late", "2026-01-03 00:00:00")
        self.insert("telegram:1:2", 3, "early", "2026-01-01 00:00:00")
        self.insert("discord:9:3", 4, "tie-a", "2026-01-02 00:00:00")
        self.insert("discord:9:4", 1, "tie-b", "2026-01-02 00:00:00")
        out = self.tmp / "out.csv"
        self.assertEqual(ef.export_feedback(self.db, out), 4)
        rows = self.read_csv(out)
        self.assertEqual(rows[0], ["rating", "comment", "updated_at"])
        self.assertEqual(rows[1:], [
            ["3", "early", "2026-01-01 00:00:00"],
            ["4", "tie-a", "2026-01-02 00:00:00"],
            ["1", "tie-b", "2026-01-02 00:00:00"],
            ["5", "late", "2026-01-03 00:00:00"],
        ])

    def test_header_line_exact_bytes(self):
        out = self.tmp / "out.csv"
        ef.export_feedback(self.db, out)
        self.assertEqual(out.read_bytes(), BOM + b"rating,comment,updated_at\r\n")

    def test_main_success_stdout_one_line(self):
        self.insert("telegram:1:1", 5, "ok", "2026-01-01")
        self.insert("telegram:1:2", 4, "ok2", "2026-01-02")
        out = self.tmp / "out.csv"
        code, stdout, stderr = self.run_main("--db", str(self.db), "--output", str(out))
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, f"Exported 2 rows to {out}\n")
        self.assertEqual(len(self.read_csv(out)), 3)

    # R3 -------------------------------------------------------------------
    def test_sender_key_not_exported(self):
        senders = ["telegram:1:1", "discord:22:33"]
        for i, s in enumerate(senders):
            self.insert(s, 5, f"c{i}", f"2026-01-0{i + 1}")
        out = self.tmp / "out.csv"
        ef.export_feedback(self.db, out)
        data = out.read_bytes()
        self.assertNotIn(b"sender_key", data)
        for s in senders:
            self.assertNotIn(ProcessedMessages.sender_key(s).encode(), data)
            self.assertNotIn(s.encode(), data)
        self.assertTrue(all(len(r) == 3 for r in self.read_csv(out)))

    # R4 -------------------------------------------------------------------
    def test_db_unchanged_and_no_journal_files(self):
        self.insert("telegram:1:1", 5, "x", "2026-01-01")
        before_hash, before_files = sha256(self.db), sorted(p.name for p in self.tmp.iterdir())
        out_dir = self.tmp / "o"
        ef.export_feedback(self.db, out_dir / "out.csv")
        self.assertEqual(sha256(self.db), before_hash)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), sorted(before_files + ["o"]))
        for suffix in ("-journal", "-wal", "-shm"):
            self.assertFalse(Path(str(self.db) + suffix).exists(), suffix)

    def test_missing_db_not_created(self):
        missing = self.tmp / "nope" / "missing.db"
        out = self.tmp / "outdir" / "out.csv"
        code, stdout, stderr = self.run_main("--db", str(missing), "--output", str(out))
        self.assert_error(code, stdout, stderr, "Error: database file not found")
        self.assertFalse(missing.exists())
        self.assertFalse(missing.parent.exists())
        self.assertFalse(out.parent.exists())

    def test_db_without_table_not_modified(self):
        db = self.tmp / "other.db"
        with closing(sqlite3.connect(db)) as conn, conn:
            conn.execute("CREATE TABLE other (x TEXT)")
            conn.execute("INSERT INTO other VALUES ('v')")
        before_master, before_hash = master(db), sha256(db)
        code, stdout, stderr = self.run_main("--db", str(db), "--output", str(self.tmp / "o" / "out.csv"))
        self.assert_error(code, stdout, stderr, "Error: survey_answers table not found")
        self.assertEqual(master(db), before_master)
        self.assertEqual(sha256(db), before_hash)
        self.assertFalse((self.tmp / "o").exists())

    # R5 -------------------------------------------------------------------
    def test_zero_rows_header_only(self):
        out = self.tmp / "out.csv"
        code, stdout, _ = self.run_main("--db", str(self.db), "--output", str(out))
        self.assertEqual(code, 0)
        self.assertEqual(stdout, f"Exported 0 rows to {out}\n")
        self.assertEqual(self.read_csv(out), [["rating", "comment", "updated_at"]])

    # R6 -------------------------------------------------------------------
    def test_escaping_round_trip(self):
        comments = ["日本語のコメント", "a,b,c", 'say "hi"', "line1\nline2", "crlf1\r\ncrlf2",
                    'mix, "q"\n改行', "trailing space "]
        for i, c in enumerate(comments):
            self.insert(f"telegram:1:{i}", 5, c, f"2026-01-{i + 10}")
        out = self.tmp / "out.csv"
        self.assertEqual(ef.export_feedback(self.db, out), len(comments))
        self.assertTrue(out.read_bytes().startswith(BOM))
        self.assertFalse(out.read_bytes().startswith(BOM + BOM))
        self.assertEqual([r[1] for r in self.read_csv(out)[1:]], comments)

    def test_null_comment_and_null_rating(self):
        self.insert("telegram:1:1", None, None, "2026-01-01")
        out = self.tmp / "out.csv"
        self.assertEqual(ef.export_feedback(self.db, out), 1)
        self.assertEqual(self.read_csv(out)[1], ["", "", "2026-01-01"])

    # R7 -------------------------------------------------------------------
    def test_formula_prefixes_neutralized(self):
        prefixes = ["=", "+", "-", "@", "\t", "\r", "\n", "＝", "＋", "－", "＠"]
        for p in prefixes:
            self.assertEqual(ef.neutralize(p + "SUM(A1)"), "'" + p + "SUM(A1)", repr(p))
            self.assertEqual(ef.neutralize(p), "'" + p, repr(p))

    def test_non_leading_unchanged(self):
        for v in ["a=b", "x-1", " =1", " +cmd", "hello@example", "", "'already", "5"]:
            self.assertEqual(ef.neutralize(v), v, repr(v))
        self.assertEqual(ef.neutralize(None), "")
        self.assertEqual(ef.neutralize(5), "5")

    def test_formula_in_csv_file(self):
        comments = ['=HYPERLINK("http://x","y")', "+1+1", "-2", "@SUM(A1)", "\t=1", "＝1", "a=b"]
        for i, c in enumerate(comments):
            self.insert(f"telegram:1:{i}", 5, c, f"2026-01-{i + 10}")
        out = self.tmp / "out.csv"
        ef.export_feedback(self.db, out)
        got = [r[1] for r in self.read_csv(out)[1:]]
        self.assertEqual(got, ["'" + c for c in comments[:-1]] + ["a=b"])

    # R8 -------------------------------------------------------------------
    def test_nested_parent_dirs_created(self):
        out = self.tmp / "a" / "b" / "c" / "out.csv"
        code, _, _ = self.run_main("--db", str(self.db), "--output", str(out))
        self.assertEqual(code, 0)
        self.assertTrue(out.is_file())

    # R9 -------------------------------------------------------------------
    def test_db_path_is_directory(self):
        d = self.tmp / "dbdir"
        d.mkdir()
        code, out, err = self.run_main("--db", str(d), "--output", str(self.tmp / "out.csv"))
        self.assert_error(code, out, err, "Error: database file not found")
        self.assertFalse((self.tmp / "out.csv").exists())

    def test_non_sqlite_file(self):
        bad = self.tmp / "bad.db"
        bad.write_bytes(b"this is not a sqlite database at all" * 20)
        before = sha256(bad)
        code, out, err = self.run_main("--db", str(bad), "--output", str(self.tmp / "o" / "out.csv"))
        self.assert_error(code, out, err, "Error: cannot read database")
        self.assertEqual(sha256(bad), before)
        self.assertFalse((self.tmp / "o").exists())

    def test_missing_columns(self):
        db = self.tmp / "cols.db"
        with closing(sqlite3.connect(db)) as conn, conn:
            conn.execute("CREATE TABLE survey_answers (sender_key TEXT PRIMARY KEY, rating INTEGER)")
            conn.execute("INSERT INTO survey_answers VALUES ('k', 1)")
        before = sha256(db)
        code, out, err = self.run_main("--db", str(db), "--output", str(self.tmp / "out.csv"))
        self.assert_error(code, out, err, "Error: survey_answers table is missing required columns")
        self.assertEqual(sha256(db), before)
        self.assertFalse((self.tmp / "out.csv").exists())

    def test_output_is_existing_directory(self):
        d = self.tmp / "outdir"
        d.mkdir()
        code, out, err = self.run_main("--db", str(self.db), "--output", str(d))
        self.assert_error(code, out, err, "Error: output path is a directory")
        self.assertEqual(list(d.iterdir()), [])

    def test_output_exists_without_force(self):
        self.insert("telegram:1:1", 5, SECRET, "2026-01-01")
        out = self.tmp / "out.csv"
        out.write_bytes(b"original")
        code, stdout, stderr = self.run_main("--db", str(self.db), "--output", str(out))
        self.assert_error(code, stdout, stderr, "Error: output file already exists")
        self.assertEqual(out.read_bytes(), b"original")
        self.assertNotIn(SECRET, stdout + stderr)
        self.assertEqual(self.leftover_temp(self.tmp), [])

    def test_force_overwrites(self):
        self.insert("telegram:1:1", 5, "new", "2026-01-01")
        out = self.tmp / "out.csv"
        out.write_bytes(b"original")
        code, _, _ = self.run_main("--db", str(self.db), "--output", str(out), "--force")
        self.assertEqual(code, 0)
        self.assertEqual(self.read_csv(out), [["rating", "comment", "updated_at"], ["5", "new", "2026-01-01"]])
        self.assertEqual(self.leftover_temp(self.tmp), [])

    def test_output_equals_db_path(self):
        self.insert("telegram:1:1", 5, "x", "2026-01-01")
        before = sha256(self.db)
        for extra in ((), ("--force",)):
            code, out, err = self.run_main("--db", str(self.db), "--output", str(self.db), *extra)
            self.assert_error(code, out, err, "Error: output path must differ from the database path")
            self.assertEqual(sha256(self.db), before)
        # Same file via a non-normalized path.
        alias = self.tmp / "sub" / ".." / "test.db"
        code, out, err = self.run_main("--db", str(self.db), "--output", str(alias), "--force")
        self.assert_error(code, out, err, "Error: output path must differ from the database path")
        self.assertEqual(sha256(self.db), before)

    def test_parent_is_regular_file(self):
        blocker = self.tmp / "blocker"
        blocker.write_bytes(b"file")
        out = blocker / "sub" / "out.csv"
        code, stdout, stderr = self.run_main("--db", str(self.db), "--output", str(out))
        self.assert_error(code, stdout, stderr, "Error: cannot create output directory")
        self.assertEqual(blocker.read_bytes(), b"file")

    def test_write_failure_cleans_temp(self):
        self.insert("telegram:1:1", 5, SECRET, "2026-01-01")
        out = self.tmp / "o" / "out.csv"
        with patch.object(ef.os, "replace", side_effect=PermissionError("denied " + SECRET)):
            code, stdout, stderr = self.run_main("--db", str(self.db), "--output", str(out))
        self.assert_error(code, stdout, stderr, "Error: cannot write output file")
        self.assertNotIn(SECRET, stdout + stderr)
        self.assertNotIn("denied", stderr)
        self.assertFalse(out.exists())
        self.assertEqual(self.leftover_temp(out.parent), [])

    # R10 ------------------------------------------------------------------
    def test_success_output_has_no_comment_text(self):
        self.insert("telegram:1:1", 5, SECRET, "2026-01-01")
        code, stdout, stderr = self.run_main("--db", str(self.db), "--output", str(self.tmp / "out.csv"))
        self.assertEqual(code, 0)
        self.assertNotIn(SECRET, stdout + stderr)
        self.assertNotIn(ProcessedMessages.sender_key("telegram:1:1"), stdout + stderr)

    def test_failure_outputs_have_no_comment_text(self):
        self.insert("telegram:1:1", 5, SECRET, "2026-01-01")
        d = self.tmp / "isdir"
        d.mkdir()
        cases = [("--output", str(d)), ("--output", str(self.db))]
        for case in cases:
            code, stdout, stderr = self.run_main("--db", str(self.db), *case)
            self.assertEqual(code, 1)
            self.assertNotIn(SECRET, stdout + stderr)

    # Paths / CLI ----------------------------------------------------------
    def test_special_character_paths(self):
        base = self.tmp / "dir with space #1 %20 日本語"
        base.mkdir()
        db = base / "回答 #%.db"
        ProcessedMessages(str(db))
        self.insert("telegram:1:1", 5, "ok", "2026-01-01", db=db)
        before = sha256(db)
        out = base / "出力 #%" / "out file.csv"
        code, stdout, stderr = self.run_main("--db", str(db), "--output", str(out))
        self.assertEqual(code, 0, stderr)
        self.assertEqual(self.read_csv(out)[1], ["5", "ok", "2026-01-01"])
        self.assertEqual(sha256(db), before)

    def test_missing_required_args(self):
        for args in ([], ["--db", str(self.db)], ["--output", str(self.tmp / "o.csv")]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
                ef.main(args)
            self.assertEqual(cm.exception.code, 2)

    def test_subprocess_end_to_end(self):
        self.insert("telegram:1:1", 5, "e2e", "2026-01-01")
        out = self.tmp / "e2e" / "out.csv"
        proc = subprocess.run([sys.executable, "tools/export_feedback.py", "--db", str(self.db), "--output", str(out)],
                              cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(proc.stdout.strip(), f"Exported 1 rows to {out}")
        self.assertEqual(self.read_csv(out)[1], ["5", "e2e", "2026-01-01"])

    def test_subprocess_error_exit_code(self):
        proc = subprocess.run([sys.executable, "tools/export_feedback.py", "--db", str(self.tmp / "missing.db"),
                               "--output", str(self.tmp / "o.csv")],
                              cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(proc.stderr.startswith("Error: database file not found"), proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
