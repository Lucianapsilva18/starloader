"""Date dimension generator."""

from __future__ import annotations

from datetime import date, timedelta

MONTHS_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]
WEEKDAYS_PT = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def date_key(d: date) -> int:
    """Smart key in YYYYMMDD form, the usual convention for dim_date."""
    return d.year * 10000 + d.month * 100 + d.day


def build_date_rows(start: date, end: date) -> list[dict]:
    if end < start:
        raise ValueError("end date is before start date")
    rows = []
    current = start
    while current <= end:
        iso_year, iso_week, _ = current.isocalendar()
        rows.append(
            {
                "date_sk": date_key(current),
                "full_date": current.isoformat(),
                "year": current.year,
                "quarter": (current.month - 1) // 3 + 1,
                "month": current.month,
                "month_name": MONTHS_PT[current.month - 1],
                "day": current.day,
                "weekday": current.weekday() + 1,
                "weekday_name": WEEKDAYS_PT[current.weekday()],
                "iso_week": iso_week,
                "is_weekend": int(current.weekday() >= 5),
                "year_month": f"{current.year}-{current.month:02d}",
            }
        )
        current += timedelta(days=1)
    return rows
