# Design

## Context

Ver `proposal.md` (sección "Por qué") para la motivación de negocio. Este documento cubre cómo se implementa: qué tecnología de cola se usa, cómo se garantiza idempotencia bajo entrega at-least-once y consumidores concurrentes, qué nivel de consistencia expone el tablero, y el esquema de datos/claves en Redis.

Decisiones ya cerradas con el responsable del producto (ver `docs/decisiones/` para el detalle de cada ADR):
- Cola: **Redis Streams**.
- Dedupe: **script Lua atómico en Redis** (SET NX + incremento en una sola operación).
- Consistencia: **eventual, con reconciliación por ventana de tardíos**.
- Ventana de tardíos / TTL de dedupe: **5 min de allowed lateness / 15 min de TTL para llaves de dedupe**.

## Goals / Non-Goals

**Goals:**
- Definir el esquema de claves de Redis (stream, grupo, dead-letter, dedupe, buckets) y sus tiempos de vida.
- Definir el contrato exacto del script de dedupe+agregación y el orden aplicar→confirmar.
- Definir cómo se recuperan pendientes y cómo se manejan eventos inválidos, tardíos y "poison".
- Definir el mecanismo de actualización del tablero (polling vs. SSE) para esta v1.

**Non-Goals:**
- No se diseña un mecanismo de reconciliación contra una fuente de verdad externa (no existe ledger separado que auditar en este alcance; ver `proposal.md` - No-alcance).
- No se diseña autenticación/autorización de la API.
- No se diseña el particionado/sharding para 100x volumen (se documenta como análisis en el ADR correspondiente, no se implementa).

## Decisions

### 1. Cola: Redis Streams
Un único Redis sirve como cola (stream), como store de dedupe y como store de agregación. Esto minimiza infraestructura (un solo contenedor con estado) y permite que dedupe+agregación ocurran en una operación atómica del lado del servidor (Lua), evitando una segunda base de datos solo para contadores. Alternativas consideradas y motivo de descarte: RabbitMQ (no retiene mensajes para replay, exige un segundo store), Kafka (sobredimensionado para este volumen, mayor costo operativo), SQS+LocalStack (capa de emulación adicional sin beneficio real aquí), cola en memoria (no compartible entre procesos de consumidor independientes, descartada sin ambigüedad). Detalle completo en `docs/decisiones/001-tecnologia-cola-eventos.md`.

### 2. Esquema de claves en Redis

| Propósito | Clave | Tipo | Notas |
|---|---|---|---|
| Stream principal | `stream:payments` | Stream | Entradas con campos `event_id`, `type`, `occurred_at`, `payment_id` |
| Grupo de consumidores | `cg:payments-dashboard` | Consumer group sobre `stream:payments` | Creado con `MKSTREAM` si el stream no existe |
| Dead-letter | `stream:payments:dlq` | Stream | Entradas con `original_id`, `raw_payload`, `error`, `received_at`, `attempts` |
| Dedupe por evento | `dedupe:payments:{event_id}` | String (`SET NX`) | TTL 15 min |
| Bucket por minuto | `metrics:payments:{YYYYMMDDHHmm}` | Hash con campos `processed`, `failed` | TTL deslizante 2 h (retención); ver Riesgos |

**Por qué un Hash por minuto y no dos claves de contador (`...processed:{minuto}` / `...failed:{minuto}`):** una sola clave por minuto significa una sola operación `HGETALL` para leer el bucket completo (relevante para `GET /metrics/payments?minutes=N`, que lee N buckets) y una sola clave que expirar por retención, en vez de dos. Los incrementos por campo (`HINCRBY`) siguen siendo atómicos por separado, así que no se pierde atomicidad. Se descartó un Sorted Set (claves por score) por ser un ajuste forzado: un sorted set está pensado para ranking/rango por score, no para dos contadores independientes por bucket.

**Retención de buckets (2 h) vs. ventana de tardíos (5 min):** son conceptos distintos a propósito. La ventana de tardíos es la garantía de corrección ("un evento hasta 5 min tarde cae en su minuto correcto"); la retención de buckets (2 h) es el límite de memoria y determina hasta qué `minutes=N` puede responder el endpoint. Un evento más tarde que 5 min pero dentro de las 2 h igual se suma a su bucket histórico correcto (mejor solución tardía que pérdida); solo si el bucket ya expiró (evento con más de 2 h de atraso, caso extremo) se contabiliza en el bucket actual como fallback, para cumplir la regla dura de "no perder eventos" aun a costa de exactitud temporal en ese caso límite.

### 3. Dedupe atómico (script Lua) y orden aplicar→confirmar

```lua
-- KEYS[1] = dedupe:payments:{event_id}
-- KEYS[2] = metrics:payments:{bucket}
-- ARGV[1] = dedupe TTL (seg), ARGV[2] = campo ("processed"|"failed"), ARGV[3] = bucket TTL (seg)
if redis.call('SET', KEYS[1], '1', 'NX', 'EX', ARGV[1]) then
  redis.call('HINCRBY', KEYS[2], ARGV[2], 1)
  redis.call('EXPIRE', KEYS[2], ARGV[3])
  return 1
else
  return 0
end
```

El consumidor ejecuta este script **antes** de hacer `XACK`. Si el script devuelve `1` (aplicado) o `0` (ya visto, no-op), en ambos casos el efecto en la agregación es correcto y solo entonces se confirma la entrada. Si el proceso muere entre la ejecución del script y el `XACK`, la entrada queda pendiente; al reclamarse (ver punto 5) se reintenta el mismo script, que ahora sí encuentra la llave de dedupe puesta y no reincrementa — el reprocesamiento es seguro por construcción, sin necesitar lógica adicional de "detectar que ya se aplicó": el propio script es la fuente de verdad. Detalle y alternativas en `docs/decisiones/002-estrategia-deduplicacion.md`.

### 4. Consistencia eventual con reconciliación por ventana de tardíos
Cada bucket-minuto es atómico en sí mismo (los `HINCRBY` son operaciones de un solo comando en Redis, sin condiciones de carrera), pero no hay coordinación global entre buckets ni entre consumidores: dos consumidores pueden estar aplicando eventos de distintos minutos al mismo tiempo sin sincronizarse entre sí, y un lector puede ver el bucket del minuto en curso "creciendo" entre llamadas sucesivas. Esto es aceptable porque el tablero es una vista operativa de solo lectura, no una fuente de verdad transaccional; la "reconciliación" para tardíos es el mecanismo descrito en la Decisión 2 (el evento tardío se suma a su bucket correcto en cuanto llega, no hace falta un job de reconciliación aparte). Detalle en `docs/decisiones/003-modelo-consistencia-tablero.md`.

### 5. Recuperación de pendientes
Cada consumidor, antes de leer nuevas entradas con `XREADGROUP`, ejecuta `XAUTOCLAIM` sobre el grupo con un `min-idle-time` (p. ej. 30 s) para reclamar entradas que quedaron pendientes de otro consumidor caído. El reprocesamiento de una entrada reclamada sigue el mismo camino de dedupe+ack descrito arriba, por lo que es seguro sin importar cuántas veces se reclame.

### 6. Validación, dead-letter y poison messages
Cada entrada se valida contra un modelo Pydantic (`type` ∈ {`payment.processed`, `payment.failed`}, `event_id`, `occurred_at`, `payment_id` presentes y con el tipo correcto). Si falla la validación, se copia a `stream:payments:dlq` con el motivo y se hace `XACK` inmediato en el stream principal (no bloquea la cola). Para mensajes "poison" que sí parsean pero fallan al aplicarse repetidamente, se usa `XPENDING` para conocer el contador de entregas; al superar un máximo configurable, se mueve también a `dlq` y se confirma.

### 7. Actualización del tablero: polling, no SSE (para esta v1)
Se elige **polling simple desde el HTML** (`fetch` cada 2 s a `GET /metrics/payments`) en vez de Server-Sent Events. Con un endpoint de solo lectura sobre datos que cambian a lo sumo una vez por segundo por consumidor, SSE no aporta una mejora perceptible y sí agrega complejidad (mantener conexiones abiertas, reconexión del lado del cliente). Queda como mejora incremental documentada en "Pendientes" del README si se necesitara push real.

## Risks / Trade-offs

- **Redis sin persistencia habilitada → pérdida de stream y agregados si el proceso muere.** Mitigación: habilitar `appendonly yes` (AOF) en el `docker-compose.yml` de esta v1; documentado también como el primer cuello de botella a resolver si el volumen crece (ver `docs/decisiones/004-escalamiento-100x-volumen.md`).
- **TTL de dedupe (15 min) acotado → una redelivery extremadamente tardía (más de 15 min) se trataría como evento nuevo.** Mitigación: 15 min cubre holgadamente los tiempos típicos de `XAUTOCLAIM`/reintento de este diseño; el trade-off queda documentado explícitamente en vez de ignorado.
- **Fallback de eventos más tardíos que la retención de buckets (2 h) se cuentan en el bucket "equivocado" (el actual).** Mitigación: es un caso límite explícitamente aceptado — se prioriza no perder el evento sobre la exactitud temporal exacta en ese escenario extremo; se deja instrumentado (contador de fallback) para que sea visible si ocurre.
- **Consistencia eventual entre buckets podría sorprender a un lector que espera una "foto" congelada.** Mitigación: se documenta explícitamente en el README y en la spec (`payment-metrics-api`) que el bucket en curso puede seguir creciendo entre lecturas; es el comportamiento esperado para un tablero operativo.

## Migration Plan

Proyecto greenfield: no hay estado previo que migrar. Despliegue es `docker compose up` (crea stream, grupo de consumidores y arranca N réplicas de consumidor + la API). Rollback es `docker compose down` sin pasos adicionales, dado que no hay datos que preservar entre versiones en esta v1 (ver No-alcance en `proposal.md`).
