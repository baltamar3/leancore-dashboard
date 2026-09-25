# 002 - Estrategia de deduplicación

## Contexto

La cola entrega eventos con semántica at-least-once: un mismo evento puede reentregarse (timeout de ack, recuperación de pendientes) o el productor puede reintentar una publicación. El conteo agregado no debe duplicarse por ninguna de esas dos causas, y debe seguir siendo correcto si un consumidor muere justo entre aplicar el efecto y confirmarlo (ack).

## Opciones consideradas

1. **Idempotencia por `event_id` con dedupe atómico en Redis (script Lua)** — un script ejecuta, en una sola operación atómica del servidor, "si no he visto este `event_id`, márcalo como visto e incrementa el contador; si ya lo vi, no hagas nada". No hay ventana de carrera entre comprobar y contar porque ambos pasos ocurren en el mismo script.
2. **Constraint único en base de datos** — tabla `processed_events(event_id UNIQUE)`, con `INSERT ... ON CONFLICT DO NOTHING` y el incremento del contador en la misma transacción SQL. Garantía fuerte y estándar, pero requiere una base de datos relacional que hoy el sistema no tiene, solo para esto.
3. **Contadores "exactly-once" transaccionales** (ej. transacciones de Kafka, o un patrón read-process-write atómico) — la garantía más fuerte en teoría (ni siquiera depende de dedupe explícito), pero de implementación no trivial en Python en este plazo, y solo tiene sentido natural si la cola ya fuera Kafka.

## Decisión

Idempotencia por `event_id` con dedupe atómico vía script Lua en Redis (opción 1).

## Justificación

- Es atómica por construcción: no existe una ventana entre "verificar si ya se vio" y "aplicar el incremento" porque el script Lua se ejecuta de forma indivisible en el servidor de Redis. Esto elimina la clase de bug más común en dedupe hecho a mano (dos consumidores concurrentes leen "no visto" antes de que ninguno escriba).
- No introduce una segunda base de datos solo para esto: aprovecha que Redis ya es la cola elegida (ADR 001).
- El orden **aplicar → confirmar (ack)** se resuelve solo: el consumidor ejecuta el script (aplica el efecto de forma idempotente) y recién después hace `XACK`. Si muere entre ambos pasos, la entrada queda pendiente y se reprocesa; el script vuelve a ejecutarse, encuentra la llave de dedupe ya puesta, y no reincrementa — es decir, el mecanismo de dedupe es también el mecanismo que hace segura la reentrega, sin lógica adicional.
- Se descartó el constraint único en base de datos porque agrega un componente nuevo (Postgres) y el costo de una transacción ACID por evento, sin una necesidad real de auditoría transaccional para una métrica agregada de lectura (ver ADR 003).
- Se descartó exactly-once transaccional por complejidad de implementación desproporcionada al alcance y porque presupone Kafka como cola, que no fue la elegida.

## Consecuencias

- Las llaves de dedupe (`dedupe:payments:{event_id}`) tienen TTL (15 min, ver ADR 003 y `design.md`): una redelivery más tardía que ese TTL se trataría como evento nuevo. Es un trade-off aceptado y documentado, no un descuido.
- No queda un registro de auditoría de "todos los `event_id` vistos" más allá del TTL — si en el futuro se necesita trazabilidad completa por evento, esto requeriría una capa adicional (ej. log de eventos aplicados en un store durable), fuera del alcance actual.
- La lógica de dedupe queda acoplada a Redis (Lua); es la contrapartida de haber elegido Redis Streams como cola (ver Consecuencias del ADR 001).
