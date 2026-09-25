from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator


class PaymentEventType(str, Enum):
    PROCESSED = "payment.processed"
    FAILED = "payment.failed"


class PaymentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    type: PaymentEventType
    occurred_at: datetime
    payment_id: str

    @field_validator("occurred_at")
    @classmethod
    def _ensure_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include timezone info (UTC)")
        return value.astimezone(timezone.utc)
