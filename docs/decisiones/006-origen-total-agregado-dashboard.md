# 006 - Origen del total agregado en el tablero

## Contexto

El tablero necesita una vista agregada (cards verde/rojo) con el total de pagos procesados y fallidos del período seleccionado, además de la vista de serie de tiempo existente. Hay que decidir dónde vive ese cálculo de suma.

## Opciones consideradas

1. **Suma en el cliente**: el JS del tablero suma `processed`/`failed` de todos los buckets que ya devuelve `GET /metrics/payments?minutes=N`.
2. **Agregado en el backend**: un modo nuevo del endpoint (`?view=aggregate`) o un endpoint nuevo (`/metrics/payments/summary`) que devuelve el total ya sumado.

## Decisión

Suma en el cliente (opción 1).

## Justificación

- Cero cambios de contrato de API: el endpoint existente no se toca, por lo que ningún test existente (`tests/unit/test_api.py`, `tests/integration/*`) se ve afectado.
- Un solo `fetch` sirve para ambas vistas (serie y agregado): no hay una llamada HTTP adicional al cambiar de vista, lo que además cumple el criterio de aceptación de "no disparar una petición redundante".
- El criterio de aceptación "el total agregado coincide con la suma de los buckets de la serie de tiempo" se cumple de forma estructural: ambas vistas son proyecciones del mismo dato recibido, no dos fuentes independientes que podrían desincronizarse (por ejemplo, si el backend calculara el agregado en un momento ligeramente distinto al de la serie).
- Se descartó agregar en el backend porque excede el alcance acotado pedido explícitamente para este cambio (regla: "no un rediseño del backend de agregación"), y porque a este volumen de datos (como mucho 120 buckets por consulta) sumar en el cliente es trivial en costo computacional.

## Consecuencias

- Si en el futuro otro cliente (no el HTML del tablero) necesitara el total agregado — por ejemplo, una integración con otra herramienta — tendría que reimplementar la misma suma, ya que la API no la expone. Es un costo aceptado; se resolvería agregando el modo backend en ese momento, no antes.
- El cálculo del porcentaje de éxito/fallo también vive en el cliente, con la misma lógica de "sin datos" cuando el total es cero (ver spec `payment-metrics-api`, Requirement "Vista HTML del tablero").
