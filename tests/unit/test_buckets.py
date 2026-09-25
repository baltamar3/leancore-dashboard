from datetime import datetime, timezone

from src.aggregation.buckets import bucket_key, classify_event, minute_range, truncate_to_minute


def test_minute_boundary_produces_distinct_buckets():
    before = datetime(2026, 1, 1, 12, 0, 59, 900_000, tzinfo=timezone.utc)
    after = datetime(2026, 1, 1, 12, 1, 0, 100_000, tzinfo=timezone.utc)

    assert bucket_key(truncate_to_minute(before)) != bucket_key(truncate_to_minute(after))
    assert bucket_key(truncate_to_minute(before)) == "metrics:payments:202601011200"
    assert bucket_key(truncate_to_minute(after)) == "metrics:payments:202601011201"


def test_event_within_lateness_window_lands_in_its_own_bucket():
    now = datetime(2026, 1, 1, 12, 3, 0, tzinfo=timezone.utc)
    occurred_at = datetime(2026, 1, 1, 12, 0, 30, tzinfo=timezone.utc)

    placement = classify_event(
        occurred_at, now, allowed_lateness_seconds=300, bucket_retention_seconds=7200
    )

    assert placement.bucket_start == truncate_to_minute(occurred_at)
    assert placement.out_of_window is False
    assert placement.fallback is False


def test_event_beyond_lateness_but_within_retention_keeps_correct_bucket():
    now = datetime(2026, 1, 1, 12, 10, 0, tzinfo=timezone.utc)
    occurred_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)  # 600s late

    placement = classify_event(
        occurred_at, now, allowed_lateness_seconds=300, bucket_retention_seconds=7200
    )

    assert placement.bucket_start == truncate_to_minute(occurred_at)
    assert placement.out_of_window is True
    assert placement.fallback is False


def test_event_beyond_retention_falls_back_to_current_bucket():
    now = datetime(2026, 1, 1, 15, 0, 0, tzinfo=timezone.utc)
    occurred_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)  # 3h late

    placement = classify_event(
        occurred_at, now, allowed_lateness_seconds=300, bucket_retention_seconds=7200
    )

    assert placement.bucket_start == truncate_to_minute(now)
    assert placement.fallback is True


def test_future_event_due_to_clock_skew_is_treated_as_on_time():
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    occurred_at = datetime(2026, 1, 1, 12, 0, 5, tzinfo=timezone.utc)

    placement = classify_event(
        occurred_at, now, allowed_lateness_seconds=300, bucket_retention_seconds=7200
    )

    assert placement.out_of_window is False
    assert placement.fallback is False


def test_minute_range_returns_chronological_consecutive_minutes():
    end = datetime(2026, 1, 1, 12, 5, 30, tzinfo=timezone.utc)

    buckets = minute_range(end, minutes=3)

    assert buckets == [
        datetime(2026, 1, 1, 12, 3, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 12, 4, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc),
    ]
