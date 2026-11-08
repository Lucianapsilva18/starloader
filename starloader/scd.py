"""Slowly Changing Dimension (Type 1 + Type 2) loading.

Columns listed in ``tracked`` keep history (Type 2): a change closes the
current version and opens a new one. Every other attribute is overwritten in
place on the current version (Type 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from starloader.config import DimensionConfig
from starloader.warehouse import SQL_TYPES, Warehouse, to_sql_value

OPEN_END = "9999-12-31"
UNKNOWN_SK = -1


@dataclass
class MergeStats:
    read: int = 0
    inserted: int = 0
    versioned: int = 0
    updated: int = 0
    unchanged: int = 0


def ensure_dimension(wh: Warehouse, dim: DimensionConfig) -> None:
    if wh.table_exists(dim.name):
        return
    cols = [(dim.surrogate_key, "INTEGER PRIMARY KEY AUTOINCREMENT")]
    cols += [(c, SQL_TYPES[t]) for c, t in dim.columns.items()]
    cols += [("valid_from", "TEXT NOT NULL"), ("valid_to", "TEXT NOT NULL"),
             ("is_current", "INTEGER NOT NULL")]
    wh.create_table(dim.name, cols)
    nk = ", ".join(dim.natural_key)
    wh.conn.execute(
        f"CREATE INDEX IF NOT EXISTS ix_{dim.name}_nk ON {dim.name} ({nk}, is_current)"
    )
    # Unknown member so that fact lookups never produce NULL foreign keys.
    unknown = {dim.surrogate_key: UNKNOWN_SK}
    for c, t in dim.columns.items():
        unknown[c] = "UNKNOWN" if t == "str" else None
    unknown.update(valid_from="1900-01-01", valid_to=OPEN_END, is_current=1)
    wh.insert_many(dim.name, [unknown])


def _key(row: dict, cols: list[str]) -> tuple:
    return tuple(to_sql_value(row[c]) for c in cols)


def _current_versions(wh: Warehouse, dim: DimensionConfig) -> dict[tuple, dict]:
    rows = wh.query(
        f"SELECT * FROM {dim.name} WHERE is_current = 1 AND {dim.surrogate_key} <> ?",
        (UNKNOWN_SK,),
    )
    return {_key(r, dim.natural_key): r for r in rows}


def merge_dimension(wh: Warehouse, dim: DimensionConfig, rows: list[dict],
                    effective: date | None = None) -> MergeStats:
    """Apply an extract to a dimension table. ``effective`` is the business
    date of the extract (defaults to today) and becomes valid_from for new
    versions."""
    ensure_dimension(wh, dim)
    eff = (effective or date.today()).isoformat()
    current = _current_versions(wh, dim)
    stats = MergeStats(read=len(rows))
    attrs = [c for c in dim.columns if c not in dim.natural_key]
    type1 = [c for c in attrs if c not in dim.tracked]

    new_rows = []
    for row in rows:
        key = _key(row, dim.natural_key)
        existing = current.get(key)
        incoming = {c: to_sql_value(row[c]) for c in dim.columns}

        if existing is None:
            new_rows.append({**incoming, "valid_from": eff, "valid_to": OPEN_END, "is_current": 1})
            stats.inserted += 1
            current[key] = incoming  # protects against duplicate keys in the same extract
            continue

        if any(existing.get(c) != incoming[c] for c in dim.tracked):
            wh.conn.execute(
                f"UPDATE {dim.name} SET valid_to = ?, is_current = 0 "
                f"WHERE {dim.surrogate_key} = ?",
                (eff, existing[dim.surrogate_key]),
            )
            new_rows.append({**incoming, "valid_from": eff, "valid_to": OPEN_END, "is_current": 1})
            stats.versioned += 1
            current[key] = incoming
        elif any(existing.get(c) != incoming[c] for c in type1):
            sets = ", ".join(f"{c} = ?" for c in type1)
            wh.conn.execute(
                f"UPDATE {dim.name} SET {sets} WHERE {dim.surrogate_key} = ?",
                (*[incoming[c] for c in type1], existing[dim.surrogate_key]),
            )
            stats.updated += 1
        else:
            stats.unchanged += 1

    wh.insert_many(dim.name, new_rows)
    return stats


def current_key_map(wh: Warehouse, dim: DimensionConfig) -> dict:
    """Natural key value -> current surrogate key. Only single-column natural
    keys are supported for fact lookups."""
    if len(dim.natural_key) != 1:
        raise NotImplementedError(f"{dim.name}: composite natural keys cannot be used in lookups")
    nk = dim.natural_key[0]
    rows = wh.query(f"SELECT {nk}, {dim.surrogate_key} FROM {dim.name} WHERE is_current = 1")
    return {r[nk]: r[dim.surrogate_key] for r in rows if r[dim.surrogate_key] != UNKNOWN_SK}
