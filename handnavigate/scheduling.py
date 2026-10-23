"""Daily wall-clock schedules with explicit DST and missed-run policies.

No timer is durable by itself. The store persists next_due_at and materializes
one unique occurrence; this module only performs deterministic date arithmetic.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .contracts import ContractError

UTC = timezone.utc


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ContractError("An explicitly timezone-aware datetime is required")
    return value.astimezone(UTC)


def iso(value: datetime) -> str:
    return utc(value).isoformat(timespec="microseconds")


def parse(value: str) -> datetime:
    try:
        return utc(datetime.fromisoformat(value))
    except (ValueError, TypeError) as exc:
        raise ContractError("Invalid timezone-aware timestamp") from exc


def validate_schedule(spec: dict) -> None:
    if not isinstance(spec, dict) or set(spec) != {"name", "timezone", "time", "misfire", "grace_seconds"}:
        raise ContractError("Schedule needs name, timezone, time, misfire and grace_seconds")
    if not isinstance(spec["name"], str) or not 1 <= len(spec["name"].strip()) <= 100:
        raise ContractError("Schedule name must be 1-100 characters")
    if not isinstance(spec["time"], str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", spec["time"]):
        raise ContractError("Daily time must be HH:MM in 24-hour format")
    if not isinstance(spec["timezone"], str) or len(spec["timezone"]) > 100:
        raise ContractError("Choose an IANA timezone")
    try:
        ZoneInfo(spec["timezone"])
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ContractError("Unknown timezone; install tzdata when system zone data is unavailable") from exc
    if spec["misfire"] not in ("run_once", "skip"):
        raise ContractError("Missed-run policy must be run_once or skip")
    if type(spec["grace_seconds"]) is not int or not 0 <= spec["grace_seconds"] <= 3600:
        raise ContractError("Grace period must be an integer from 0 to 3600 seconds")


def occurrence_on(spec: dict, day: date) -> datetime | None:
    """Skip nonexistent wall times; choose only the FIRST occurrence of repeated times."""
    hour, minute = (int(x) for x in spec["time"].split(":"))
    zone = ZoneInfo(spec["timezone"])
    wall = datetime.combine(day, time(hour, minute))
    candidates = []
    for fold in (0, 1):
        candidate = wall.replace(tzinfo=zone, fold=fold).astimezone(UTC)
        if candidate.astimezone(zone).replace(tzinfo=None) == wall:
            candidates.append(candidate)
    return min(candidates) if candidates else None


def next_due(spec: dict, after: datetime) -> datetime:
    validate_schedule(spec)
    after = utc(after)
    day = after.astimezone(ZoneInfo(spec["timezone"])).date()
    for offset in range(370):
        candidate = occurrence_on(spec, day + timedelta(days=offset))
        if candidate is not None and candidate > after:
            return candidate
    raise ContractError("No supported daily occurrence found")


def latest_due(spec: dict, at: datetime) -> datetime:
    validate_schedule(spec)
    at = utc(at)
    day = at.astimezone(ZoneInfo(spec["timezone"])).date()
    for offset in range(370):
        candidate = occurrence_on(spec, day - timedelta(days=offset))
        if candidate is not None and candidate <= at:
            return candidate
    raise ContractError("No supported daily occurrence found")


def preview(spec: dict, at: datetime, count: int = 3) -> list[dict]:
    result = []
    for _ in range(count):
        at = next_due(spec, at)
        result.append({"utc": iso(at), "local": at.astimezone(ZoneInfo(spec["timezone"])).isoformat()})
    return result
