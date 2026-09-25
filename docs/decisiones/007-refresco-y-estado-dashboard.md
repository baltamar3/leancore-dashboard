# 007 - Mecanismo de refresco y sincronización de estado en el tablero

## Contexto

Al agregar un selector de ventana de tiempo y un toggle de vistas al tablero, hay dos problemas nuevos: (a) qué pasa con el polling existente cuando el usuario cambia el selector, incluyendo la condición de carrera de una respuesta que llega tarde; y (b) cómo se sincroniza el estado (`minutes`, `view`, datos) entre los controles y las dos vistas, sin introducir un framework de frontend nuevo sin aprobación.

## Opciones consideradas

**Refresco:**
1. Mantener el polling cada 2s existente, y al cambiar el selector disparar un fetch inmediato + reiniciar el intervalo, con un guard que descarta respuestas obsoletas.
2. Eliminar el polling y consultar solo bajo demanda (al cambiar el selector).

**Sincronización de estado:**
1. JS plano: un objeto de estado simple y funciones de render puras por vista.
2. Alpine.js vía CDN (~15KB, sin build step) para data-binding declarativo.

## Decisión

- Refresco: opción 1 (polling + fetch inmediato + guard de respuesta obsoleta).
- Estado: opción 1 (JS plano).

## Justificación

- Eliminar el polling (opción 2 de refresco) sería un retroceso: la spec `payment-metrics-api` ya exige que el tablero se actualice automáticamente sin recargar, y ese comportamiento ya estaba validado manualmente en la iteración anterior.
- La condición de carrera (cambiar el selector mientras una consulta anterior sigue en vuelo) se resuelve con un contador de secuencia (`requestSeq`) capturado antes de cada `fetch`: si al recibir la respuesta el contador global ya avanzó, se descarta sin pintar nada. Se evaluó `AbortController` (cancelar la request en curso) pero se descartó por ser complejidad adicional para el mismo resultado observable a esta escala — no hay ninguna operación costosa del lado del servidor que valga la pena cancelar activamente.
- El estado del tablero son 2-3 variables (`minutes`, `view`, la última respuesta recibida) con una interacción simple (un listener por control). Alpine.js resolvería lo mismo con menos código de "pegamento" manual, pero introduce una dependencia nueva que el usuario pidió aprobar explícitamente antes de sumar, y el tamaño del problema no la justifica.

## Consecuencias

- Cambiar de vista (serie ↔ agregado) reutiliza la última respuesta cacheada en el estado en vez de volver a consultar el endpoint, cumpliendo el criterio de aceptación de no disparar peticiones redundantes.
- Si el tablero creciera en complejidad (más controles, más vistas, estado compartido más profundo), el costo de mantener la sincronización a mano en JS plano subiría — ese sería el punto en el que reconsiderar Alpine.js (o algo similar) tendría sentido, pero no hoy.
