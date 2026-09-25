from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.consumer.schemas import PaymentEvent, PaymentEventType


def test_valid_processed_event_parses():
    event = PaymentEvent(
        event_id="evt-1",
        type="payment.processed",
        occurred_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        payment_id="pay-1",
    )

    assert event.type is PaymentEventType.PROCESSED
    assert event.occurred_at.tzinfo is not None


def test_missing_field_fails_validation():
    with pytest.raises(ValidationError):
        PaymentEvent(
            event_id="evt-1",
            type="payment.processed",
            payment_id="pay-1",
        )


def test_wrong_field_type_fails_validation():
    with pytest.raises(ValidationError):
        PaymentEvent(
            event_id="evt-1",
            type="payment.processed",
            occurred_at="not-a-date",
            payment_id="pay-1",
        )


def test_unknown_event_type_fails_validation():
    with pytest.raises(ValidationError):
        PaymentEvent(
            event_id="evt-1",
            type="payment.refunded",
            occurred_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            payment_id="pay-1",
        )


def test_naive_datetime_is_rejected():
    with pytest.raises(ValidationError):
        PaymentEvent(
            event_id="evt-1",
            type="payment.processed",
            occurred_at=datetime(2026, 1, 1, 12, 0, 0),
            payment_id="pay-1",
        )
