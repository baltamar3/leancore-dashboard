# 003 - Modelo de consistencia del tablero

## Contexto

Varios consumidores escriben en paralelo a la agregación por minuto mientras la API lee esos mismos datos para el tablero. Hay que decidir qué garantías de consistencia se ofrecen entre escrituras concurrentes y lecturas, y cómo se reconcilian eventos tardíos o fuera de orden.

## Opciones consideradas

1. **Consistencia fuerte con locks/transacciones globales** — serializar todas las escrituras (por ejemplo, con un lock global o una transacción que abarque todos los buckets afectados) para que en todo momento exista una "foto" perfectamente sincronizada del tablero completo.
2. **Consistencia eventual con reconciliación por ventana de tardíos** — cada bucket-minuto se actualiza de forma atómica de manera independiente (sin lock global entre buckets ni entre consumidores); los eventos tardíos se reconcilian sumándose directamente a su bucket histórico correcto en cuanto llegan, dentro de una ventana de tolerancia definida (allowed lateness).

## Decisión

Consistencia eventual con reconciliación por ventana de tardíos (opción 2).

## Justificación

- El tablero es una métrica agregada de **lectura operativa**, no un ledger financiero ni una fuente de verdad transaccional: no hay un requisito de negocio que exija que todos los buckets estén "congelados" en el mismo instante exacto para ser útiles.
- Un lock/transacción global serializaría a todos los consumidores entre sí para escribir, anulando el paralelismo que es justamente el punto de tener varios consumidores (ver ADR 001) — el costo de la opción 1 es alto y el beneficio, nulo para este caso de uso.
- Cada bucket individual sí es atómico (los incrementos son operaciones de un solo comando en Redis), así que la propiedad importante — nunca ver un conteo "a medio escribir" dentro de un mismo minuto — se cumple sin necesitar coordinación global.
- La "reconciliación" de tardíos no requiere un job aparte: en este diseño, un evento tardío simplemente se suma a su bucket correcto en el momento en que se procesa (ver `design.md`, Decisión 2), porque los buckets no se cierran ni se "finalizan" — permanecen abiertos a incrementos mientras estén dentro de su retención.

## Consecuencias

- Un lector puede observar el bucket del minuto en curso "creciendo" entre dos llamadas sucesivas al endpoint. Esto se documenta explícitamente como comportamiento esperado, no como un bug (ver spec `payment-metrics-api`).
- No existe una fuente de verdad externa contra la cual reconciliar en caso de duda (no hay un ledger separado en el alcance actual); si en el futuro se necesitara auditar el tablero contra el sistema transaccional de pagos, habría que añadir un proceso de reconciliación batch aparte — queda documentado como pendiente.
- La corrección temporal exacta de un evento (que caiga en su minuto correcto) tiene un límite práctico: la ventana de tardíos (5 min) y, como caso extremo, la retención del bucket (2 h). Fuera de esos límites se prioriza no perder el evento sobre la exactitud del minuto exacto (ver `design.md` - Riesgos).
