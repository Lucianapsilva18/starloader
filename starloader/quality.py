"""Row-level and column-level data quality checks."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from starloader.config import QualityRule
from starloader.errors import ConfigError


@dataclass
class Violation:
    rule: QualityRule
    line: int | None
    value: object
    message: str


@dataclass
class QualityReport:
    table: str
    rows_checked: int = 0
    violations: list[Violation] = field(default_factory=list)

    @property
    def errors(self) -> list[Violation]:
        return [v for v in self.violations if v.rule.severity == "error"]

    @property
    def warnings(self) -> list[Violation]:
        return [v for v in self.violations if v.rule.severity == "warn"]

    @property
    def passed(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return (
            f"{self.table}: {self.rows_checked} rows checked, "
            f"{len(self.errors)} errors, {len(self.warnings)} warnings"
        )

    def by_rule(self) -> dict[str, int]:
        counts = Counter(f"{v.rule.column}:{v.rule.rule}" for v in self.violations)
        return dict(counts)


def _not_null(value, _arg):
    return value is not None


def _min(value, arg):
    return value is None or value >= arg


def _max(value, arg):
    return value is None or value <= arg


def _allowed(value, arg):
    return value is None or value in arg


def _regex(value, arg):
    return value is None or re.fullmatch(arg, str(value)) is not None


ROW_CHECKS = {
    "not_null": _not_null,
    "min": _min,
    "max": _max,
    "allowed": _allowed,
    "regex": _regex,
}
COLUMN_CHECKS = {"unique"}


def validate_rules(rules: list[QualityRule]) -> None:
    for r in rules:
        if r.rule not in ROW_CHECKS and r.rule not in COLUMN_CHECKS:
            raise ConfigError(f"unknown quality rule '{r.rule}' on column '{r.column}'")
        if r.severity not in {"error", "warn"}:
            raise ConfigError(f"invalid severity '{r.severity}' on column '{r.column}'")


def check(table: str, rows: list[dict], rules: list[QualityRule]) -> QualityReport:
    validate_rules(rules)
    report = QualityReport(table=table, rows_checked=len(rows))

    for rule in rules:
        if rule.rule == "unique":
            seen: dict[object, int] = {}
            for row in rows:
                val = row.get(rule.column)
                if val is None:
                    continue
                if val in seen:
                    report.violations.append(
                        Violation(rule, row.get("_line"), val,
                                  f"duplicate value (first seen on line {seen[val]})")
                    )
                else:
                    seen[val] = row.get("_line")
            continue

        fn = ROW_CHECKS[rule.rule]
        for row in rows:
            val = row.get(rule.column)
            if not fn(val, rule.value):
                report.violations.append(
                    Violation(rule, row.get("_line"), val, f"failed {rule.rule}({rule.value!r})")
                )
    return report
