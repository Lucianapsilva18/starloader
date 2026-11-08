"""Orchestrates extract -> quality -> load for every table in a config."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from starloader.config import PipelineConfig
from starloader.dates import build_date_rows
from starloader.errors import QualityError
from starloader.extract import read_rows
from starloader.facts import FactStats, load_fact
from starloader.quality import QualityReport, check
from starloader.scd import MergeStats, merge_dimension
from starloader.warehouse import Warehouse

log = logging.getLogger("starloader")


@dataclass
class RunResult:
    quality: list[QualityReport] = field(default_factory=list)
    dimensions: dict[str, MergeStats] = field(default_factory=dict)
    facts: dict[str, FactStats] = field(default_factory=dict)
    date_rows: int = 0

    @property
    def ok(self) -> bool:
        return all(r.passed for r in self.quality)


class Pipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config

    def check_only(self) -> list[QualityReport]:
        reports = []
        for dim in self.config.dimensions:
            rows = list(read_rows(dim.source, dim.columns))
            reports.append(check(dim.name, rows, dim.rules))
        for fact in self.config.facts:
            rows = list(read_rows(fact.source, fact.columns))
            reports.append(check(fact.name, rows, fact.rules))
        return reports

    def _load_date_dimension(self, wh: Warehouse) -> int:
        if not self.config.date_dimension:
            return 0
        start, end = (date.fromisoformat(d) for d in self.config.date_dimension)
        rows = build_date_rows(start, end)
        if not wh.table_exists("dim_date"):
            wh.create_table(
                "dim_date",
                [("date_sk", "INTEGER PRIMARY KEY")] + [(c, "TEXT") for c in rows[0] if c != "date_sk"],
            )
        existing = {r["date_sk"] for r in wh.query("SELECT date_sk FROM dim_date")}
        missing = [r for r in rows if r["date_sk"] not in existing]
        return wh.insert_many("dim_date", missing)

    def run(self, effective: date | None = None, full_reload: bool = False,
            fail_on_quality: bool = True) -> RunResult:
        result = RunResult()
        with Warehouse(self.config.warehouse) as wh, wh.transaction():
            result.date_rows = self._load_date_dimension(wh)

            for dim in self.config.dimensions:
                rows = list(read_rows(dim.source, dim.columns))
                report = check(dim.name, rows, dim.rules)
                result.quality.append(report)
                if not report.passed and fail_on_quality:
                    raise QualityError(report)
                stats = merge_dimension(wh, dim, rows, effective)
                wh.log_load(dim.name, stats.read, stats.inserted + stats.versioned, stats.updated)
                result.dimensions[dim.name] = stats
                log.info("%s: %s", dim.name, stats)

            for fact in self.config.facts:
                rows = list(read_rows(fact.source, fact.columns))
                report = check(fact.name, rows, fact.rules)
                result.quality.append(report)
                if not report.passed and fail_on_quality:
                    raise QualityError(report)
                stats = load_fact(wh, self.config, fact, rows, full_reload=full_reload)
                wh.log_load(fact.name, stats.read, stats.inserted, 0, stats.new_watermark)
                result.facts[fact.name] = stats
                log.info("%s: %s", fact.name, stats)
        return result
