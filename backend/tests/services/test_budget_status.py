from decimal import Decimal

from app.services.budget_status import budget_alert_status, budget_pct


def test_pct_zero_spent():
    assert budget_pct(Decimal("0"), Decimal("100000")) == Decimal("0.0")


def test_pct_half():
    assert budget_pct(Decimal("50000"), Decimal("100000")) == Decimal("50.0")


def test_pct_rounds_to_one_decimal():
    assert budget_pct(Decimal("333"), Decimal("1000")) == Decimal("33.3")
    assert budget_pct(Decimal("6666"), Decimal("10000")) == Decimal("66.7")


def test_pct_over_100():
    assert budget_pct(Decimal("150000"), Decimal("100000")) == Decimal("150.0")


def test_pct_zero_limit_with_spend_reports_100():
    assert budget_pct(Decimal("1"), Decimal("0")) == Decimal("100.0")


def test_pct_zero_limit_zero_spent():
    assert budget_pct(Decimal("0"), Decimal("0")) == Decimal("0.0")


def test_status_ok_below_80():
    assert budget_alert_status(Decimal("79999"), Decimal("100000")) == "ok"


def test_status_warning_at_80():
    assert budget_alert_status(Decimal("80000"), Decimal("100000")) == "warning"


def test_status_warning_just_below_100():
    assert budget_alert_status(Decimal("99999.99"), Decimal("100000")) == "warning"


def test_status_exceeded_at_100():
    assert budget_alert_status(Decimal("100000"), Decimal("100000")) == "exceeded"


def test_status_exceeded_over_100():
    assert budget_alert_status(Decimal("250000"), Decimal("100000")) == "exceeded"


def test_status_zero_limit_with_spend_is_exceeded():
    assert budget_alert_status(Decimal("1"), Decimal("0")) == "exceeded"


def test_status_zero_limit_zero_spent_is_ok():
    assert budget_alert_status(Decimal("0"), Decimal("0")) == "ok"
