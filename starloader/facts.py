"""Incremental fact loading with surrogate key lookups."""

from __future__ import annotations

from dataclasses import dataclass, field

from starloader.config import FactConfig, PipelineConfig
from starloader.dates import date_key
from starloader.scd import UNKNOWN_SK, current_key_map
from starloader.warehouse import SQL_TYPES, Warehouse, to_sql_value


@dataclass
class FactStats:
    read: int = 0
    skipped_by_watermark: int = 0
    inserted: int = 0
    unknown_members: dict[str, int] = field(default_factory=dict)
    new_watermark: str | None = None


def _fact_columns(cfg: PipelineConfig, fact: FactConfig) -> list[tuple[str, str]]:
    cols = []
    for src_col, dim_name in fact.lookups.items():
        cols.append((cfg.dimension(dim_name).surrogate_key, "INTEGER NOT NULL"))
    if fact.watermark and fact.columns.get(fact.watermark) in {"date", "datetime"}:
        cols.append(("date_sk", "INTEGER"))
    for c, t in fact.columns.items():
        if c in fact.lookups:
            continue
        cols.append((c, SQL_TYPES[t]))
    return cols


def ensure_fact(wh: Warehouse, cfg: PipelineConfig, fact: FactConfig) -> None:
    if not wh.table_exists(fact.name):
        wh.create_table(fact.name, _fact_columns(cfg, fact))


def load_fact(wh: Warehouse, cfg: PipelineConfig, fact: FactConfig, rows: list[dict],
              full_reload: bool = False) -> FactStats:
    ensure_fact(wh, cfg, fact)
    stats = FactStats(read=len(rows))

    if full_reload:
        wh.conn.execute(f"DELETE FROM {fact.name}")
        last = None
    else:
        last = wh.last_watermark(fact.name) if fact.watermark else None

    key_maps = {
        src: (cfg.dimension(dim_name), current_key_map(wh, cfg.dimension(dim_name)))
        for src, dim_name in fact.lookups.items()
    }

    out = []
    max_wm = last
    for row in rows:
        wm_value = None
        if fact.watermark:
            wm_value = to_sql_value(row[fact.watermark])
            if last is not None and wm_value is not None and wm_value <= last:
                stats.skipped_by_watermark += 1
                continue
            if wm_value is not None and (max_wm is None or wm_value > max_wm):
                max_wm = wm_value

        record = {}
        for src, (dim, kmap) in key_maps.items():
            sk = kmap.get(row[src], UNKNOWN_SK)
            if sk == UNKNOWN_SK:
                stats.unknown_members[dim.name] = stats.unknown_members.get(dim.name, 0) + 1
            record[dim.surrogate_key] = sk
        if fact.watermark and fact.columns.get(fact.watermark) in {"date", "datetime"}:
            value = row[fact.watermark]
            record["date_sk"] = date_key(value) if value is not None else None
        for c in fact.columns:
            if c not in fact.lookups:
                record[c] = row[c]
        out.append(record)

    stats.inserted = wh.insert_many(fact.name, out)
    stats.new_watermark = max_wm
    return stats
