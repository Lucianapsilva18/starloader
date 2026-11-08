"""Pipeline configuration, read from a TOML file.

Example layout::

    [warehouse]
    path = "warehouse.db"

    [[dimensions]]
    name = "dim_store"
    source = "data/stores.csv"
    natural_key = ["store_code"]
    tracked = ["region", "manager_level"]   # SCD Type 2 columns
    [dimensions.columns]
    store_code = "str"
    region = "str"

    [[facts]]
    name = "fact_sales"
    source = "data/sales.csv"
    watermark = "sold_at"
    ...
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from starloader.errors import ConfigError

SUPPORTED_TYPES = {"str", "int", "float", "date", "datetime", "bool"}


@dataclass
class QualityRule:
    column: str
    rule: str
    value: object = None
    severity: str = "error"  # "error" blocks the load, "warn" only reports


@dataclass
class DimensionConfig:
    name: str
    source: Path
    natural_key: list[str]
    columns: dict[str, str]
    tracked: list[str] = field(default_factory=list)
    rules: list[QualityRule] = field(default_factory=list)

    @property
    def surrogate_key(self) -> str:
        base = self.name[4:] if self.name.startswith("dim_") else self.name
        return f"{base}_sk"


@dataclass
class FactConfig:
    name: str
    source: Path
    columns: dict[str, str]
    lookups: dict[str, str]  # source column -> dimension name
    measures: list[str]
    watermark: str | None = None
    rules: list[QualityRule] = field(default_factory=list)


@dataclass
class PipelineConfig:
    warehouse: Path
    dimensions: list[DimensionConfig]
    facts: list[FactConfig]
    date_dimension: tuple[str, str] | None = None

    def dimension(self, name: str) -> DimensionConfig:
        for dim in self.dimensions:
            if dim.name == name:
                return dim
        raise ConfigError(f"unknown dimension: {name}")


def _parse_rules(raw: list[dict], owner: str) -> list[QualityRule]:
    rules = []
    for item in raw:
        if "column" not in item or "rule" not in item:
            raise ConfigError(f"{owner}: every rule needs 'column' and 'rule'")
        rules.append(
            QualityRule(
                column=item["column"],
                rule=item["rule"],
                value=item.get("value"),
                severity=item.get("severity", "error"),
            )
        )
    return rules


def _check_types(columns: dict[str, str], owner: str) -> None:
    for col, typ in columns.items():
        if typ not in SUPPORTED_TYPES:
            raise ConfigError(f"{owner}: column '{col}' has unsupported type '{typ}'")


def load_config(path: str | Path) -> PipelineConfig:
    path = Path(path)
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    base = path.parent

    try:
        warehouse = base / raw["warehouse"]["path"]
    except KeyError as exc:
        raise ConfigError("missing [warehouse] path") from exc

    dims = []
    for d in raw.get("dimensions", []):
        cols = d.get("columns", {})
        _check_types(cols, d["name"])
        missing = [k for k in d["natural_key"] + d.get("tracked", []) if k not in cols]
        if missing:
            raise ConfigError(f"{d['name']}: columns not declared: {missing}")
        dims.append(
            DimensionConfig(
                name=d["name"],
                source=base / d["source"],
                natural_key=list(d["natural_key"]),
                columns=cols,
                tracked=list(d.get("tracked", [])),
                rules=_parse_rules(d.get("rules", []), d["name"]),
            )
        )

    dim_names = {d.name for d in dims}
    facts = []
    for f in raw.get("facts", []):
        cols = f.get("columns", {})
        _check_types(cols, f["name"])
        lookups = f.get("lookups", {})
        for src_col, dim_name in lookups.items():
            if dim_name not in dim_names:
                raise ConfigError(f"{f['name']}: lookup to unknown dimension '{dim_name}'")
            if src_col not in cols:
                raise ConfigError(f"{f['name']}: lookup column '{src_col}' not declared")
        facts.append(
            FactConfig(
                name=f["name"],
                source=base / f["source"],
                columns=cols,
                lookups=lookups,
                measures=list(f.get("measures", [])),
                watermark=f.get("watermark"),
                rules=_parse_rules(f.get("rules", []), f["name"]),
            )
        )

    date_dim = None
    if "date_dimension" in raw:
        dd = raw["date_dimension"]
        date_dim = (dd["start"], dd["end"])

    return PipelineConfig(warehouse=warehouse, dimensions=dims, facts=facts, date_dimension=date_dim)
