# Spec Delta

## MODIFIED Requirements

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
