# Design

## Context

Ver `proposal.md` para la motivación. El tablero actual (`src/api/dashboard_html.py`) es una página HTML con JS embebido (sin build step) que hace polling cada 2s a `GET /metrics/payments?minutes=15` (valor fijo) y pinta una tabla. Este cambio reemplaza esa página por una versión con selector de ventana, dos vistas (serie/agregado) y Bootstrap vía CDN, sin tocar la API ni el backend de agregación.

## Goals / Non-Goals

**Goals:**
- Selector de ventana de tiempo que controla ambas vistas.
- Vista agregada (cards verde/rojo) calculada sobre el mismo dato que la serie de tiempo.
- Evitar que una respuesta obsoleta (de un fetch anterior al cambio de selector) pise el estado vigente.
- Mantener el archivo como HTML+JS plano, sin bundler ni framework nuevo.

**Non-Goals:**
- Cambiar el contrato de `GET /metrics/payments` (ver ADR 006 y 008).
- Persistir preferencias de usuario entre recargas (`localStorage`) — no pedido, se deja como posible mejora futura si se pide.
- Cualquier cambio a dedupe, agregación por minuto o consistencia (ADRs 001-005 intactos).

## Decisions

### 1. Agregado calculado en el cliente (ADR 006)
El JS del tablero suma `processed`/`failed` de todos los buckets de la respuesta ya obtenida para pintar las cards. No hay una llamada HTTP adicional para la vista agregada: ambas vistas (serie y agregado) son proyecciones de la misma respuesta cacheada en el cliente, lo que además cumple el criterio de aceptación "el total coincide con la suma de los buckets" de forma estructural (mismo dato, no una fuente distinta que podría desincronizarse).

### 2. Refresco: polling + fetch inmediato con guard de respuesta obsoleta (ADR 007)
Se mantiene el `setInterval` de 2s existente, pero:
- Al cambiar el selector de minutos, se llama a `refresh()` inmediatamente y se reinicia el `setInterval` (para no esperar hasta 2s con el valor nuevo).
- Cada llamada a `refresh()` incrementa un contador `requestSeq` local y captura su propio valor antes del `fetch`. Al recibir la respuesta, si `requestSeq` ya avanzó (otro cambio de selector disparó un fetch más nuevo mientras este estaba en vuelo), la respuesta se descarta sin pintar nada. Esto resuelve la condición de carrera pedida explícitamente en el brief sin necesitar cancelar requests (`AbortController` sería una alternativa válida pero más código para el mismo resultado a esta escala).

### 3. Rango del selector sin cambios de backend (ADR 008)
Botones predefinidos (5/15/30/60) + un input numérico "personalizado" que se habilita al seleccionarlo, con `min=1` y `max=120` en el propio HTML (`<input type="number" min="1" max="120">`), reflejando exactamente `settings.max_metrics_minutes`. El backend ya devuelve 422 si se excede, así que un valor fuera de rango (si el usuario lo fuerza saltándose el `max` del input) simplemente muestra el error tal cual lo da la API, sin lógica nueva de validación en el cliente.

### 4. Toggle de vistas y estado en JS plano
Estado en un objeto simple: `{ minutes, view, lastData }`. Dos funciones de render puras (`renderTimeSeries(data)`, `renderAggregate(data)`) que leen de `lastData` — cambiar de vista con el toggle NO dispara un fetch nuevo si `lastData` ya corresponde al `minutes` vigente (evita la petición redundante pedida en los criterios de aceptación). Un único event listener por control (selector de minutos, botón personalizado, toggle de vista).

## Risks / Trade-offs

- **El guard de `requestSeq` es una convención en memoria del cliente, no algo que el backend garantice.** Si se necesitara cancelar la request HTTP en curso (no solo ignorar su respuesta), se usaría `AbortController` — se deja fuera por ser complejidad innecesaria: descartar la respuesta ya resuelve el bug observable (parpadeo con datos de la ventana anterior).
- **El máximo de 120 minutos limita la utilidad del selector para comparar contra ventanas más largas (ej. un día completo).** Es una limitación heredada de ADR 005 (retención de bucket = 2h), documentada explícitamente en vez de ampliarse sin necesidad (ver ADR 008) — queda como mejora futura si el negocio lo pide.
- **Bootstrap por CDN introduce una dependencia de red externa para que el tablero se vea bien** (aunque no para que funcione: sin CSS el HTML sigue siendo funcional, solo sin estilos). Aceptable para un tablero interno; si se necesitara operar sin acceso a internet, se serviría Bootstrap desde un archivo estático local — no pedido, no implementado.

## Migration Plan

Sin migración de datos (cambio de UI únicamente). Se reemplaza el contenido de `DASHBOARD_HTML` en `src/api/dashboard_html.py`; el rollback es revertir ese archivo a la versión anterior, sin tocar Redis ni el resto del stack.
