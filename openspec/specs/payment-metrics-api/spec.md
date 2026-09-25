# payment-metrics-api Specification

## Purpose
Exponer las métricas agregadas de pagos por minuto a través de un endpoint JSON de solo lectura y una vista HTML mínima que se actualiza casi en tiempo real, sin exponer estados parciales o inconsistentes de un mismo bucket.

## Requirements

### Requirement: Endpoint de métricas por minuto
El sistema SHALL exponer `GET /metrics/payments?minutes=N` que devuelve, para cada uno de los últimos N minutos completos, el conteo de eventos `processed` y `failed` correspondientes a ese minuto (en UTC).

#### Scenario: Consulta con ventana válida
- **WHEN** un cliente solicita `GET /metrics/payments?minutes=10`
- **THEN** la respuesta incluye un elemento por cada uno de los últimos 10 minutos (en orden cronológico), cada uno con su timestamp de inicio de minuto (UTC) y los conteos `processed`/`failed` de ese minuto (0 si no hubo eventos)

#### Scenario: Parámetro fuera de rango o inválido
- **WHEN** un cliente solicita `GET /metrics/payments?minutes=0`, un valor negativo, no numérico, o mayor al máximo permitido
- **THEN** el sistema responde con un error 422 indicando el rango válido, sin intentar construir una respuesta parcial

#### Scenario: Parámetro omitido
- **WHEN** un cliente solicita `GET /metrics/payments` sin el parámetro `minutes`
- **THEN** el sistema usa un valor por defecto documentado (no falla)

### Requirement: Lecturas consistentes por bucket
El sistema SHALL garantizar que cada bucket de minuto devuelto en una lectura refleje un estado internamente consistente (nunca una escritura a medio aplicar dentro de ese minuto), aunque distintos buckets puedan reflejar distinto grado de actualización entre sí.

#### Scenario: Lectura durante escritura concurrente
- **WHEN** un cliente lee las métricas mientras uno o más consumidores están incrementando contadores del minuto en curso
- **THEN** el valor leído para cualquier bucket dado es siempre el resultado de una o más operaciones de incremento completas (nunca un valor corrupto o parcial), aunque el bucket en curso pueda seguir creciendo en lecturas posteriores

### Requirement: Vista HTML del tablero
El sistema SHALL exponer una página HTML mínima que muestre los mismos datos que el endpoint de métricas, actualizándose automáticamente sin que el usuario recargue la página.

#### Scenario: Actualización automática
- **WHEN** un usuario mantiene abierta la página del tablero mientras se procesan nuevos eventos
- **THEN** los conteos mostrados se actualizan en la página dentro de un intervalo corto (segundos), sin acción manual del usuario

### Requirement: Degradación ante indisponibilidad del almacenamiento de métricas
El sistema SHALL responder con un error de servicio controlado si el almacenamiento de métricas no está disponible, en vez de fallar de forma no controlada o devolver datos incorrectos.

#### Scenario: Almacenamiento de métricas caído
- **WHEN** el endpoint de métricas es consultado mientras el almacenamiento subyacente no responde
- **THEN** el sistema responde con un error 503 y un mensaje indicando la indisponibilidad, sin exponer una traza interna ni datos inventados
