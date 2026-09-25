# 001 - Tecnología de cola de eventos

## Contexto

El servicio necesita consumir eventos `payment.processed` / `payment.failed` con varios consumidores en paralelo, tolerando reentregas (at-least-once), recuperando mensajes pendientes si un consumidor cae, y corriendo localmente con `docker compose up` sin depender de cuentas cloud.

## Opciones consideradas

1. **Redis Streams** — consumer groups nativos (`XREADGROUP`), confirmación explícita (`XACK`), recuperación de pendientes (`XPENDING`/`XAUTOCLAIM`), at-least-once por diseño. Un mismo Redis puede usarse también como store de dedupe y de agregación.
2. **RabbitMQ** — patrón competing-consumers maduro, ack/nack nativo, dead-letter exchange incorporado. No retiene mensajes para replay (se descartan al confirmarse), así que dedupe y agregación necesitan un store aparte.
3. **Kafka** — particionado, offsets y replay nativos; el estándar de facto para volumen alto. Requiere Zookeeper/KRaft, más código de administración de topics/particiones y un arranque considerablemente más pesado en docker-compose.
4. **SQS + LocalStack** — emula AWS localmente (visibility timeout como análogo a "pendiente"), sin necesidad de cuenta real. Añade una capa de emulación con particularidades propias (drift entre comportamiento real de SQS y el emulado) y tampoco resuelve por sí sola dedupe/agregación.
5. **Cola en memoria (proceso único)** — cero infraestructura. Descartada de entrada: no es compartible entre procesos de consumidor independientes (contenedores separados), por lo que no cumple el requisito de "varios consumidores en paralelo" de forma realista.

## Decisión

Redis Streams.

## Justificación

- Cumple los cuatro criterios (local sin cloud, múltiples consumidores, at-least-once, recuperación de pendientes) con primitivas nativas que se corresponden 1:1 con los casos borde pedidos (`XPENDING`, `XAUTOCLAIM`, consumer groups).
- Reduce la superficie de infraestructura: el mismo Redis sirve de cola, de store de dedupe y de store de agregación, habilitando que dedupe+conteo se resuelvan en una sola operación atómica del lado del servidor (ver ADR 002), algo que RabbitMQ y SQS no ofrecen sin un segundo componente.
- Kafka resuelve el mismo problema con garantías más fuertes de las que este volumen necesita, a costa de más piezas operativas (Zookeeper/KRaft, gestión de topics) que no se justifican para un tablero de este alcance; se retoma como opción natural si el volumen crece 100x (ver ADR 004).

## Consecuencias

- Redis pasa a ser un componente con estado crítico para el negocio (cola + agregación); su durabilidad depende de tener AOF habilitado (ver `design.md` - Riesgos).
- Si el proyecto más adelante necesita replay histórico completo, particionado por clave a gran escala, u ordenamiento estricto multi-partición, migrar a Kafka es el camino natural — Redis Streams no fue diseñado para eso a ese volumen.
- Se acopla el diseño del dedupe a Redis (scripts Lua); migrar de cola implicaría rediseñar esa pieza, no solo cambiar el cliente de conexión.
