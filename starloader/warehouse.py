"""Thin wrapper around a SQLite database that holds the star schema."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

SQL_TYPES = {
    "str": "TEXT",
    "int": "INTEGER",
    "float": "REAL",
    "date": "TEXT",
    "datetime": "TEXT",
    "bool": "INTEGER",
}


def to_sql_value(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    return value


class Warehouse:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._ensure_meta()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @contextmanager
    def transaction(self):
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _ensure_meta(self) -> None:
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS _load_log (
                   run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                   table_name TEXT NOT NULL,
                   started_at TEXT NOT NULL,
                   rows_read INTEGER NOT NULL,
                   rows_inserted INTEGER NOT NULL,
                   rows_updated INTEGER NOT NULL,
                   watermark TEXT
               )"""
        )
        self.conn.commit()

    def table_exists(self, name: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        )
        return cur.fetchone() is not None

    def create_table(self, name: str, columns: list[tuple[str, str]], extra: str = "") -> None:
        cols = ", ".join(f"{c} {t}" for c, t in columns)
        if extra:
            cols = f"{cols}, {extra}"
        self.conn.execute(f"CREATE TABLE IF NOT EXISTS {name} ({cols})")

    def insert_many(self, table: str, rows: list[dict]) -> int:
        if not rows:
            return 0
        cols = list(rows[0].keys())
        placeholders = ", ".join("?" for _ in cols)
        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
        self.conn.executemany(sql, [[to_sql_value(r[c]) for c in cols] for r in rows])
        return len(rows)

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def last_watermark(self, table: str) -> str | None:
        cur = self.conn.execute(
            "SELECT watermark FROM _load_log WHERE table_name=? AND watermark IS NOT NULL "
            "ORDER BY run_id DESC LIMIT 1",
            (table,),
        )
        row = cur.fetchone()
        return row["watermark"] if row else None

    def log_load(self, table: str, read: int, inserted: int, updated: int,
                 watermark: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO _load_log (table_name, started_at, rows_read, rows_inserted, "
            "rows_updated, watermark) VALUES (?, ?, ?, ?, ?, ?)",
            (table, datetime.now().isoformat(timespec="seconds"), read, inserted, updated, watermark),
        )
