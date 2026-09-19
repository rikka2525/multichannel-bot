"""Admin status report. Never includes tokens, DB paths, or connection strings."""
import logging

FAILED = "取得失敗"
DB_FAILED = "接続失敗"


def build_status(repository, active_adapters, db_unavailable=False):
    """Return status text. Each item is collected independently; errors never propagate."""
    try:
        adapters = ", ".join(sorted(active_adapters)) or "なし"
    except Exception as error:
        logging.error("Status adapters failed (%s)", type(error).__name__)
        adapters = FAILED
    try:
        if db_unavailable:
            db = DB_FAILED
        else:
            db = "接続OK" if repository.check() else "接続NG"
    except Exception as error:
        logging.error("Status DB check failed (%s)", type(error).__name__)
        db = DB_FAILED
    return f"[status]\n有効なAdapter: {adapters}\nDB接続: {db}"
