# starloader

A small, dependency-free Python toolkit for loading CSV extracts into a
**SQLite star schema**. It covers the parts of a classic BI load that usually
end up hand-written in every project:

- typed CSV extraction (auto-detected delimiter, Brazilian number and date formats)
- declarative data quality rules with blocking (`error`) and non-blocking (`warn`) severity
- dimensions with **SCD Type 2** history for tracked columns and Type 1 overwrite for the rest
- an "unknown member" row (`-1`) in every dimension so facts never get NULL keys
- incremental fact loads driven by a watermark column, with a load log table
- a generated `dim_date` with a `YYYYMMDD` smart key
- a CLI that prints a run summary or a Markdown quality report

Only the Python standard library is needed at runtime (Python 3.11+, for `tomllib`).

## Quick start

```bash
python -m starloader check examples/retail.toml            # quality report only
python -m starloader run examples/retail.toml --effective 2026-03-01
python -m starloader run examples/retail.toml --full-reload  # ignore watermarks
```

The example warehouse is written to `examples/retail.db`.

## Project layout

| Module | Responsibility |
|---|---|
| `config.py` | Parses and validates the TOML pipeline definition |
| `extract.py` | Reads CSVs and coerces values to declared types |
| `quality.py` | Runs quality rules and builds a `QualityReport` |
| `scd.py` | Creates dimension tables and merges extracts (SCD 1/2) |
| `facts.py` | Surrogate key lookups and incremental fact inserts |
| `dates.py` | Date dimension rows |
| `warehouse.py` | SQLite connection, DDL helpers, load log |
| `pipeline.py` | Orchestrates a full run inside one transaction |
| `report.py` | Text and Markdown rendering |
| `cli.py` | `python -m starloader` entry point |

## Configuration

See [`examples/retail.toml`](examples/retail.toml). Supported column types are
`str`, `int`, `float`, `date`, `datetime` and `bool`. Supported rules are
`not_null`, `unique`, `min`, `max`, `allowed` and `regex`.

## Known limitations

- Fact lookups always resolve to the **current** dimension version, not the
  version valid at the fact's date.
- Composite natural keys work for dimensions but cannot be used in fact lookups.
- Facts are append-only; late-arriving corrections to an already loaded row are
  not detected.
- Only SQLite is supported as a target.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

All example data under `examples/data` is synthetic.

## License

MIT, see [LICENSE](LICENSE).
