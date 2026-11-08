from starloader.cli import main


def test_check_exit_code_and_markdown(project, tmp_path):
    out = tmp_path / "report.md"
    assert main(["check", str(project / "config.toml"), "--markdown", str(out)]) == 0
    assert "fact_orders [PASS]" in out.read_text(encoding="utf-8")


def test_run_prints_summary(project, capsys):
    assert main(["run", str(project / "config.toml"), "--effective", "2026-01-01"]) == 0
    printed = capsys.readouterr().out
    assert "dim_customer: read=2 new=2" in printed
    assert "fact_orders: read=3 inserted=3" in printed


def test_missing_source_returns_error(project, capsys):
    (project / "orders.csv").unlink()
    assert main(["run", str(project / "config.toml")]) == 1
    assert "source not found" in capsys.readouterr().err
