"""Oracle connection layer (python-oracledb Thin mode) and query helpers.

Every helper takes SQL with bind variables plus a parameter dict - values are
never interpolated into SQL text. Failures are translated into AppError
subclasses whose messages never contain credentials, SQL or ORA internals.
"""
import logging
import re
from contextlib import contextmanager

import oracledb

import config
from .errors import (AppError, ConflictError, DatabaseUnavailableError,
                     NotFoundError, ValidationError)

log = logging.getLogger(__name__)
oracledb.defaults.fetch_decimals = True      # NUMBER(p,2) -> Decimal, never float

# Oracle error code -> (AppError class, user-safe message)
_ORA_MESSAGES = {
    1: (ConflictError, "A record with the same unique value (name, email, model number) already exists."),
    2290: (ValidationError, "A value violates a database rule (for example a negative price or stock)."),
    2291: (ValidationError, "A referenced record (category, supplier, customer ...) does not exist."),
    2292: (ConflictError, "This record is referenced by other records (for example products or sales) and cannot be deleted."),
    1438: (ValidationError, "A number is too large for its column."),
    12899: (ValidationError, "A text value is too long for its column."),
    30006: (ConflictError, "The inventory is being updated by another user. Please retry in a moment."),
    20001: (ValidationError, "Restock quantity must be a positive whole number."),
    20002: (NotFoundError, "Product does not exist."),
}
_CONNECTIVITY = (12154, 12514, 12541, 12170, 1017, 28000, 1005, 12505, 12543, 17002)


def ora_code(exc):
    """Extract the ORA-nnnnn number from an oracledb exception (or None)."""
    arg = exc.args[0] if exc.args else None
    code = getattr(arg, "code", None)
    if code:
        return code
    match = re.search(r"(?:ORA|DPY)-(\d+)", str(exc))
    return int(match.group(1)) if match else None


def translate(exc):
    """Map a driver exception to a safe AppError (details only go to the log)."""
    if isinstance(exc, AppError):
        return exc
    log.error("Database error: %s", exc)
    code = ora_code(exc)
    if code in _ORA_MESSAGES:
        cls, msg = _ORA_MESSAGES[code]
        return cls(msg)
    if isinstance(exc, (oracledb.OperationalError, oracledb.InterfaceError)) or code in _CONNECTIVITY \
            or "DPY-6" in str(exc) or "DPY-4" in str(exc):
        return DatabaseUnavailableError(
            "The database is unavailable. Check that the Oracle service and listener are running "
            "and that the DB_* settings in .env are correct (see README, Troubleshooting).")
    return AppError("A database error occurred. Details were written to the server log.")


def get_connection():
    """Open a new Thin-mode connection as the application user. Caller must close it."""
    s = config.load_db_settings()
    try:
        return oracledb.connect(user=s.user, password=s.password, dsn=s.dsn)
    except oracledb.Error as exc:
        raise translate(exc) from None


@contextmanager
def connection():
    """Yield a connection, always closed afterwards. Rolls back if the block raised."""
    conn = get_connection()
    try:
        yield conn
    except BaseException:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def _rows(cursor):
    names = [d[0].lower() for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def fetch_all(sql, params=None, conn=None):
    def run(c):
        with c.cursor() as cur:
            cur.execute(sql, params or {})
            return _rows(cur)
    try:
        if conn is not None:
            return run(conn)
        with connection() as c:
            return run(c)
    except oracledb.Error as exc:
        raise translate(exc) from None


def fetch_one(sql, params=None, conn=None):
    rows = fetch_all(sql, params, conn)
    return rows[0] if rows else None


def execute(sql, params=None):
    """Run one DML statement in its own transaction (commit on success). Returns row count."""
    try:
        with connection() as c:
            with c.cursor() as cur:
                cur.execute(sql, params or {})
                count = cur.rowcount
            c.commit()
            return count
    except oracledb.Error as exc:
        raise translate(exc) from None


def insert_returning(sql, params, id_column_bind="new_id"):
    """INSERT ... RETURNING <id> INTO :new_id ; returns the new id (own transaction)."""
    try:
        with connection() as c:
            with c.cursor() as cur:
                out = cur.var(int)
                cur.execute(sql, {**params, id_column_bind: out})
                new_id = out.getvalue()[0]
            c.commit()
            return new_id
    except oracledb.Error as exc:
        raise translate(exc) from None


PER_PAGE = 10


def fetch_page(columns, source, where, params, order_by, page_no, per_page=PER_PAGE):
    """Paged SELECT. columns/source/where/order_by are developer-written SQL fragments
    (never user input); user values travel only in `params`. Returns a dict for templates."""
    try:
        with connection() as c:
            total = int(fetch_one(f"SELECT COUNT(*) AS n FROM {source}{where}", params, c)["n"])
            pages = max(1, -(-total // per_page))
            page_no = min(max(1, page_no), pages)
            sql = (f"SELECT {columns} FROM {source}{where} ORDER BY {order_by} "
                   "OFFSET :page_offset ROWS FETCH NEXT :page_size ROWS ONLY")
            rows = fetch_all(sql, {**params, "page_offset": (page_no - 1) * per_page,
                                   "page_size": per_page}, c)
        return {"rows": rows, "page": page_no, "pages": pages, "total": total}
    except oracledb.Error as exc:
        raise translate(exc) from None


def health_check():
    """Return (ok, message). Only reports success after a real round trip."""
    try:
        row = fetch_one("SELECT USER AS db_user, SYS_CONTEXT('USERENV','SERVICE_NAME') AS service FROM DUAL")
        return True, f"Connected as {row['db_user']} to service {row['service']}"
    except (AppError, config.ConfigError) as exc:
        return False, str(exc)


if __name__ == "__main__":      # python -m services.database  -> connectivity diagnostic
    from dotenv import load_dotenv
    load_dotenv()
    ok, message = health_check()
    print(("OK: " if ok else "FAILED: ") + message)
    raise SystemExit(0 if ok else 1)
