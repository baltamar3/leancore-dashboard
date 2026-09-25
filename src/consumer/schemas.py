"""Validation model for incoming payment events."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator


class PaymentEventType(str, Enum):
    """Supported payment event types; any other value is invalid."""

    PROCESSED = "payment.processed"
    FAILED = "payment.failed"


class PaymentEvent(BaseModel):
    """A validated payment event, ready to be deduplicated and aggregated."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    type: PaymentEventType
    occurred_at: datetime
    payment_id: str

    @field_validator("occurred_at")
    @classmethod
    def _ensure_utc(cls, value: datetime) -> datetime:
        """Require an explicit timezone and normalize `occurred_at` to UTC."""
        if value.tzinfo is None:
            raise ValueError("occurred_at must include timezone info (UTC)")
        return value.astimezone(timezone.utc)
