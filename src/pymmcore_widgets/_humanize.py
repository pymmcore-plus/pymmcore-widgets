from __future__ import annotations

import re
from datetime import timedelta
from typing import TYPE_CHECKING, Literal

import pint

if TYPE_CHECKING:
    from typing import SupportsFloat

    from pint.facets.plain import PlainQuantity
    from typing_extensions import TypeAlias

    SupportsDuration: TypeAlias = SupportsFloat | timedelta | str | PlainQuantity
    Unit: TypeAlias = Literal[
        "microseconds", "milliseconds", "seconds", "minutes", "hours", "days"
    ]

__all__ = ["humanize_time", "parse_time_string"]

# canonical order, abbreviations, and sizes
UNIT_ORDER: tuple[Unit, ...] = (
    "microseconds",
    "milliseconds",
    "seconds",
    "minutes",
    "hours",
    "days",
)
ABBR: dict[Unit, str] = {
    "microseconds": "µs",
    "milliseconds": "ms",
    "seconds": "s",
    "minutes": "min",
    "hours": "h",
    "days": "d",
}
UNIT_SECS: dict[Unit, int] = {
    "days": 86_400,
    "hours": 3_600,
    "minutes": 60,
}
_IDX = {u: i for i, u in enumerate(UNIT_ORDER)}
_TIME_PARTS = re.compile(r"[-+]?\d*\.?\d+(?:e[-+]?\d+)?\s*[^\d,+-]+")


def _fmt(val: float, unit_abbr: str, fmt: str) -> str:
    return f"{(fmt % val).rstrip('0').rstrip('.')} {unit_abbr}"


def _to_seconds(duration: SupportsDuration) -> float:
    if isinstance(duration, str):
        duration = parse_time_string(duration)
    if isinstance(duration, pint.Quantity):
        if not duration.check("[time]"):  # pragma: no cover
            raise ValueError(f"{duration!r} is not a temporal quantity.")
        duration = timedelta(seconds=float(duration.to("s").magnitude))
    if isinstance(duration, timedelta):
        return duration.total_seconds()
    return float(duration)


def _split_major(total_sec: float) -> tuple[list[str], int, float]:
    """Return (major_parts, whole_seconds, frac_seconds)."""
    secs_i = int(total_sec)
    frac = total_sec - secs_i
    parts: list[str] = []
    for u, size in UNIT_SECS.items():
        if secs_i >= size:
            q, secs_i = divmod(secs_i, size)
            parts.append(f"{q} {ABBR[u]}")
    return parts, secs_i, frac


def _append_seconds(
    parts: list[str],
    secs_i: int,
    frac: float,
    minimum_unit: Unit,
    fmt: str,
) -> None:
    if _IDX["seconds"] < _IDX[minimum_unit]:
        return
    s = secs_i + (frac if minimum_unit == "seconds" else 0.0)
    if s <= 0:
        return
    if s.is_integer():
        parts.append(f"{int(s)} {ABBR['seconds']}")
    else:
        parts.append(_fmt(s, ABBR["seconds"], fmt))


def _subsecond_tail(
    frac_s: float, minimum_unit: Unit, fmt: str, whole_under_one_sec: bool
) -> list[str]:
    """Return subseconds after second handling.

    For the <1 s path:
      - milliseconds: round sub-1 ms to nearest int ms; omit if 0
      - microseconds: round to int µs, splitting into ms+µs when ≥ 1000 µs
    Otherwise (tail path), format the chosen subsecond unit, allowing
    fractional µs/ms via `fmt` when not an integer.
    """
    factor = 1_000.0 if minimum_unit == "milliseconds" else 1_000_000.0
    abbr = ABBR[minimum_unit]
    v = frac_s * factor

    if whole_under_one_sec:
        vi = round(v)
        if minimum_unit == "milliseconds":
            # Round sub-1 ms cases and suppress zero
            if v < 1:
                return [f"{vi} {abbr}"] if vi else []
        else:  # microseconds
            if vi < 1_000:
                return [f"{vi} {abbr}"]
            ms, us = divmod(vi, 1_000)
            out = [f"{ms} {ABBR['milliseconds']}"]
            if us:
                out.append(f"{us} {ABBR['microseconds']}")
            return out

    # Standard tail formatting (allows fractional values)
    if v.is_integer():
        return [f"{int(v)} {abbr}"] if v else []
    return [_fmt(v, abbr, fmt)]


def humanize_time(
    duration: SupportsDuration, minimum_unit: Unit = "seconds", format: str = "%.2f"
) -> str:
    """Convert a duration to a human-readable string.

    Parameters
    ----------
    duration
        Seconds as int or float, a timedelta, a time-like pint Quantity, or a string.
        Strings are parsed additively, e.g. "1 day 3 min 4 s".
    minimum_unit
        The smallest unit to display. One of "microseconds", "milliseconds", "seconds",
        "minutes", "hours", "days".
    format
        A format string for the fractional part of `minimum_unit`. When
        `minimum_unit == "seconds"`, fractional seconds are shown even when
        larger units are present.

    Returns
    -------
    str
        Human-readable duration string.
    """
    if minimum_unit not in _IDX:  # pragma: no cover
        raise ValueError(f"Invalid minimum_unit, must be one of {UNIT_ORDER}")

    total = abs(_to_seconds(duration))

    # Pure subsecond path when total < 1 s
    if total < 1 and minimum_unit in {"milliseconds", "microseconds"}:
        parts = _subsecond_tail(total, minimum_unit, format, whole_under_one_sec=True)
        return " and ".join(parts) if parts else f"0 {ABBR[minimum_unit]}"

    # Fractional minutes under 1 hour
    if minimum_unit == "minutes" and total < 3600:
        return _fmt(total / 60.0, ABBR["minutes"], format)

    # General path
    parts, secs_i, frac = _split_major(total)
    _append_seconds(parts, secs_i, frac, minimum_unit, format)

    # Subsecond tail for higher precision requests
    if minimum_unit in {"milliseconds", "microseconds"}:
        parts.extend(
            _subsecond_tail(frac, minimum_unit, format, whole_under_one_sec=False)
        )

    if not parts:
        return f"0 {ABBR[minimum_unit]}"
    if len(parts) <= 2:
        return " and ".join(parts)
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def parse_time_string(
    time_string: str, quant_cls: type[pint.Quantity] = pint.Quantity
) -> PlainQuantity:
    """Parse additive strings like '1 day, 3 min and 4 s' into a pint Quantity."""
    print("parse", time_string)
    import inspect

    # show who called us
    print("called from", inspect.stack()[1].function, inspect.stack()[2].function)
    time_string = time_string.replace(",", "").replace("and", " ")
    if not (parts := _TIME_PARTS.findall(time_string)):
        raise ValueError(f"Invalid time string: {time_string}")
    total = sum([quant_cls(part) for part in parts], quant_cls("0 s"))
    return total
