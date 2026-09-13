from __future__ import annotations

import hashlib
import json
import re
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from functools import total_ordering
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

# Positive UTC leap-second boundaries published through 2016-12-31. Each tuple
# names the first nominal UTC second after the inserted leap second. Future leap
# seconds require an explicit source update rather than guessed chronology.
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


def _fraction_decimal(digits: str) -> Decimal:
    if not digits:
        return Decimal(0)
    return Decimal(int(digits)) / (Decimal(10) ** len(digits))


@dataclass(frozen=True)
class RFC3339Duration:
    later: RFC3339Timestamp
    earlier: RFC3339Timestamp

    def total_seconds(self) -> float:
        whole = self.later.timeline_seconds - self.earlier.timeline_seconds
        fractional = _fraction_decimal(self.later.fraction_digits) - _fraction_decimal(
            self.earlier.fraction_digits
        )
        return float(Decimal(whole) + fractional)


@total_ordering
@dataclass(frozen=True, eq=False)
class RFC3339Timestamp:
    """Exact RFC3339 chronology independent of Python microsecond precision."""

    timeline_seconds: int
    fraction_digits: str

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RFC3339Timestamp):
            return NotImplemented
        return (
            self.timeline_seconds == other.timeline_seconds
            and _fraction_compare(self.fraction_digits, other.fraction_digits) == 0
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, RFC3339Timestamp):
            return NotImplemented
        if self.timeline_seconds != other.timeline_seconds:
            return self.timeline_seconds < other.timeline_seconds
        return _fraction_compare(self.fraction_digits, other.fraction_digits) < 0

    def __sub__(self, earlier: RFC3339Timestamp) -> RFC3339Duration:
        return RFC3339Duration(self, earlier)

    def is_within_seconds_after(
        self,
        earlier: RFC3339Timestamp,
        max_seconds: int,
    ) -> bool:
        """Return whether self is in [earlier, earlier + max_seconds] exactly."""

        if self < earlier:
            return False
        whole_seconds = self.timeline_seconds - earlier.timeline_seconds
        if whole_seconds < max_seconds:
            return True
        if whole_seconds > max_seconds:
            return False
        return _fraction_compare(self.fraction_digits, earlier.fraction_digits) <= 0


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


def parse_rfc3339(value: object) -> RFC3339Timestamp:
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
    offset_minutes = 0
    if zone not in {"Z", "z"}:
        offset_hour = int(zone[1:3])
        offset_minute = int(zone[4:6])
        if offset_hour > 23 or offset_minute > 59:
            raise ValueError("timestamp must use a valid RFC3339 numeric offset")
        offset_minutes = offset_hour * 60 + offset_minute
        if zone[0] == "-":
            offset_minutes = -offset_minutes

    fraction_digits = (match.group("fraction") or "").rstrip("0")
    represented_second = 59 if second == 60 else second
    try:
        local = datetime(
            year,
            month,
            day,
            hour,
            minute,
            represented_second,
        )
    except ValueError as exc:
        raise ValueError("timestamp must be a valid RFC3339 date-time") from exc

    # Convert to the UTC chronology with integer arithmetic. Unlike
    # datetime.astimezone(), this stays defined when a legal local timestamp plus
    # its RFC3339 offset denotes an instant just outside Python's year 1..9999
    # datetime range.
    offset_seconds = offset_minutes * 60
    local_nominal_seconds = _nominal_utc_seconds(local)
    if second == 60:
        boundary_seconds = local_nominal_seconds + 1 - offset_seconds
        if boundary_seconds not in _LEAP_BOUNDARY_SET:
            raise ValueError("timestamp uses :60 outside a known UTC leap second")
        timeline_seconds = boundary_seconds + bisect_left(
            _LEAP_BOUNDARY_SECONDS,
            boundary_seconds,
        )
    else:
        nominal_seconds = local_nominal_seconds - offset_seconds
        timeline_seconds = nominal_seconds + bisect_right(
            _LEAP_BOUNDARY_SECONDS,
            nominal_seconds,
        )

    return RFC3339Timestamp(
        timeline_seconds=timeline_seconds,
        fraction_digits=fraction_digits,
    )


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
