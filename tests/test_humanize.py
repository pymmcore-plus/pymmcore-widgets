from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from pymmcore_widgets._humanize import humanize_time

if TYPE_CHECKING:
    from pymmcore_widgets._humanize import Precision


@pytest.mark.parametrize(
    "duration, minimum_precision, expected",
    [
        (timedelta(microseconds=5), "microseconds", "5 µs"),
        (0.000005, "microseconds", "5 µs"),
        (timedelta(microseconds=1500), "microseconds", "1 ms and 500 µs"),
        (timedelta(milliseconds=5), "microseconds", "5 ms"),
        (0.005, "microseconds", "5 ms"),
        (timedelta(milliseconds=500), "milliseconds", "500 ms"),
        (0.5, "milliseconds", "500 ms"),
        (5, "seconds", "5 s"),
        (5.5, "seconds", "5.50 s"),
        (timedelta(seconds=30), "seconds", "30 s"),
        (60, "minutes", "1 min"),
        (75, "seconds", "1 min and 15 s"),
        (75, "minutes", "1.25 min"),
        (timedelta(seconds=3600), "hours", "1 h"),
        (timedelta(seconds=4600), "seconds", "1 h, 16 min and 40 s"),
        (86400, "days", "1 d"),
    ],
)
def test_humanize_time(
    duration: timedelta | float | int,
    minimum_precision: Precision,
    expected: str,
) -> None:
    result = humanize_time(duration, minimum_precision)
    assert result == expected
