"""Shared fakes. FakeConnection stands in for an Oracle connection in UNIT tests only;
it proves our SQL/transaction logic, NOT Oracle behaviour (see test_oracle_integration.py)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import database  # noqa: E402


class FakeVar:
    def __init__(self):
        self.value = None

    def getvalue(self):
        return [self.value]


class FakeCursor:
    def __init__(self, conn):
        self.conn, self.rows, self.rowcount, self.description, self._pos = conn, [], 1, None, 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def var(self, _type):
        return FakeVar()

    def callproc(self, name, args):
        self.conn.executed.append((f"CALL {name}", list(args)))
        self.conn._maybe_fail(f"CALL {name}")

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))
        self.rows, self.rowcount, self._pos, self.description = [], 1, 0, None
        for r in self.conn.responders:
            if r["match"] in sql:
                if r.get("error"):
                    raise r["error"]
                rows = r.get("rows", [])
                self.rows = rows(params) if callable(rows) else rows
                self.rowcount = r.get("rowcount", 1)
                if r.get("cols"):
                    self.description = [(c,) for c in r["cols"]]
                break
        for key, value in (params or {}).items():
            if isinstance(value, FakeVar):
                value.value = self.conn.returning.get(key, 1)

    def fetchone(self):
        if self._pos < len(self.rows):
            self._pos += 1
            return self.rows[self._pos - 1]
        return None

    def fetchall(self):
        out, self._pos = self.rows[self._pos:], len(self.rows)
        return out


class FakeConnection:
    def __init__(self, responders=None, returning=None):
        self.responders, self.returning = responders or [], returning or {}
        self.executed, self.commits, self.rollbacks, self.closed = [], 0, 0, False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True

    def _maybe_fail(self, sql):
        for r in self.responders:
            if r["match"] in sql and r.get("error"):
                raise r["error"]

    def sql_log(self):
        return [s for s, _ in self.executed]


@pytest.fixture
def fake_db(monkeypatch):
    """Return a factory: fake_db(responders, returning) -> FakeConnection wired into services.database."""
    def install(responders=None, returning=None):
        conn = FakeConnection(responders, returning)
        monkeypatch.setattr(database, "get_connection", lambda: conn)
        return conn
    return install
