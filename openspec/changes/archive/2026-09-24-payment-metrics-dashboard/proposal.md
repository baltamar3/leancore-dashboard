# Propuesta

## Por qué

El equipo de Pagos de LeanCore no tiene visibilidad casi en tiempo real del volumen de pagos exitosos y fallidos: hoy esa información solo se puede reconstruir después del hecho, revisando logs o la base de datos transaccional, lo que retrasa la detección de incidentes (por ejemplo, un pico repentino de `payment.failed`). Se necesita un tablero operativo que refleje el estado agregado por minuto a partir de los eventos que ya se publican en la cola de pagos.

El reto técnico central es **concurrencia vs. consistencia**: varios consumidores deben poder procesar la cola en paralelo (para escalar y tolerar caídas) sin que eso implique duplicar ni perder conteos, incluso ante reentregas, caídas de un consumidor a mitad de proceso, o eventos tardíos y malformados. No existe una implementación previa; este cambio construye el servicio completo desde cero.

## Qué cambia

- Se introduce un **consumidor** que lee eventos de pago desde una cola (tecnología a decidir en Fase 2 — ver `design.md`), valida su forma con Pydantic, y aplica **dedupe idempotente** antes de agregarlos.
- Se introduce una **agregación por minuto** (bucket por tiempo del evento, en UTC) de conteos `processed` / `failed`, con manejo explícito de tardíos (allowed lateness) y fuera de orden.
- Se introduce una **API FastAPI** de solo lectura: `GET /metrics/payments?minutes=N` (JSON) y una página HTML mínima que hace polling o SSE sobre esos datos.
- Se introduce un **dead-letter** para eventos malformados o de tipo desconocido, de forma que no bloqueen la cola principal.
- Se introduce un **generador de eventos** (`scripts/producer.py`) capaz de duplicar, desordenar e inyectar eventos malformados, para demostrar el comportamiento ante esos casos.
- Se documentan las decisiones de concurrencia/consistencia como ADRs (`docs/decisiones/`), incluyendo qué se descartó y por qué.

No hay componentes existentes que se modifiquen (proyecto nuevo); todo es capacidad nueva.

## Capacidades

### Capacidades nuevas
- `payment-event-ingestion`: consumo de eventos desde la cola, validación, dedupe idempotente, agregación por minuto (bucket en tiempo de evento, UTC), manejo de tardíos, eventos malformados (dead-letter), recuperación de mensajes pendientes tras caída de un consumidor, y cierre ordenado (graceful shutdown).
- `payment-metrics-api`: exposición de las métricas agregadas vía `GET /metrics/payments?minutes=N` y una vista HTML mínima con actualización casi en tiempo real; define qué puede ver un lector mientras el consumidor escribe (consistencia de lectura).

### Capacidades modificadas
_(ninguna — proyecto greenfield)_

## Impacto

- **Código**: todo nuevo — `src/api`, `src/consumer`, `src/aggregation`, `src/config`, `scripts/producer.py`, `tests/`.
- **Infraestructura**: nuevo `docker-compose.yml` que levanta la cola elegida, la API y N réplicas de consumidor; sin dependencias cloud.
- **Dependencias externas**: ninguna cuenta o servicio cloud; todo debe correr con `docker compose up`.
- **Interfaces**: se expone un único contrato HTTP nuevo (`GET /metrics/payments`); no hay contratos previos que romper.

## Alcance

- Consumidor(es) leyendo `payment.processed` / `payment.failed` desde una cola local (Docker), con soporte para **N consumidores en paralelo** sobre el mismo grupo lógico.
- Dedupe por `event_id` para garantizar que una reentrega (at-least-once) no duplique el conteo.
- Agregación por minuto usando **tiempo del evento** (no tiempo de procesamiento), en UTC, con ventana de tolerancia para tardíos a definir en Fase 2.
- Recuperación de pendientes cuando un consumidor muere entre "aplicar" y "confirmar" (ack).
- Dead-letter para eventos inválidos/desconocidos, sin bloquear el resto de la cola.
- API de solo lectura para el tablero + página HTML mínima (polling o SSE).
- Productor de prueba con flags para duplicar, desordenar e inyectar malformados.
- Tests que demuestren: idempotencia, concurrencia sin pérdida/duplicado, recuperación de pendientes, tardíos, inválidos.
- Documentación completa: README (arquitectura, cómo correr, decisiones y trade-offs, uso de IA, pendientes) + ADRs.

## No-alcance

- Autenticación, autorización o HTTPS en la API (v1 de uso interno; se añadirá cuando se exponga fuera de la red interna).
- Persistencia histórica de métricas más allá de una ventana acotada y configurable (no es un data warehouse ni un ledger contable).
- Procesamiento de montos, monedas, reembolsos u otra lógica de negocio de pagos: solo se cuentan eventos por tipo y minuto.
- Multi-tenancy o soporte para métricas distintas a `payment.processed`/`payment.failed`.
- Despliegue a la nube, IaC, CI/CD productivo.
- UI elaborada (frameworks de frontend, diseño visual): solo HTML mínimo funcional.
- Garantías de "exactly-once" a nivel de infraestructura (Kafka transaccional, etc.); se resuelve con idempotencia a nivel de aplicación (ver `design.md`).
- Observabilidad/alerting de nivel productivo (métricas de Prometheus, tracing); puede mencionarse como pendiente.

## Supuestos a confirmar

1. **Payload del evento**: asumo un JSON mínimo tipo `{"event_id": "uuid", "type": "payment.processed"|"payment.failed", "occurred_at": "ISO8601 UTC", "payment_id": "..."}` — sin monto, porque el tablero solo cuenta eventos. ¿Correcto, o necesitas que el payload incluya más campos (monto, moneda, merchant)?
2. **Demostración de concurrencia**: asumo que basta con levantar 2–3 réplicas del consumidor vía `docker compose up --scale consumer=3` para demostrar que no hay duplicado/pérdida. ¿Es suficiente o esperas un mecanismo de prueba más elaborado (chaos testing, etc.)?
3. **Persistencia entre reinicios**: asumo que las métricas **no** necesitan sobrevivir a un reinicio completo del stack en esta v1 — es un tablero operativo de corto plazo, no un sistema de reporting histórico — así que el TTL de buckets y llaves de dedupe se documenta pero no se exige durabilidad a largo plazo. ¿De acuerdo?
4. **Alcance del "casi tiempo real"**: asumo que un refresco cada 1–2 segundos (polling) o SSE con push al agregar es aceptable; no hay un SLA de latencia explícito. ¿Confirmas o tienes un número en mente (ej. <500ms)?
5. **Idioma de commits**: confirmo que el código, nombres de variables y mensajes de commit van en inglés, y toda la documentación (README, specs, ADRs) en español, como indicaste.

Estos supuestos, junto con las decisiones técnicas obligatorias (cola, dedupe, consistencia, escalamiento), se cierran formalmente en `design.md` (Fase 2) con opciones y tu elección explícita.
