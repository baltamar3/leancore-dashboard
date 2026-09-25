# Tasks

## 1. Layout Bootstrap y selector de ventana

- [ ] 1.1 Reestructurar `src/api/dashboard_html.py` con Bootstrap vía CDN (layout, navbar/título, contenedor responsive); verificar que `GET /` sigue devolviendo 200 y el HTML referencia el CDN de Bootstrap.
- [ ] 1.2 Agregar el selector de ventana: botones predefinidos (5/15/30/60) + opción "personalizado" con `<input type="number" min="1" max="120">`; verificar visualmente que el input personalizado se habilita solo al elegir esa opción.

## 2. Estado, refresco y guard de respuesta obsoleta

- [ ] 2.1 Implementar el objeto de estado JS (`minutes`, `view`, `lastData`) y refactorizar `refresh()` para leer `minutes` del estado en vez de un valor fijo; verificar que cambiar el selector dispara un fetch inmediato con el nuevo valor.
- [ ] 2.2 Implementar el guard de respuesta obsoleta (`requestSeq`): cada `refresh()` captura un número de secuencia y descarta la respuesta si ya no es la última solicitada; verificar manualmente forzando dos cambios rápidos de selector y confirmando que el dato final mostrado corresponde al último seleccionado, no a una respuesta anterior fuera de orden.
- [ ] 2.3 Reiniciar el `setInterval` de polling al cambiar el selector (para no esperar hasta 2s con el valor viejo); verificar que el auto-refresh sigue funcionando cada 2s con el `minutes` vigente.

## 3. Vista de serie de tiempo y vista agregada

- [ ] 3.1 Extraer el renderizado actual (tabla por minuto) a una función `renderTimeSeries(data)` que lee del estado en vez de la respuesta del fetch directamente; verificar que la vista de serie sigue mostrando los mismos datos que antes.
- [ ] 3.2 Implementar `renderAggregate(data)`: dos cards Bootstrap (verde=processed, rojo=failed) con el total sumado de los buckets y el % de éxito/fallo; mostrar "sin datos" si el total es 0; verificar visualmente con datos reales (usando `scripts/producer.py`) que el total coincide con la suma manual de los buckets de la vista de serie para la misma ventana.
- [ ] 3.3 Implementar el toggle serie/agregado que alterna `view` en el estado y llama a la función de render correspondiente sin volver a hacer fetch si `lastData` ya corresponde al `minutes` vigente; verificar (con un contador de fetches temporal en consola) que alternar vistas no genera una petición nueva.

## 4. Tests y verificación

- [ ] 4.1 Extender `tests/unit/test_api.py::test_dashboard_page_loads` para verificar que la página contiene el selector de ventana y los controles de ambas vistas (por id/atributo esperado); verificar que `make test-unit` sigue en verde.
- [ ] 4.2 Verificar que toda la suite existente (unit + integration) sigue pasando sin modificaciones: `make test`.
- [ ] 4.3 Documentar en el README un test manual paso a paso: publicar un lote con `scripts/producer.py`, comparar el total mostrado en la vista agregada contra la suma de los buckets de la vista de serie para la misma ventana, y confirmar que cambiar el selector refresca ambas vistas correctamente.

## 5. Documentación y cierre

- [ ] 5.1 Actualizar la sección de uso del README (cómo usar el selector y las dos vistas) y ampliar "Decisiones y trade-offs" con la tabla de los ADRs 006-008; verificar siguiendo los pasos documentados desde `docker compose up`.
- [ ] 5.2 Verificar que todo corre con el mismo comando de siempre (`docker compose up --build --scale consumer=3`) sin cambios adicionales de infraestructura.
