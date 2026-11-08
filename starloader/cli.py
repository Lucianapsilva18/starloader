"""Command line interface: ``python -m starloader <command> config.toml``."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from starloader.config import load_config
from starloader.errors import StarloaderError
from starloader.pipeline import Pipeline
from starloader.report import quality_markdown, run_summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="starloader", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="load all dimensions and facts")
    run.add_argument("config")
    run.add_argument("--effective", type=date.fromisoformat,
                     help="business date of the extract (YYYY-MM-DD), default today")
    run.add_argument("--full-reload", action="store_true",
                     help="truncate fact tables and ignore watermarks")
    run.add_argument("--ignore-quality", action="store_true",
                     help="load even when blocking quality rules fail")

    chk = sub.add_parser("check", help="run quality rules without loading")
    chk.add_argument("config")
    chk.add_argument("--markdown", metavar="FILE", help="write the report to FILE")

    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(message)s")
    try:
        cfg = load_config(args.config)
        pipeline = Pipeline(cfg)
        if args.command == "check":
            reports = pipeline.check_only()
            text = quality_markdown(reports)
            if args.markdown:
                with open(args.markdown, "w", encoding="utf-8") as fh:
                    fh.write(text)
            else:
                print(text)
            return 0 if all(r.passed for r in reports) else 2

        result = pipeline.run(effective=args.effective, full_reload=args.full_reload,
                              fail_on_quality=not args.ignore_quality)
        print(run_summary(result))
        return 0
    except StarloaderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
