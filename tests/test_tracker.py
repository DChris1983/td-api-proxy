"""The scorecard must reproduce the worksheet tracker, deposits included."""

from datetime import date

import pytest

from desk import DayEntry, score_days

WEEK = [
    DayEntry(date(2020, 8, 3), 4038.79),
    DayEntry(date(2020, 8, 4), 4115.00),
    DayEntry(date(2020, 8, 5), 4155.00),
    DayEntry(date(2020, 8, 6), 4285.16),
    DayEntry(date(2020, 8, 7), 8266.55, deposit=4000),
]


def test_first_day_is_measured_from_starting_capital():
    first = score_days(4000, WEEK)[0]
    assert first.daily_gain == 38.79
    assert first.daily_pct == pytest.approx(38.79 / 4000, abs=1e-6)
    assert first.pct_target == 4040.00
    assert first.pct_target_delta == -1.21
    assert first.dollar_target == 5000.00
    assert first.dollar_target_delta == -961.21
    assert not first.made_daily_pct


def test_gain_is_day_over_day():
    second = score_days(4000, WEEK)[1]
    assert second.daily_gain == 76.21
    assert second.daily_pct == pytest.approx(76.21 / 4038.79, abs=1e-6)
    assert second.made_daily_pct
    assert second.pct_target == 4080.40  # compounds


def test_deposit_is_not_a_gain_and_lifts_both_targets():
    last = score_days(4000, WEEK)[-1]
    assert last.capital == 8000
    assert last.daily_gain == pytest.approx(-18.61)
    assert last.total_gain == pytest.approx(266.55)
    assert last.pct_target == pytest.approx(4000 * 1.01**5 + 4000, abs=0.01)
    assert last.dollar_target == 4000 + 5 * 1000 + 4000
    assert last.pct_target_delta == pytest.approx(8266.55 - (4000 * 1.01**5 + 4000), abs=0.01)


def test_entries_must_be_in_date_order():
    with pytest.raises(ValueError):
        score_days(4000, [WEEK[1], WEEK[0]])
