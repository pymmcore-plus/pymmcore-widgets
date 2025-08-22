from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from pymmcore_widgets._humanize import humanize_time, parse_time_string

if TYPE_CHECKING:
    from pymmcore_widgets._humanize import SupportsDuration, Unit

# fmt: off
CASES: list[tuple[SupportsDuration, Unit, str]] = [
    # basic micro/milli/second behavior
    (timedelta(microseconds=5), "microseconds", "5 µs"),
    (0.000005, "microseconds", "5 µs"),
    (timedelta(microseconds=1500), "microseconds", "1 ms and 500 µs"),
    (timedelta(microseconds=1500), "milliseconds", "1.5 ms"),
    (timedelta(milliseconds=5), "microseconds", "5 ms"),
    (0.005, "microseconds", "5 ms"),
    (1.1, "microseconds", "1.1 s"),
    (360.00512, "milliseconds", "6 min and 5.12 ms"),
    (360.00000512, "microseconds", "6 min and 5.12 µs"),
    (360.005000045, "milliseconds", "6 min and 5 ms"),
    (0.0008, "milliseconds", "1 ms"),
    (timedelta(milliseconds=500), "milliseconds", "500 ms"),
    (0.5, "milliseconds", "500 ms"),
    (5, "seconds", "5 s"),
    (5.5, "seconds", "5.5 s"),
    (timedelta(seconds=30), "seconds", "30 s"),

    # minutes/hours/days composition
    (60, "minutes", "1 min"),
    (75, "seconds", "1 min and 15 s"),
    (75, "microseconds", "1 min and 15 s"),
    (75, "minutes", "1.25 min"),
    (timedelta(seconds=3600), "hours", "1 h"),
    (timedelta(seconds=4600), "seconds", "1 h, 16 min and 40 s"),
    (86400, "days", "1 d"),

    # edge cases: zeros at each precision
    (0, "microseconds", "0 µs"),
    (0, "milliseconds", "0 ms"),
    (0, "seconds", "0 s"),
    (0, "minutes", "0 min"),
    (0, "hours", "0 h"),
    (0, "days", "0 d"),

    # rounding/threshold edges
    (0.0000004, "microseconds", "0 µs"),   # rounds down to 0 µs
    (0.0008, "milliseconds", "1 ms"),      # 0.8 ms rounds to 1 ms
    (0.9, "seconds", "0.9 s"),             # fractional seconds to 2 dp
    (59.999, "seconds", "60 s"),           # rounds up within seconds view
    (60, "seconds", "1 min"),              # switches to minutes at 60 s
    (3599, "minutes", "59.98 min"),        # just under an hour at minutes precision

    # negative durations are treated as absolute values
    (-5, "seconds", "5 s"),

    # multi-unit composition and Oxford-comma/and join
    (3661, "seconds", "1 h, 1 min and 1 s"),
    (90061, "seconds", "1 d, 1 h, 1 min and 1 s"),

    # strings
    ("5 µs", "microseconds", "5 µs"),
    ("5 us", "microseconds", "5 µs"),
    ("3 minutes 1 day 15 seconds", "microseconds", "1 d, 3 min and 15 s"),
    ("3 minutes 1 day 0.25 min", "seconds", "1 d, 3 min and 15 s"),
    ("3 minutes 1 day 4 µs", "microseconds", "1 d, 3 min and 4 µs"),
    ("3 minutes 1 day 410 ms", "seconds", "1 d, 3 min and 0.41 s"),
]


# fmt: on
@pytest.mark.parametrize("duration, minimum_precision, expected", CASES)
def test_humanize_time(
    duration: SupportsDuration,
    minimum_precision: Unit,
    expected: str,
) -> None:
    result = humanize_time(duration, minimum_precision)
    assert result == expected


def test_parse_time_string():
    with pytest.raises(ValueError):
        parse_time_string("asdaf")
