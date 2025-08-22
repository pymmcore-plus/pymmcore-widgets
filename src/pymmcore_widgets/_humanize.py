from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Literal

import pint

if TYPE_CHECKING:
    from pint.facets.plain import PlainQuantity
    from typing_extensions import TypeAlias

    Precision: TypeAlias = Literal[
        "microseconds",
        "milliseconds",
        "seconds",
        "minutes",
        "hours",
        "days",
    ]


UNIT_ABBR = {
    "microseconds": (US := "µs"),
    "milliseconds": (MS := "ms"),
    "seconds": (S := "s"),
    "minutes": (MIN := "min"),
    "hours": (H := "h"),
    "days": (D := "d"),
}
PRECISIONS = list(UNIT_ABBR)
UNIT_SECONDS = {
    "days": 86400,
    "hours": 3600,
    "minutes": 60,
    "seconds": 1,
}


def humanize_time(
    duration: int | float | timedelta | str | PlainQuantity,
    minimum_precision: Precision = "seconds",
) -> str:
    """
    Convert a duration to a human-readable duration string.

    Parameters
    ----------
    duration : int | float | timedelta | str | PlainQuantity
        int/float (seconds) or timedelta object to convert.  Also accepts pint
        Quantities (must be time dimension compatible), and strings will be cast
        to pint Quantities.
    minimum_precision : str
        Controls the smallest unit that will be displayed.  Must be one of:
        "microseconds", "milliseconds", "seconds", "minutes", "hours", "days

    Returns
    -------
        str: Human-readable duration string
    """
    total_sec = _norm_seconds(duration)
    try:
        idx = PRECISIONS.index(minimum_precision)
    except ValueError:  # pragma: no cover
        raise ValueError(
            f"Invalid minimum_precision string, must be one of {PRECISIONS}"
        ) from None

    # Handle sub-second formatting first
    if minimum_precision == "microseconds":  # allow µs
        total_micro = round(total_sec * 1_000_000)
        if total_micro == 0:
            return _zero(minimum_precision)
        if total_micro < 1000:
            return f"{total_micro} {US}"
        ms, us = divmod(total_micro, 1000)
        return f"{ms} {MS}" + (f" and {us} {US}" if us else "")

    if minimum_precision == "milliseconds" and total_sec < 1:  # only ms, no µs
        ms = round(total_sec * 1000)
        return f"{ms} {MS}" if ms else _zero(minimum_precision)

    if idx <= 2 and total_sec < 60:  # seconds (optionally fractional)
        return (
            (f"{int(total_sec)} {S}")
            if total_sec.is_integer()
            else f"{total_sec:.2f} {S}"
        )

    # Minutes precision: when caller requested 'minutes', format as
    # fractional minutes for durations less than 1 hour (e.g., 75s -> 1.25 min).
    if minimum_precision == "minutes" and total_sec < 3600:
        minutes = total_sec / 60
        return (
            f"{int(minutes)} {MIN}" if minutes.is_integer() else f"{minutes:.2f} {MIN}"
        )

    # From here on, compose days/hours/minutes/seconds as integers
    secs = int(total_sec)
    parts: list[str] = []
    for name, size in UNIT_SECONDS.items():
        if PRECISIONS.index(name) >= idx and secs >= size:
            qty, secs = divmod(secs, size)
            parts.append(f"{qty} {UNIT_ABBR[name]}")

    if not parts:
        return _zero(minimum_precision)

    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def _zero(unit: Precision) -> str:
    return f"0 {UNIT_ABBR[unit]}"


def _norm_seconds(duration: int | float | timedelta | str | PlainQuantity) -> float:
    # cast strings to pint quantities
    if isinstance(duration, str):
        duration = pint.Quantity(duration)

    # ensure pint quantities are time dimension compatible, and convert to timedelta
    if isinstance(duration, pint.Quantity):
        if not duration.check("[time]"):
            raise ValueError(f"{duration!r} is not a temporal quantity.")
        duration = timedelta(seconds=duration.to_base_units().magnitude)

    if isinstance(duration, timedelta):
        return duration.total_seconds()
    return float(duration)
