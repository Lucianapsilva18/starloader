import pytest

from starloader.config import QualityRule
from starloader.errors import ConfigError
from starloader.quality import check


ROWS = [
    {"id": 1, "v": 5, "c": "a", "_line": 2},
    {"id": 2, "v": -1, "c": "z", "_line": 3},
    {"id": 2, "v": None, "c": "a", "_line": 4},
]


def test_unique_reports_first_seen_line():
    rep = check("t", ROWS, [QualityRule("id", "unique")])
    assert len(rep.errors) == 1
    assert rep.errors[0].line == 4
    assert "line 3" in rep.errors[0].message


def test_min_ignores_nulls_and_not_null_catches_them():
    rep = check("t", ROWS, [QualityRule("v", "min", 0), QualityRule("v", "not_null")])
    assert rep.by_rule() == {"v:min": 1, "v:not_null": 1}


def test_warn_severity_does_not_fail():
    rep = check("t", ROWS, [QualityRule("c", "allowed", ["a"], severity="warn")])
    assert rep.passed
    assert len(rep.warnings) == 1


def test_regex_full_match():
    rows = [{"x": "S001"}, {"x": "S0011"}]
    rep = check("t", rows, [QualityRule("x", "regex", r"S\d{3}")])
    assert [v.value for v in rep.violations] == ["S0011"]


def test_unknown_rule_is_config_error():
    with pytest.raises(ConfigError):
        check("t", ROWS, [QualityRule("id", "between")])
