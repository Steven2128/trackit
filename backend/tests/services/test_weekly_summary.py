from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services.weekly_summary import (
    CategoryTotal,
    WeeklySummaryData,
    render_weekly_summary_email,
)


def _data(**overrides) -> WeeklySummaryData:
    defaults = dict(
        week_start=date(2026, 7, 6),
        week_end=date(2026, 7, 12),
        total_spent=Decimal("150000"),
        total_received=Decimal("500000"),
        by_category=[
            CategoryTotal(category="food", total=Decimal("100000"), count=5),
            CategoryTotal(category="transport", total=Decimal("50000"), count=3),
        ],
        transaction_count=8,
    )
    defaults.update(overrides)
    return WeeklySummaryData(**defaults)


class TestRenderWeeklySummaryEmail:
    def test_subject_includes_formatted_total_spent(self) -> None:
        subject, _ = render_weekly_summary_email(_data())
        assert "$150.000" in subject

    def test_subject_includes_week_range(self) -> None:
        subject, _ = render_weekly_summary_email(_data())
        assert "06/07" in subject
        assert "12/07/2026" in subject

    def test_html_includes_totals(self) -> None:
        _, html = render_weekly_summary_email(_data())
        assert "$150.000" in html
        assert "$500.000" in html
        assert "8" in html

    def test_html_includes_category_breakdown(self) -> None:
        _, html = render_weekly_summary_email(_data())
        assert "food" in html
        assert "$100.000" in html
        assert "transport" in html
        assert "$50.000" in html

    def test_empty_categories_shows_no_spending_message(self) -> None:
        _, html = render_weekly_summary_email(
            _data(by_category=[], total_spent=Decimal("0"), transaction_count=0)
        )
        assert "Sin gastos esta semana" in html

    def test_null_category_renders_fallback_label(self) -> None:
        _, html = render_weekly_summary_email(
            _data(by_category=[CategoryTotal(category=None, total=Decimal("1000"), count=1)])
        )
        assert "Sin categoría" in html
