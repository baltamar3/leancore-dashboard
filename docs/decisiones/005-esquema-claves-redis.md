# 005 - Esquema de datos y claves en Redis

## Contexto

Con Redis Streams como cola y dedupe atómico como estrategia (ADR 001, 002), hace falta definir: (a) cómo se modela el contador de un bucket-minuto, y (b) qué ventana de tolerancia para tardíos y qué tiempo de vida (TTL) tienen las llaves de dedupe y de agregación, de forma que la memoria usada quede acotada.

## Opciones consideradas

**Modelo del bucket-minuto:**
1. **Hash por minuto** (`metrics:payments:{YYYYMMDDHHmm}` con campos `processed`/`failed`, vía `HINCRBY`) — una sola clave agrupa ambos contadores de un minuto; leer un bucket completo es un `HGETALL`.
2. **Dos claves de contador por minuto** (`metrics:payments:processed:{minuto}` y `...failed:{minuto}`, vía `INCR`) — más simple conceptualmente, pero duplica el número de claves a gestionar (crear, expirar, leer) y requiere dos lecturas por bucket.
3. **Sorted set con score acumulado** — pensado para ranking/rango por score, no para dos contadores independientes por bucket; requeriría codificar tipo+minuto en el miembro, una solución forzada.

**Ventana de tardíos (allowed lateness) y TTL de dedupe:**
1. 5 min de tolerancia / TTL dedupe 15 min.
2. 1 min de tolerancia / TTL dedupe 5 min (memoria mínima, pero cualquier latencia de red o cola de reintento algo mayor cae fuera de ventana).
3. 15 min de tolerancia / TTL dedupe 30 min (más margen, más memoria y buckets "abiertos" por más tiempo).

## Decisión

- Bucket-minuto: **Hash por minuto** (opción 1).
- Allowed lateness / TTL dedupe: **5 min / 15 min** (opción 1).
- TTL de retención del bucket: **2 h**, deslizante (se renueva en cada escritura al bucket), para acotar memoria y a la vez cubrir consultas `GET /metrics/payments?minutes=N` con N razonable.

## Justificación

- El Hash por minuto reduce a la mitad el número de claves a administrar frente a dos contadores separados, y permite leer un bucket completo (`processed` + `failed`) en un solo round trip — relevante porque el endpoint de métricas lee N buckets por request.
- 5 min de allowed lateness cubre holgadamente los tiempos esperados de recuperación de pendientes (`XAUTOCLAIM` con `min-idle-time` del orden de segundos) y reintentos típicos de red, sin mantener ventanas abiertas innecesariamente largas.
- El TTL de dedupe (15 min, 3x la ventana de tardíos) da margen para que una redelivery que llegó tarde por causas de infraestructura (no solo de negocio) siga siendo detectada como duplicado, sin acumular memoria indefinidamente.
- La retención de bucket (2 h) es independiente de la ventana de tardíos a propósito: un evento puede llegar tarde (más de 5 min) y aun así sumarse correctamente a su minuto histórico mientras ese bucket no haya expirado (ver `design.md` y ADR 003) — se separan los dos conceptos (corrección temporal vs. límite de memoria) para que cada uno se pueda ajustar sin afectar al otro.

## Consecuencias

- Un evento con más de 2 h de atraso (fuera de la retención del bucket) se contabiliza como fallback en el bucket actual en vez de perderse, a costa de no caer en su minuto exacto — caso extremo, documentado y aceptado (ver `design.md` - Riesgos).
- Cambiar cualquiera de estos tres valores (lateness, TTL dedupe, retención de bucket) es un cambio de configuración, no de código ni de spec — quedan como constantes configurables desde el inicio.
