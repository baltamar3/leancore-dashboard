# Propuesta

## Por qué

El tablero actual (`GET /`) muestra una única vista de serie de tiempo con una ventana fija de 15 minutos hardcodeada en el HTML. El equipo de Pagos necesita poder elegir cuánto tiempo hacia atrás mirar (por ejemplo, para comparar el último minuto contra la última hora) y, además, quiere ver de un vistazo el total agregado del período — cuántos pagos exitosos y fallidos hubo en total, sin tener que sumar mentalmente los buckets de la serie de tiempo.

## Qué cambia

- El tablero HTML incorpora un **selector de ventana de tiempo** (minutos hacia atrás) que reemplaza el valor fijo actual.
- Se agrega una **vista agregada** (cards estilo Datadog: total procesados en verde, total fallidos en rojo, con % de éxito/fallo) como alternativa a la vista de serie de tiempo existente, con un toggle entre ambas.
- Se adopta **Bootstrap vía CDN** (sin bundler) para el layout, los cards y los controles, manteniendo el HTML simple de un solo archivo como hasta ahora.
- Cambio **puramente de UI** sobre la capability existente `payment-metrics-api`: no se toca el mecanismo de dedupe, agregación por minuto, ni consistencia (ADRs 001-005 siguen vigentes sin cambios).

## Capacidades

### Capacidades nuevas
_(ninguna)_

### Capacidades modificadas
- `payment-metrics-api`: el requirement "Vista HTML del tablero" se extiende para cubrir el selector de ventana, las dos vistas (serie/agregado) y su sincronización.

## Impacto

- **Código**: exclusivamente `src/api/dashboard_html.py` (el HTML/JS embebido del tablero). Sin cambios en `src/aggregation/`, `src/consumer/`, `src/api/app.py` ni `src/config/settings.py`.
- **API**: sin cambios de contrato — el agregado se calcula en el cliente sumando los buckets del mismo endpoint existente, y el límite superior de `minutes` (120) no cambia.
- **Tests existentes**: no se ven afectados (`tests/unit/test_api.py`, `tests/integration/*` siguen pasando sin modificación).

## Alcance

- Selector de ventana de tiempo (predefinidos + opción personalizada) en el tablero.
- Vista agregada (dos cards, verde/rojo, con totales y %) calculada sobre el mismo período que la serie de tiempo.
- Toggle entre vista serie de tiempo y vista agregada, conservando el minuto seleccionado al cambiar de vista.
- Manejo explícito de condición de carrera: si el usuario cambia el selector mientras hay una consulta en curso, la respuesta obsoleta no debe pisar el estado vigente.
- Migración del HTML/JS actual a Bootstrap (CDN) para el layout y los componentes visuales.
- Verificación manual (o test) de que el total agregado coincide exactamente con la suma de los buckets de la serie de tiempo para el mismo período.
- README: sección de uso del selector/vistas, y ampliación de "Decisiones y trade-offs" con esta iteración.

## No-alcance

- No se toca el mecanismo de dedupe, agregación por minuto, ni el modelo de consistencia (ADRs 001-005 sin cambios).
- No se introduce un framework de frontend nuevo (React/Vue/Alpine) sin aprobación explícita — ver Decisión 4.
- No se persiste la preferencia del usuario (ventana/vista elegida) entre recargas de página — cada carga arranca en el estado por defecto (ver Supuesto 4).
- No se agregan más métricas ni tipos de evento — sigue siendo `payment.processed`/`payment.failed` únicamente.
- No se rediseña la API más allá del ajuste puntual (si aplica) del límite superior de `minutes`.

## Supuestos a confirmar

1. **Forma de la respuesta del endpoint**: se asume que `GET /metrics/payments?minutes=N` sigue devolviendo la misma lista de buckets que hoy (sin un modo `?view=aggregate` en el backend) — ver Decisión 1.
2. **Cálculo del % de éxito/fallo**: `processed / (processed + failed)` sobre el total del período; si el total es 0 (sin eventos en la ventana), el card debe mostrar "sin datos" en vez de una división por cero o un porcentaje engañoso (ej. 0% en rojo cuando en realidad no hubo ningún evento). ¿Correcto?
3. **Valor por defecto al cargar la página**: sigue siendo `settings.default_metrics_minutes` (15 minutos), igual que hoy.
4. **Sin persistencia de preferencia de usuario**: no se guarda en `localStorage` la última ventana/vista elegida — cada carga de página vuelve al default. Si prefieres que sí se recuerde entre recargas, es un cambio menor pero lo confirmo antes de implementar.
5. **Bootstrap por CDN sin integridad SRI estricta** ni paso de build, consistente con "HTML simple, sin bundler" que pediste.

## Decisiones (cerradas)

1. **Origen del total agregado**: se calcula en el cliente, sumando los buckets que ya devuelve `GET /metrics/payments?minutes=N`. Sin cambios de contrato de API. Ver ADR 006.
2. **Mecanismo de refresco**: se mantiene el polling existente (cada 2s); al cambiar el selector se dispara un fetch inmediato y se reinicia el intervalo, con un guard de respuesta obsoleta (se descarta cualquier respuesta cuyo `minutes` no coincida con el selector vigente al momento de recibirla). Ver ADR 007.
3. **Rango del selector**: predefinidos (5/15/30/60) + opción personalizada, limitada al máximo ya vigente en el backend (`max_metrics_minutes=120`, 2 h de retención). Sin cambios de configuración. Ver ADR 008.
4. **Sincronización de estado**: JS plano (sin framework nuevo), con un objeto de estado simple (`minutes`, `view`, última respuesta cacheada) y una función de render por vista. Ver ADR 007.
