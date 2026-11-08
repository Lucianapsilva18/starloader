"""Plain-text and Markdown rendering for run results and quality reports."""

from __future__ import annotations

from starloader.pipeline import RunResult
from starloader.quality import QualityReport


def quality_markdown(reports: list[QualityReport], max_examples: int = 5) -> str:
    lines = ["# Data quality report", ""]
    for rep in reports:
        status = "PASS" if rep.passed else "FAIL"
        lines.append(f"## {rep.table} [{status}]")
        lines.append("")
        lines.append(f"- rows checked: {rep.rows_checked}")
        lines.append(f"- errors: {len(rep.errors)}")
        lines.append(f"- warnings: {len(rep.warnings)}")
        if rep.violations:
            lines.append("")
            lines.append("| rule | count |")
            lines.append("|---|---|")
            for rule, count in sorted(rep.by_rule().items()):
                lines.append(f"| {rule} | {count} |")
            lines.append("")
            lines.append("Examples:")
            for v in rep.violations[:max_examples]:
                lines.append(f"- line {v.line}: `{v.rule.column}` = {v.value!r} ({v.message})")
        lines.append("")
    return "\n".join(lines)


def run_summary(result: RunResult) -> str:
    out = []
    if result.date_rows:
        out.append(f"dim_date: {result.date_rows} new days")
    for name, s in result.dimensions.items():
        out.append(
            f"{name}: read={s.read} new={s.inserted} new_versions={s.versioned} "
            f"type1_updates={s.updated} unchanged={s.unchanged}"
        )
    for name, s in result.facts.items():
        unknown = ", ".join(f"{k}={v}" for k, v in s.unknown_members.items()) or "none"
        out.append(
            f"{name}: read={s.read} inserted={s.inserted} "
            f"skipped_by_watermark={s.skipped_by_watermark} unknown_members={unknown} "
            f"watermark={s.new_watermark}"
        )
    return "\n".join(out)
