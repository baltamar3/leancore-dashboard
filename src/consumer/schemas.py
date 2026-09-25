"""Modelo de validación de eventos de pago entrantes."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator


class PaymentEventType(str, Enum):
    """Tipos de evento de pago soportados; cualquier otro valor es inválido."""

    PROCESSED = "payment.processed"
    FAILED = "payment.failed"


class PaymentEvent(BaseModel):
    """Evento de pago validado, listo para deduplicar y agregar."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    type: PaymentEventType
    occurred_at: datetime
    payment_id: str

    @field_validator("occurred_at")
    @classmethod
    def _ensure_utc(cls, value: datetime) -> datetime:
        """Exige timezone explícito y normaliza `occurred_at` a UTC."""
        if value.tzinfo is None:
            raise ValueError("occurred_at must include timezone info (UTC)")
        return value.astimezone(timezone.utc)
