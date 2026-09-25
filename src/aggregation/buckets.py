"""Minute-bucket computation and late-event classification (ADR 003, 005)."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

BUCKET_KEY_PREFIX = "metrics:payments:"
BUCKET_KEY_FORMAT = "%Y%m%d%H%M"


def truncate_to_minute(moment: datetime) -> datetime:
    """Truncate `moment` to UTC with seconds and microseconds zeroed out."""
    moment_utc: datetime = moment.astimezone(timezone.utc)
    return moment_utc.replace(second=0, microsecond=0)


def bucket_key(minute_start: datetime) -> str:
    """Redis key of the minute-bucket corresponding to `minute_start`."""
    return f"{BUCKET_KEY_PREFIX}{minute_start.strftime(BUCKET_KEY_FORMAT)}"


@dataclass(frozen=True)
class EventPlacement:
    """Result of `classify_event`: which bucket an event lands in and its flags."""

    bucket_start: datetime
    out_of_window: bool
    fallback: bool


def classify_event(
    occurred_at: datetime,
    now: datetime,
    allowed_lateness_seconds: int,
    bucket_retention_seconds: int,
) -> EventPlacement:
    """Decide which minute-bucket an event belongs to (see ADR 003 and 005).

    - Within the lateness window: lands in its own minute, unflagged.
    - Later than the window but within the bucket retention: still lands
      in its own minute, but flagged as out-of-window (visibility only,
      does not affect the count).
    - Later than the retention (the original bucket would have already
      expired): applied to the current bucket as a fallback, so the
      event is never lost.
    """
    now_utc: datetime = now.astimezone(timezone.utc)
    occurred_at_utc: datetime = occurred_at.astimezone(timezone.utc)
    age_seconds: float = max((now_utc - occurred_at_utc).total_seconds(), 0.0)

    if age_seconds <= allowed_lateness_seconds:
        return EventPlacement(truncate_to_minute(occurred_at), out_of_window=False, fallback=False)

    if age_seconds <= bucket_retention_seconds:
        return EventPlacement(truncate_to_minute(occurred_at), out_of_window=True, fallback=False)

    return EventPlacement(truncate_to_minute(now), out_of_window=True, fallback=True)


def minute_range(end: datetime, minutes: int) -> list[datetime]:
    """Last `minutes` buckets, in chronological order, ending at `end`."""
    end_minute: datetime = truncate_to_minute(end)
    return [end_minute - timedelta(minutes=offset) for offset in range(minutes - 1, -1, -1)]
