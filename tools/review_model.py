from __future__ import annotations

import hashlib
import json
import re
from bisect import bisect_left, bisect_right
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

SEMANTIC_EXIT_CODES: dict[str, int] = {
    "PASS": 0,
    "BLOCKED": 1,
    "INCOMPLETE": 3,
    "CONFLICTING": 4,
}
ERROR_EXIT_CODE = 2

RFC3339_PATTERN = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})[Tt]"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})"
    r"(?:\.(?P<fraction>\d+))?(?P<zone>[Zz]|[+-]\d{2}:\d{2})$"
)

# Positive UTC leap-second boundaries published through 2016-12-31.  Each
# tuple names the first nominal UTC second after the inserted leap second.  A
# future leap second therefore requires an explicit source update rather than
# silently inventing chronology from an unverified :60 timestamp.
_LEAP_SECOND_BOUNDARIES = (
    (1972, 7, 1),
    (1973, 1, 1),
    (1974, 1, 1),
    (1975, 1, 1),
    (1976, 1, 1),
    (1977, 1, 1),
    (1978, 1, 1),
    (1979, 1, 1),
    (1980, 1, 1),
    (1981, 7, 1),
    (1982, 7, 1),
    (1983, 7, 1),
    (1985, 7, 1),
    (1988, 1, 1),
    (1990, 1, 1),
    (1991, 1, 1),
    (1992, 7, 1),
    (1993, 7, 1),
    (1994, 7, 1),
    (1996, 1, 1),
    (1997, 7, 1),
    (1999, 1, 1),
    (2006, 1, 1),
    (2009, 1, 1),
    (2012, 7, 1),
    (2015, 7, 1),
    (2017, 1, 1),
)


def _nominal_utc_seconds(value: datetime) -> int:
    return (
        value.toordinal() * 86_400
        + value.hour * 3_600
        + value.minute * 60
        + value.second
    )


_LEAP_BOUNDARY_SECONDS = tuple(
    _nominal_utc_seconds(datetime(year, month, day, tzinfo=UTC))
    for year, month, day in _LEAP_SECOND_BOUNDARIES
)
_LEAP_BOUNDARY_SET = set(_LEAP_BOUNDARY_SECONDS)


def _fraction_compare(left: str, right: str) -> int:
    width = max(len(left), len(right))
    left_key = left.ljust(width, "0")
    right_key = right.ljust(width, "0")
    return (left_key > right_key) - (left_key < right_key)


class _ExactSeconds(float):
    def __new__(
        cls,
        later: RFC3339DateTime,
        earlier: RFC3339DateTime,
    ) -> _ExactSeconds:
        whole = later._timeline_seconds - earlier._timeline_seconds
        fraction_order = _fraction_compare(later._fraction_digits, earlier._fraction_digits)
        approximate = float(whole)
        if whole == 0 and fraction_order:
            approximate = 0.5 if fraction_order > 0 else -0.5
        elif whole > 0 and fraction_order < 0:
            approximate -= 0.5
        elif whole < 0 and fraction_order > 0:
            approximate += 0.5
        result = float.__new__(cls, approximate)
        result._later = later
        result._earlier = earlier
        return result

    def _compare_integer(self, other: object) -> int | None:
        if not isinstance(other, int) or isinstance(other, bool):
            return None
        target_whole = self._earlier._timeline_seconds + other
        if self._later._timeline_seconds != target_whole:
            return (self._later._timeline_seconds > target_whole) - (
                self._later._timeline_seconds < target_whole
            )
        return _fraction_compare(
            self._later._fraction_digits,
            self._earlier._fraction_digits,
        )

    def __le__(self, other: object) -> bool:
        compared = self._compare_integer(other)
        return float.__le__(self, other) if compared is None else compared <= 0

    def __lt__(self, other: object) -> bool:
        compared = self._compare_integer(other)
        return float.__lt__(self, other) if compared is None else compared < 0

    def __ge__(self, other: object) -> bool:
        compared = self._compare_integer(other)
        return float.__ge__(self, other) if compared is None else compared >= 0

    def __gt__(self, other: object) -> bool:
        compared = self._compare_integer(other)
        return float.__gt__(self, other) if compared is None else compared > 0


class _ExactTimedelta(timedelta):
    _later: RFC3339DateTime
    _earlier: RFC3339DateTime

    def __new__(
        cls,
        later: RFC3339DateTime,
        earlier: RFC3339DateTime,
    ) -> _ExactTimedelta:
        result = timedelta.__new__(cls)
        result._later = later
        result._earlier = earlier
        return result

    def total_seconds(self) -> float:
        return _ExactSeconds(self._later, self._earlier)


class RFC3339DateTime(datetime):
    """UTC datetime carrying an exact RFC3339 chronology key."""

    _timeline_seconds: int
    _fraction_digits: str

    def _compare_exact(self, other: RFC3339DateTime) -> int:
        if self._timeline_seconds != other._timeline_seconds:
            return (self._timeline_seconds > other._timeline_seconds) - (
                self._timeline_seconds < other._timeline_seconds
            )
        return _fraction_compare(self._fraction_digits, other._fraction_digits)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RFC3339DateTime):
            return self._compare_exact(other) == 0
        return datetime.__eq__(self, other)

    def __lt__(self, other: object) -> bool:
        if isinstance(other, RFC3339DateTime):
            return self._compare_exact(other) < 0
        return datetime.__lt__(self, other)

    def __le__(self, other: object) -> bool:
        if isinstance(other, RFC3339DateTime):
            return self._compare_exact(other) <= 0
        return datetime.__le__(self, other)

    def __gt__(self, other: object) -> bool:
        if isinstance(other, RFC3339DateTime):
            return self._compare_exact(other) > 0
        return datetime.__gt__(self, other)

    def __ge__(self, other: object) -> bool:
        if isinstance(other, RFC3339DateTime):
            return self._compare_exact(other) >= 0
        return datetime.__ge__(self, other)

    def __sub__(self, other: datetime) -> timedelta:
        if isinstance(other, RFC3339DateTime):
            return _ExactTimedelta(self, other)
        return datetime.__sub__(self, other)

    __hash__ = datetime.__hash__


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def canonical_digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def parse_rfc3339(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp must be a non-empty RFC3339 string")
    match = RFC3339_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("timestamp must use RFC3339 date-time syntax")

    year = int(match.group("year"))
    month = int(match.group("month"))
    day = int(match.group("day"))
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    second = int(match.group("second"))
    if hour > 23 or minute > 59 or second > 60:
        raise ValueError("timestamp must use valid RFC3339 clock fields")

    zone = match.group("zone")
    if zone in {"Z", "z"}:
        offset = UTC
    else:
        offset_hour = int(zone[1:3])
        offset_minute = int(zone[4:6])
        if offset_hour > 23 or offset_minute > 59:
            raise ValueError("timestamp must use a valid RFC3339 numeric offset")
        minutes = offset_hour * 60 + offset_minute
        if zone[0] == "-":
            minutes = -minutes
        try:
            offset = timezone(timedelta(minutes=minutes))
        except ValueError as exc:
            raise ValueError("timestamp must use a valid RFC3339 numeric offset") from exc

    fraction_digits = (match.group("fraction") or "").rstrip("0")
    represented_second = 59 if second == 60 else second
    microsecond = int((fraction_digits[:6]).ljust(6, "0")) if fraction_digits else 0
    try:
        local = datetime(
            year,
            month,
            day,
            hour,
            minute,
            represented_second,
            microsecond,
            tzinfo=offset,
        )
    except ValueError as exc:
        raise ValueError("timestamp must be a valid RFC3339 date-time") from exc

    utc = local.astimezone(UTC)
    if second == 60:
        boundary = utc.replace(microsecond=0) + timedelta(seconds=1)
        boundary_seconds = _nominal_utc_seconds(boundary)
        if boundary_seconds not in _LEAP_BOUNDARY_SET:
            raise ValueError("timestamp uses :60 outside a known UTC leap second")
        timeline_seconds = boundary_seconds + bisect_left(
            _LEAP_BOUNDARY_SECONDS,
            boundary_seconds,
        )
        visible = boundary
    else:
        nominal_seconds = _nominal_utc_seconds(utc)
        timeline_seconds = nominal_seconds + bisect_right(
            _LEAP_BOUNDARY_SECONDS,
            nominal_seconds,
        )
        visible = utc

    parsed = RFC3339DateTime(
        visible.year,
        visible.month,
        visible.day,
        visible.hour,
        visible.minute,
        visible.second,
        microsecond,
        tzinfo=UTC,
    )
    parsed._timeline_seconds = timeline_seconds
    parsed._fraction_digits = fraction_digits
    return parsed


def error_payload(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": {} if details is None else details,
        }
    }


def semantic_result(
    outcome: str,
    reason: str,
    *,
    input_document: dict[str, Any],
    policy_document: dict[str, Any],
    assessments: list[dict[str, Any]],
    collection: dict[str, Any],
    qualification: dict[str, Any],
    quorum: dict[str, Any],
    blockers: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    exclusions: list[dict[str, Any]],
    diagnostics: list[str],
) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "reason": reason,
        "binding": False,
        "evaluation_context": input_document.get("evaluation_context", {}),
        "subject": input_document.get("subject", {}),
        "authority": input_document.get("authority", {}),
        "judge": input_document.get("acquired_judge", {}),
        "policy": {
            "id": policy_document.get("id"),
            "version": policy_document.get("version"),
            "change_class": policy_document.get("change_class"),
            "review_requirement": policy_document.get("review_requirement"),
        },
        "collection": collection,
        "qualification": qualification,
        "quorum": quorum,
        "blockers": blockers,
        "conflicts": conflicts,
        "exclusions": exclusions,
        "diagnostics": sorted(set(diagnostics)),
        "assessments": assessments,
    }
