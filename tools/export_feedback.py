"""Export survey answers to CSV. Read-only DB access; never outputs sender_key, raw IDs, or answer text in logs.

Usage: python tools/export_feedback.py --db data/mock.db --output exports/feedback.csv [--force]
"""
import argparse
import csv
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

FIELDS = ("rating", "comment", "updated_at")
# SQLite sidecar files next to the DB; overwriting them could corrupt the DB on recovery.
SIDECAR_SUFFIXES = ("-journal", "-wal", "-shm")
# Leading characters that spreadsheet apps may treat as a formula (incl. full-width variants).
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n", "＝", "＋", "－", "＠")


class ExportError(Exception):
    """Expected failure with a fixed, user-safe message."""


def neutralize(value) -> str:
    """Return a CSV cell string; prefix "'" so spreadsheets do not evaluate it as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text


def read_answers(db_path):
    """Read survey answers from an existing SQLite DB opened read-only."""
    path = Path(db_path).resolve()
    if not path.is_file():
        raise ExportError("database file not found")
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only = ON")
            if db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'survey_answers'").fetchone() is None:
                raise ExportError("survey_answers table not found")
            columns = {row[1] for row in db.execute("PRAGMA table_info(survey_answers)")}
            if not set(FIELDS) <= columns:
                raise ExportError("survey_answers table is missing required columns")
            return db.execute("SELECT rating, comment, updated_at FROM survey_answers ORDER BY updated_at, rowid").fetchall()
    except sqlite3.DatabaseError as error:
        raise ExportError(f"cannot read database ({type(error).__name__})") from None


def _same_file(a: Path, b: Path) -> bool:
    if a == b:
        return True
    try:
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def _normalize_name(name: str) -> str:
    """Normalize a file name as Windows would open it: drop ADS suffix, trailing dots/spaces, and case."""
    if os.name != "nt":
        return name
    return name.split(":", 1)[0].rstrip(" .").casefold()


def _is_db_sidecar(db_path, output_path) -> bool:
    """Return True if output_path names one of the DB's SQLite sidecar files (journal, WAL, shared memory).

    Compares the normalized file name and the parent directory (via samefile), so it also catches
    Windows spellings that differ lexically but open the same file (extended-length prefix, 8.3 names,
    trailing dots/spaces, case, ADS suffix). The sidecar need not exist yet. An existing sidecar is
    also matched by samefile, which covers its own 8.3 short name.
    """
    # abspath keeps an unresolved symlink name, which SQLite may use as the sidecar base.
    db_paths = {Path(db_path).resolve(), Path(os.path.abspath(db_path))}
    outputs = {Path(output_path).resolve(), Path(os.path.abspath(output_path))}
    if any(_same_file(Path(str(db) + suffix), output)
           for db in db_paths for suffix in SIDECAR_SUFFIXES for output in outputs):
        return True
    sidecar_names = {_normalize_name(db.name + suffix) for db in db_paths for suffix in SIDECAR_SUFFIXES}
    # Check each normalized candidate (not the raw name), so "<sidecar>.\x\.." style paths are caught.
    return any(_normalize_name(output.name) in sidecar_names
               and any(_same_file(db.parent, output.parent) for db in db_paths)
               for output in outputs)


def write_csv(rows, output_path, force=False):
    """Write rows atomically as UTF-8 (with BOM) CSV. Refuses to overwrite unless force is True."""
    output = Path(output_path).resolve()
    if output.is_dir():
        raise ExportError("output path is a directory")
    if output.exists() and not force:
        raise ExportError("output file already exists (use --force to overwrite)")
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ExportError(f"cannot create output directory ({type(error).__name__})") from None
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=output.parent, prefix=".feedback-", suffix=".tmp",
                                         delete=False, encoding="utf-8-sig", newline="") as handle:
            temp_path = Path(handle.name)
            writer = csv.writer(handle)
            writer.writerow(FIELDS)
            writer.writerows([neutralize(cell) for cell in row] for row in rows)
        os.replace(temp_path, output)
        temp_path = None
    except (OSError, csv.Error) as error:
        raise ExportError(f"cannot write output file ({type(error).__name__})") from None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def export_feedback(db_path, output_path, force=False) -> int:
    """Export survey answers to CSV and return the number of data rows written."""
    db = Path(db_path).resolve()
    output = Path(output_path).resolve()
    # abspath applies Windows normalization (e.g. strips trailing dots/spaces) that resolve() keeps.
    outputs = {output, Path(os.path.abspath(output_path))}
    if any(_same_file(db, candidate) for candidate in outputs):
        raise ExportError("output path must differ from the database path")
    if _is_db_sidecar(db_path, output_path):
        raise ExportError("output path must not be a database journal file (-journal, -wal, -shm)")
    rows = read_answers(db)  # Validate the DB before creating any output directory.
    write_csv(rows, output, force)
    return len(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Export survey answers (rating, comment, updated_at) to CSV.")
    parser.add_argument("--db", required=True, help="SQLite DB path (opened read-only)")
    parser.add_argument("--output", required=True, help="CSV output path")
    parser.add_argument("--force", action="store_true", help="overwrite an existing output file")
    args = parser.parse_args(argv)
    try:
        count = export_feedback(args.db, args.output, args.force)
    except ExportError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except (sqlite3.Error, OSError, csv.Error) as error:
        print(f"Error: export failed ({type(error).__name__})", file=sys.stderr)
        return 1
    print(f"Exported {count} rows to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
