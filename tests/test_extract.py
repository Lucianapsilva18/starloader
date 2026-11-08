from datetime import date, datetime

import pytest

from starloader.errors import ExtractError
from starloader.extract import coerce, read_rows


@pytest.mark.parametrize(
    "raw,typ,expected",
    [
        ("42", "int", 42),
        ("1.234,56", "float", 1234.56),
        ("12.5", "float", 12.5),
        ("2026-02-03", "date", date(2026, 2, 3)),
        ("03/02/2026", "date", date(2026, 2, 3)),
        ("2026-02-03 10:11:12", "datetime", datetime(2026, 2, 3, 10, 11, 12)),
        ("sim", "bool", True),
        ("N", "bool", False),
        ("  ", "str", None),
        ("NULL", "int", None),
    ],
)
def test_coerce(raw, typ, expected):
    assert coerce(raw, typ) == expected


def test_coerce_rejects_bad_bool():
    with pytest.raises(ValueError):
        coerce("maybe", "bool")


def test_read_rows_semicolon_and_line_numbers(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a;b\n1;x\n2;y\n", encoding="utf-8")
    rows = list(read_rows(p, {"a": "int", "b": "str"}))
    assert [r["a"] for r in rows] == [1, 2]
    assert [r["_line"] for r in rows] == [2, 3]


def test_read_rows_missing_column(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a\n1\n", encoding="utf-8")
    with pytest.raises(ExtractError, match="missing columns"):
        list(read_rows(p, {"a": "int", "b": "str"}))


def test_read_rows_reports_line_of_bad_value(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a\n1\nabc\n", encoding="utf-8")
    with pytest.raises(ExtractError, match=":3 column 'a'"):
        list(read_rows(p, {"a": "int"}))
