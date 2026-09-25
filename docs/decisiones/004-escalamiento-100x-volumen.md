# 004 - Qué cambiaría con 100x más volumen

## Contexto

Este ADR no registra una decisión implementada, sino el análisis explícito de dónde se rompería primero el diseño actual si el volumen de eventos creciera ~100x, y qué se haría distinto. Se documenta ahora porque las decisiones de las ADR 001-003 fueron tomadas para el volumen actual (un tablero operativo con carga moderada), no para volumen alto, y ese trade-off debe quedar explícito en vez de implícito.

## Dónde se rompe primero el diseño actual

Redis Streams es single-threaded para la ejecución de comandos (incluidos los scripts Lua): cada evento en el diseño actual cuesta como mínimo 3 operaciones de servidor por evento (`XREADGROUP` de lectura, el script Lua de dedupe+incremento, y `XACK`), todas contra la misma instancia. Con AOF habilitado para no perder datos (ver `design.md` - Riesgos), cada escritura además implica trabajo de persistencia. En una instancia modesta, esto satura en un orden de magnitud de miles a pocas decenas de miles de eventos/segundo — **ese es el primer cuello de botella**, no la capacidad de FastAPI, ni la red, ni el número de consumidores: agregar más procesos consumidores mejora el paralelismo de *lectura y deserialización*, pero todos siguen escribiendo contra la misma instancia de Redis, que procesa una operación a la vez.

El segundo punto de presión, a ese volumen, es la memoria: las llaves de dedupe (`dedupe:payments:{event_id}`) crecen proporcionalmente a la tasa de eventos multiplicada por su TTL (15 min). A 100x el volumen actual, el conjunto de llaves de dedupe vivas en un momento dado podría pasar de miles a millones, con el overhead por-llave de Redis (no es solo el tamaño del valor, sino el overhead de cada entrada en el diccionario interno).

Los buckets de agregación (`metrics:payments:{minuto}`) **no** son un cuello de botella con el volumen: su cardinalidad depende de la ventana de tiempo retenida (2 h → ~120 llaves), no del número de eventos.

## Qué haría distinto

1. **Pre-agregación en el consumidor con flush periódico**: en vez de un `HINCRBY` por evento, cada consumidor acumula deltas en memoria (por bucket) y hace flush a Redis cada N milisegundos (ej. 200 ms) con un pipeline de pocos comandos. Esto reduce el número de operaciones contra Redis en órdenes de magnitud, a costa de un pequeño retraso adicional en la visibilidad del conteo (aceptable dado el modelo de consistencia eventual ya elegido en la ADR 003).
2. **Particionado/sharding**: mover de una sola instancia de Redis a Redis Cluster (particionando por `event_id` o `payment_id`) o migrar la cola a Kafka con particiones — a este volumen, el costo operativo de Kafka (descartado en la ADR 001 para el volumen actual) queda justificado por la necesidad real de paralelizar escritura, no solo lectura.
3. **Backpressure explícito**: los consumidores deben limitar cuántas entradas mantienen en vuelo (in-flight) antes de aplicar presión hacia atrás (dejar de pedir más con `XREADGROUP COUNT` alto), en vez de aceptar lotes ilimitados que harían crecer el pending list y el tiempo de recuperación ante una caída.
4. **Dedupe con ventana más agresiva y estructura más compacta**: reducir el TTL de dedupe al mínimo defendible según la métrica real de reintentos observada en producción (no un valor conservador "por si acaso"), y evaluar estructuras con menor overhead por entrada que una `SET` de strings individuales (por ejemplo, un filtro probabilístico tipo Bloom como primer filtro rápido, con la comprobación exacta en Redis solo para los casos límite) para acotar memoria sin perder la garantía de no duplicar.
5. **Batching en la publicación y el consumo**: leer con `XREADGROUP COUNT` más alto y procesar lotes en memoria antes de tocar Redis, en vez de procesar evento por evento.

## Decisión

No se implementa nada de esto ahora: el diseño actual (ADR 001-003) se mantiene porque está dimensionado al volumen real esperado. Este documento deja registrado el análisis para que la conversación de "cómo escalarías esto" en una revisión técnica tenga una respuesta cuantificada y no especulativa.

## Consecuencias

- Si el volumen crece de forma sostenida, el primer síntoma observable sería latencia creciente en el `EVALSHA` del script de dedupe y/o crecimiento del `XPENDING` (indicando que los consumidores no dan abasto) — son las señales a monitorear para saber cuándo ejecutar este plan, no una fecha arbitraria.
- Migrar a Kafka o a pre-agregación con flush periódico son cambios de diseño no triviales (afectan las specs de `payment-event-ingestion`); se harían como un nuevo change de OpenSpec, no como un parche sobre este.
