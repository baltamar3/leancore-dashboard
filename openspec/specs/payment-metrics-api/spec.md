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
El sistema SHALL exponer una página HTML mínima que muestre los mismos datos que el endpoint de métricas, actualizándose automáticamente sin que el usuario recargue la página. La página SHALL permitir elegir la ventana de tiempo consultada y SHALL ofrecer dos formas de visualizar el mismo dato: una serie de tiempo por minuto y una vista agregada con el total del período.

#### Scenario: Actualización automática
- **WHEN** un usuario mantiene abierta la página del tablero mientras se procesan nuevos eventos
- **THEN** los conteos mostrados se actualizan en la página dentro de un intervalo corto (segundos), sin acción manual del usuario

#### Scenario: Cambiar la ventana de tiempo actualiza ambas vistas
- **WHEN** el usuario selecciona una ventana de tiempo distinta (predefinida o personalizada, entre 1 y el máximo permitido por la API)
- **THEN** la página vuelve a consultar `GET /metrics/payments` con el nuevo valor de `minutes`, y tanto la vista de serie de tiempo como la vista agregada reflejan la nueva ventana

#### Scenario: Cambiar de vista no dispara una consulta redundante
- **WHEN** el usuario alterna entre la vista de serie de tiempo y la vista agregada sin cambiar la ventana de tiempo seleccionada
- **THEN** la página reutiliza los datos ya obtenidos para esa ventana en vez de repetir la consulta al endpoint

#### Scenario: Respuesta obsoleta tras un cambio rápido de ventana
- **WHEN** el usuario cambia la ventana de tiempo mientras una consulta anterior todavía está en curso
- **THEN** la respuesta de la consulta anterior (correspondiente a una ventana que ya no está seleccionada) se descarta y no reemplaza los datos mostrados de la ventana vigente

#### Scenario: Vista agregada muestra el total del período
- **WHEN** el usuario está en la vista agregada para una ventana de tiempo dada
- **THEN** la página muestra el total de eventos `processed` y el total de eventos `failed` de esa ventana, junto con el porcentaje de éxito/fallo sobre el total, y ese total coincide exactamente con la suma de los buckets de la vista de serie de tiempo para la misma ventana

#### Scenario: Vista agregada sin eventos en la ventana
- **WHEN** el usuario está en la vista agregada y la ventana seleccionada no tiene ningún evento `processed` ni `failed`
- **THEN** la página muestra un estado "sin datos" en vez de un porcentaje calculado sobre cero

### Requirement: Degradación ante indisponibilidad del almacenamiento de métricas
El sistema SHALL responder con un error de servicio controlado si el almacenamiento de métricas no está disponible, en vez de fallar de forma no controlada o devolver datos incorrectos.

#### Scenario: Almacenamiento de métricas caído
- **WHEN** el endpoint de métricas es consultado mientras el almacenamiento subyacente no responde
- **THEN** el sistema responde con un error 503 y un mensaje indicando la indisponibilidad, sin exponer una traza interna ni datos inventados
