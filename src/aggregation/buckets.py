from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

BUCKET_KEY_PREFIX = "metrics:payments:"
BUCKET_KEY_FORMAT = "%Y%m%d%H%M"


def truncate_to_minute(moment: datetime) -> datetime:
    moment = moment.astimezone(timezone.utc)
    return moment.replace(second=0, microsecond=0)


def bucket_key(minute_start: datetime) -> str:
    return f"{BUCKET_KEY_PREFIX}{minute_start.strftime(BUCKET_KEY_FORMAT)}"


@dataclass(frozen=True)
class EventPlacement:
    bucket_start: datetime
    out_of_window: bool
    fallback: bool


def classify_event(
    occurred_at: datetime,
    now: datetime,
    allowed_lateness_seconds: int,
    bucket_retention_seconds: int,
) -> EventPlacement:
    """Decide a que bucket-minuto pertenece un evento (ver ADR 003 y 005).

    - Dentro de la ventana de tardios: cae en su propio minuto, sin marcar.
    - Mas tarde que la ventana pero dentro de la retencion de buckets: sigue
      cayendo en su propio minuto, pero se marca como fuera de ventana
      (visibilidad, no afecta el conteo).
    - Mas tarde que la retencion (el bucket original ya se habria expirado):
      se aplica al bucket actual como fallback, para nunca perder el evento.
    """
    now_utc = now.astimezone(timezone.utc)
    occurred_at_utc = occurred_at.astimezone(timezone.utc)
    age_seconds = max((now_utc - occurred_at_utc).total_seconds(), 0.0)

    if age_seconds <= allowed_lateness_seconds:
        return EventPlacement(truncate_to_minute(occurred_at), out_of_window=False, fallback=False)

    if age_seconds <= bucket_retention_seconds:
        return EventPlacement(truncate_to_minute(occurred_at), out_of_window=True, fallback=False)

    return EventPlacement(truncate_to_minute(now), out_of_window=True, fallback=True)


def minute_range(end: datetime, minutes: int) -> list[datetime]:
    """Ultimos `minutes` buckets, en orden cronologico, terminando en `end`."""
    end_minute = truncate_to_minute(end)
    return [end_minute - timedelta(minutes=offset) for offset in range(minutes - 1, -1, -1)]
