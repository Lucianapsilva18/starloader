from datetime import date

import pytest

from starloader import Pipeline, load_config
from starloader.dates import build_date_rows, date_key
from starloader.errors import ConfigError, QualityError
from starloader.scd import UNKNOWN_SK
from starloader.warehouse import Warehouse


def test_first_run_loads_everything(project):
    cfg = load_config(project / "config.toml")
    result = Pipeline(cfg).run(effective=date(2026, 1, 1))

    assert result.date_rows == 31
    assert result.dimensions["dim_customer"].inserted == 2
    facts = result.facts["fact_orders"]
    assert facts.inserted == 3
    assert facts.unknown_members == {"dim_customer": 1}
    assert facts.new_watermark == "2026-01-07"

    with Warehouse(cfg.warehouse) as wh:
        rows = wh.query("SELECT customer_sk, date_sk FROM fact_orders ORDER BY order_id")
    assert rows[2]["customer_sk"] == UNKNOWN_SK
    assert rows[0]["date_sk"] == 20260105


def test_scd2_versions_tracked_and_overwrites_type1(project):
    cfg = load_config(project / "config.toml")
    Pipeline(cfg).run(effective=date(2026, 1, 1))

    (project / "customers.csv").write_text(
        "customer_id,nickname,segment\nC1,alpha,corporate\nC2,beta-renamed,corporate\n",
        encoding="utf-8",
    )
    result = Pipeline(cfg).run(effective=date(2026, 2, 1))
    stats = result.dimensions["dim_customer"]
    assert (stats.versioned, stats.updated, stats.unchanged) == (1, 1, 0)

    with Warehouse(cfg.warehouse) as wh:
        c1 = wh.query("SELECT * FROM dim_customer WHERE customer_id='C1' ORDER BY customer_sk")
        c2 = wh.query("SELECT * FROM dim_customer WHERE customer_id='C2'")
    assert [r["segment"] for r in c1] == ["retail", "corporate"]
    assert c1[0]["valid_to"] == "2026-02-01" and c1[0]["is_current"] == 0
    assert c1[1]["valid_from"] == "2026-02-01" and c1[1]["is_current"] == 1
    assert len(c2) == 1 and c2[0]["nickname"] == "beta-renamed"


def test_watermark_skips_already_loaded_rows(project):
    cfg = load_config(project / "config.toml")
    Pipeline(cfg).run()
    with open(project / "orders.csv", "a", encoding="utf-8") as fh:
        fh.write("O4,2026-01-09,C1,7\n")
    stats = Pipeline(cfg).run().facts["fact_orders"]
    assert stats.inserted == 1
    assert stats.skipped_by_watermark == 3


def test_full_reload_ignores_watermark(project):
    cfg = load_config(project / "config.toml")
    Pipeline(cfg).run()
    stats = Pipeline(cfg).run(full_reload=True).facts["fact_orders"]
    assert stats.inserted == 3
    with Warehouse(cfg.warehouse) as wh:
        assert wh.query("SELECT COUNT(*) AS n FROM fact_orders")[0]["n"] == 3


def test_blocking_quality_error_rolls_back(project):
    cfg = load_config(project / "config.toml")
    (project / "orders.csv").write_text(
        "order_id,ordered_on,customer_id,amount\nO1,2026-01-05,C1,-3\n", encoding="utf-8"
    )
    with pytest.raises(QualityError):
        Pipeline(cfg).run()
    with Warehouse(cfg.warehouse) as wh:
        assert not wh.table_exists("dim_customer")


def test_config_rejects_unknown_lookup(project):
    text = (project / "config.toml").read_text().replace(
        'customer_id = "dim_customer"', 'customer_id = "dim_nope"'
    )
    (project / "config.toml").write_text(text)
    with pytest.raises(ConfigError, match="unknown dimension"):
        load_config(project / "config.toml")


def test_date_rows():
    rows = build_date_rows(date(2026, 1, 3), date(2026, 1, 4))
    assert [r["date_sk"] for r in rows] == [20260103, 20260104]
    assert all(r["is_weekend"] == 1 for r in rows)
    assert rows[0]["month_name"] == "janeiro"
    assert date_key(date(2026, 12, 31)) == 20261231
