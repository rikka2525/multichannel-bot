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

    # PR #16 F1: DB sidecar files (-journal, -wal, -shm) are never valid outputs, even with --force.
    SIDECAR_ERROR = "Error: output path must not be a database journal file"
    SIDECAR_BYTES = b"\x00SIDECAR-ORIGINAL-BYTES\xff" * 8

    def assert_sidecar_rejected(self, output, force, db_hash):
        args = ["--db", str(self.db), "--output", str(output)] + (["--force"] if force else [])
        code, stdout, stderr = self.run_main(*args)
        self.assert_error(code, stdout, stderr, self.SIDECAR_ERROR)
        self.assertNotIn(SECRET, stdout + stderr)
        self.assertEqual(sha256(self.db), db_hash)
        self.assertEqual(self.leftover_temp(self.tmp), [])

    def test_existing_sidecar_rejected_with_and_without_force(self):
        self.insert("telegram:1:1", 5, SECRET, "2026-01-01")
        db_hash = sha256(self.db)
        for suffix in ("-journal", "-wal", "-shm"):
            for force in (False, True):
                with self.subTest(suffix=suffix, force=force):
                    sidecar = Path(str(self.db) + suffix)
                    sidecar.write_bytes(self.SIDECAR_BYTES)
                    try:
                        self.assert_sidecar_rejected(sidecar, force, db_hash)
                        self.assertEqual(sidecar.read_bytes(), self.SIDECAR_BYTES)
                    finally:
                        sidecar.unlink(missing_ok=True)

    def test_absent_sidecar_rejected_and_not_created(self):
        self.insert("telegram:1:1", 5, SECRET, "2026-01-01")
        db_hash = sha256(self.db)
        for suffix in ("-journal", "-wal", "-shm"):
            for force in (False, True):
                with self.subTest(suffix=suffix, force=force):
                    sidecar = Path(str(self.db) + suffix)
                    self.assertFalse(sidecar.exists())
                    self.assert_sidecar_rejected(sidecar, force, db_hash)
                    self.assertFalse(sidecar.exists())

    def test_sidecar_rejected_before_db_is_opened(self):
        for suffix in ("-journal", "-wal", "-shm"):
            with self.subTest(suffix=suffix):
                with patch.object(ef, "read_answers", side_effect=AssertionError("DB must not be read")) as mocked, \
                        patch.object(ef, "write_csv", side_effect=AssertionError("must not write")) as writer:
                    with self.assertRaises(ef.ExportError) as cm:
                        ef.export_feedback(self.db, Path(str(self.db) + suffix), force=True)
                mocked.assert_not_called()
                writer.assert_not_called()
                self.assertTrue(str(cm.exception).startswith("output path must not be a database journal file"))

    def test_sidecar_alias_path_rejected(self):
        db_hash = sha256(self.db)
        for force in (False, True):
            with self.subTest(force=force):
                alias = self.tmp / "sub" / ".." / "test.db-wal"
                self.assert_sidecar_rejected(alias, force, db_hash)
                self.assertFalse((self.tmp / "sub").exists())
                self.assertFalse((self.tmp / "test.db-wal").exists())

    def test_sidecar_relative_paths_subprocess(self):
        sidecar = self.tmp / "test.db-journal"
        sidecar.write_bytes(self.SIDECAR_BYTES)
        db_hash = sha256(self.db)
        proc = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / "export_feedback.py"), "--db", "test.db",
                               "--output", "test.db-journal", "--force"],
                              cwd=self.tmp, capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.startswith(self.SIDECAR_ERROR), proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(sidecar.read_bytes(), self.SIDECAR_BYTES)
        self.assertEqual(sha256(self.db), db_hash)

    def test_sidecar_case_variant_on_windows(self):
        db_hash = sha256(self.db)
        variant = self.tmp / "TEST.DB-JOURNAL"
        code, stdout, stderr = self.run_main("--db", str(self.db), "--output", str(variant), "--force")
        if os.name == "nt":
            # Case-insensitive filesystem: this is the same file as test.db-journal.
            self.assert_error(code, stdout, stderr, self.SIDECAR_ERROR)
            self.assertFalse(Path(str(self.db) + "-journal").exists())
        else:
            # Case-sensitive filesystem: a distinct, unrelated file is allowed.
            self.assertEqual(code, 0, stderr)
            self.assertTrue(variant.is_file())
        self.assertEqual(sha256(self.db), db_hash)
        self.assertEqual(self.leftover_temp(self.tmp), [])

    def real_sidecars(self):
        return [s for s in ("-journal", "-wal", "-shm") if Path(str(self.db) + s).exists()]

    def enter_sandbox(self):
        """Move self.tmp/self.db one level down so writes escaping self.tmp (e.g. a backslash name on POSIX)
        land in a directory this test owns and can be detected without noise from the system temp dir."""
        outer = self.tmp
        self.tmp = outer / "sandbox"
        self.tmp.mkdir()
        self.db = self.tmp / "test.db"
        ProcessedMessages(str(self.db))
        self._outer_snapshot = (outer, sorted(p.name for p in outer.iterdir()))

    def assert_nothing_escaped(self):
        outer, before = self._outer_snapshot
        self.assertEqual(sorted(p.name for p in outer.iterdir()), before, "file written outside self.tmp")

    def test_trailing_dot_space_variants(self):
        # Windows strips trailing dots/spaces, so these name the real sidecar / DB there; on POSIX they are distinct.
        self.enter_sandbox()
        self.insert("telegram:1:1", 5, SECRET, "2026-01-01")
        db_hash = sha256(self.db)
        cases = [("test.db-journal.", self.SIDECAR_ERROR), ("test.db-wal ", self.SIDECAR_ERROR),
                 ("test.db-shm. .", self.SIDECAR_ERROR),
                 ("test.db.", "Error: output path must differ from the database path")]
        for name, message in cases:
            for force in (False, True):
                with self.subTest(name=name, force=force):
                    out = str(self.tmp) + os.sep + name
                    args = ["--db", str(self.db), "--output", out] + (["--force"] if force else [])
                    code, stdout, stderr = self.run_main(*args)
                    self.assertNotIn(SECRET, stdout + stderr)
                    if os.name == "nt":
                        self.assert_error(code, stdout, stderr, message)
                    else:
                        self.assertEqual(code, 0, stderr)
                        self.assertEqual(self.read_csv(out)[1], ["5", SECRET, "2026-01-01"])
                        os.remove(out)
                    self.assertEqual(self.real_sidecars(), [])
                    self.assertEqual(sha256(self.db), db_hash)
                    self.assertEqual(self.leftover_temp(self.tmp), [])
        self.assert_nothing_escaped()

    def test_alternate_data_stream_forms(self):
        self.enter_sandbox()
        db_hash = sha256(self.db)
        for name in ("test.db-journal::$DATA", "test.db-journal:s"):
            with self.subTest(name=name):
                out = str(self.tmp) + os.sep + name
                code, stdout, stderr = self.run_main("--db", str(self.db), "--output", out, "--force")
                if os.name == "nt":
                    # The ADS suffix names the sidecar itself, so it must be rejected by the sidecar check.
                    self.assert_error(code, stdout, stderr, self.SIDECAR_ERROR)
                    self.assertEqual(self.leftover_temp(self.tmp), [])
                self.assertFalse(Path(str(self.db) + "-journal").exists())
                self.assertEqual(sha256(self.db), db_hash)
        self.assert_nothing_escaped()

    # Windows path aliases: extended-length prefix and 8.3 short names --------
    SAME_DB_ERROR = "Error: output path must differ from the database path"

    def short_path(self, path):
        """8.3 short form of an existing path on Windows (may equal the long form if 8.3 names are disabled)."""
        if os.name != "nt":
            return str(path)
        import ctypes
        buf = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, len(buf))
        self.assertTrue(0 < length < len(buf), f"GetShortPathNameW failed for {path}")
        return buf.value

    def run_force(self, output):
        """Run the CLI with --force. On POSIX these strings may be relative names, so run with cwd=tmp."""
        if os.name == "nt":
            return self.run_main("--db", str(self.db), "--output", output, "--force")
        proc = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / "export_feedback.py"), "--db", str(self.db),
                               "--output", output, "--force"], cwd=self.tmp, capture_output=True, text=True, timeout=60)
        return proc.returncode, proc.stdout, proc.stderr

    # Windows extended-length prefix. On POSIX it makes the path relative, so run_force uses cwd=self.tmp there.
    EXTENDED = "\\\\?\\"

    def test_extended_and_short_path_aliases_rejected(self):
        self.enter_sandbox()
        self.insert("telegram:1:1", 5, SECRET, "2026-01-01")
        db_hash = sha256(self.db)
        short_tmp, sep = self.short_path(self.tmp), os.sep
        cases = [
            ("extended sidecar", self.EXTENDED + str(self.tmp / "test.db-journal"), self.SIDECAR_ERROR),
            ("short parent + trailing dot", short_tmp + sep + "test.db-wal.", self.SIDECAR_ERROR),
            ("extended + short parent", self.EXTENDED + short_tmp + sep + "test.db-shm", self.SIDECAR_ERROR),
            ("extended DB", self.EXTENDED + str(self.db), self.SAME_DB_ERROR),
            ("short parent DB + trailing dot", short_tmp + sep + "test.db.", self.SAME_DB_ERROR),
        ]
        for label, output, message in cases:
            with self.subTest(case=label):
                code, stdout, stderr = self.run_force(output)
                self.assertNotIn(SECRET, stdout + stderr)
                if os.name == "nt":
                    self.assert_error(code, stdout, stderr, message)
                    self.assertEqual(self.leftover_temp(self.tmp), [])
                self.assertEqual(self.real_sidecars(), [])
                self.assertEqual(sha256(self.db), db_hash)
        self.assert_nothing_escaped()

    def test_normalized_component_then_parent_rejected(self):
        # Security Low-A: "<sidecar>.\x\.." collapses to the sidecar on Windows; the raw last component is "..".
        self.enter_sandbox()
        self.insert("telegram:1:1", 5, SECRET, "2026-01-01")
        db_hash = sha256(self.db)
        short_tmp, sep = self.short_path(self.tmp), os.sep
        tail = sep + "x" + sep + ".."
        cases = [
            ("short parent + trailing dot", short_tmp + sep + "test.db-journal." + tail),
            ("short parent + trailing space", short_tmp + sep + "test.db-wal " + tail),
            ("extended prefix", self.EXTENDED + str(self.tmp) + sep + "test.db-wal" + tail),
        ]
        for label, output in cases:
            with self.subTest(case=label):
                code, stdout, stderr = self.run_force(output)
                self.assertNotIn(SECRET, stdout + stderr)
                if os.name == "nt":
                    self.assert_error(code, stdout, stderr, self.SIDECAR_ERROR)
                    self.assertEqual(self.leftover_temp(self.tmp), [])
                # On POSIX these are ordinary nested names; any file they create stays inside self.tmp.
                self.assertEqual(self.real_sidecars(), [])
                self.assertEqual(sha256(self.db), db_hash)
        # The same shape under another directory is not the DB's sidecar.
        other = self.tmp / "otherdir"
        other.mkdir()
        code, stdout, stderr = self.run_force(str(other) + sep + "test.db-journal." + tail)
        self.assertNotIn(SECRET, stdout + stderr)
        if os.name == "nt":
            self.assertEqual(code, 0, stderr)
            self.assertEqual(self.read_csv(other / "test.db-journal")[1], ["5", SECRET, "2026-01-01"])
        self.assertEqual(self.real_sidecars(), [])
        self.assertEqual(sha256(self.db), db_hash)
        self.assert_nothing_escaped()

    def test_existing_sidecar_short_name_rejected(self):
        self.enter_sandbox()
        self.insert("telegram:1:1", 5, SECRET, "2026-01-01")
        db_hash = sha256(self.db)
        for suffix in ("-journal", "-wal", "-shm"):
            with self.subTest(suffix=suffix):
                sidecar = Path(str(self.db) + suffix)
                sidecar.write_bytes(self.SIDECAR_BYTES)
                try:
                    short = self.short_path(sidecar)
                    code, stdout, stderr = self.run_force(short)
                    # If 8.3 names are disabled, short == long and this is the plain existing-sidecar case.
                    self.assert_error(code, stdout, stderr, self.SIDECAR_ERROR)
                    self.assertNotIn(SECRET, stdout + stderr)
                    self.assertEqual(sidecar.read_bytes(), self.SIDECAR_BYTES)
                    self.assertEqual(sha256(self.db), db_hash)
                    self.assertEqual(self.leftover_temp(self.tmp), [])
                finally:
                    sidecar.unlink(missing_ok=True)
        self.assert_nothing_escaped()

    def test_sidecar_name_in_other_directory_allowed(self):
        self.enter_sandbox()
        self.insert("telegram:1:1", 5, "ok", "2026-01-01")
        db_hash = sha256(self.db)
        existing_dir = self.tmp / "otherdir"
        existing_dir.mkdir()
        for out in (existing_dir / "test.db-journal", self.tmp / "newdir" / "test.db-journal"):
            with self.subTest(output=str(out)):
                code, _, stderr = self.run_main("--db", str(self.db), "--output", str(out), "--force")
                self.assertEqual(code, 0, stderr)
                self.assertEqual(self.read_csv(out)[1], ["5", "ok", "2026-01-01"])
                self.assertEqual(self.real_sidecars(), [])
                self.assertEqual(sha256(self.db), db_hash)
        # Going back up through an existing directory still names the DB's own sidecar.
        alias = existing_dir / ".." / "test.db-wal"
        code, stdout, stderr = self.run_main("--db", str(self.db), "--output", str(alias), "--force")
        self.assert_error(code, stdout, stderr, self.SIDECAR_ERROR)
        self.assertEqual(self.real_sidecars(), [])
        self.assertEqual(sha256(self.db), db_hash)
        self.assert_nothing_escaped()

    def test_sidecar_near_miss_names_allowed(self):
        self.insert("telegram:1:1", 5, "ok", "2026-01-01")
        db_hash = sha256(self.db)
        other = self.tmp / "other.db"
        ProcessedMessages(str(other))
        names = ["test.db-journal.csv", "test.db.wal", "test.db-journal2", "feedback-journal.csv", "other.db-wal"]
        for name in names:
            with self.subTest(name=name):
                out = self.tmp / name
                code, stdout, stderr = self.run_main("--db", str(self.db), "--output", str(out))
                self.assertEqual(code, 0, stderr)
                self.assertEqual(stderr, "")
                self.assertEqual(self.read_csv(out), [["rating", "comment", "updated_at"], ["5", "ok", "2026-01-01"]])
                self.assertEqual(sha256(self.db), db_hash)
        # Overwriting another DB's sidecar name with --force is also allowed.
        existing = self.tmp / "other.db-shm"
        existing.write_bytes(b"x")
        code, _, stderr = self.run_main("--db", str(self.db), "--output", str(existing), "--force")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(self.read_csv(existing)[1], ["5", "ok", "2026-01-01"])

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
