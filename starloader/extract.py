"""Read CSV extracts and coerce each column to its declared type."""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from starloader.errors import ExtractError

NULL_TOKENS = {"", "null", "none", "n/a", "na"}
TRUE_TOKENS = {"1", "true", "t", "yes", "y", "sim", "s"}
FALSE_TOKENS = {"0", "false", "f", "no", "n", "nao", "não"}


def _parse_date(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date: {value!r}")


def _parse_datetime(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"unrecognised datetime: {value!r}")


def _parse_float(value: str) -> float:
    # Accept both 1234.56 and the Brazilian 1.234,56 notation.
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    return float(value)


def _parse_bool(value: str) -> bool:
    low = value.lower()
    if low in TRUE_TOKENS:
        return True
    if low in FALSE_TOKENS:
        return False
    raise ValueError(f"unrecognised boolean: {value!r}")


PARSERS = {
    "str": str,
    "int": int,
    "float": _parse_float,
    "date": _parse_date,
    "datetime": _parse_datetime,
    "bool": _parse_bool,
}


def coerce(value: str | None, typ: str):
    if value is None:
        return None
    value = value.strip()
    if value.lower() in NULL_TOKENS:
        return None
    return PARSERS[typ](value)


def detect_delimiter(path: Path) -> str:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(4096)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;|\t").delimiter
    except csv.Error:
        return ","


def read_rows(path: str | Path, columns: dict[str, str]) -> Iterator[dict]:
    """Yield typed rows. Columns not declared in ``columns`` are dropped."""
    path = Path(path)
    if not path.exists():
        raise ExtractError(f"source not found: {path}")

    delimiter = detect_delimiter(path)
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        header = [h.strip() for h in (reader.fieldnames or [])]
        reader.fieldnames = header
        missing = [c for c in columns if c not in header]
        if missing:
            raise ExtractError(f"{path.name}: missing columns {missing}")

        for line_no, raw in enumerate(reader, start=2):
            row = {}
            for col, typ in columns.items():
                try:
                    row[col] = coerce(raw.get(col), typ)
                except ValueError as exc:
                    raise ExtractError(f"{path.name}:{line_no} column '{col}': {exc}") from exc
            row["_line"] = line_no
            yield row
