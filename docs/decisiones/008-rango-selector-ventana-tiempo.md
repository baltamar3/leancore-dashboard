# 008 - Rango del selector de ventana de tiempo

## Contexto

El selector de ventana de tiempo necesita un rango razonable de minutos hacia atrás. La petición original sugería 1-1440 minutos (24 horas) como ejemplo, pero eso excede la configuración actual del backend: `max_metrics_minutes=120` (límite que ya valida la API con un 422) y `bucket_retention_seconds=7200` (2 horas — ver ADR 005), que acota cuánto tiempo se retienen los buckets en Redis.

## Opciones consideradas

1. **Predefinidos (5/15/30/60) + personalizado hasta 120**: sin cambios de backend; el input refleja exactamente el límite que la API ya impone.
2. **Predefinidos (5/15/30/60/1440) + personalizado hasta 1440**: requiere subir `max_metrics_minutes` y `bucket_retention_seconds` a 24h, con más memoria retenida en Redis por bucket y un addendum al ADR 005.

## Decisión

Opción 1: predefinidos (5/15/30/60) + personalizado hasta 120, sin cambios de configuración.

## Justificación

- Este cambio se acotó explícitamente a una extensión de UI ("no un rediseño del backend de agregación", "no toques el mecanismo... salvo que sea estrictamente necesario"). Subir la retención de buckets no es estrictamente necesario para resolver el problema pedido (elegir la ventana y ver un agregado) — es una ampliación de alcance distinta, con su propio trade-off de memoria que merece su propia decisión informada, no colarse como efecto secundario de un selector de UI.
- Mantener el límite en 120 significa que el selector nunca puede pedir algo que el backend no pueda responder correctamente: no hay riesgo de que "1440" muestre silenciosamente ceros para las últimas ~22 horas por buckets ya expirados, lo cual sería confuso para quien mira el tablero (parecería "no hubo pagos" en vez de "esos datos ya no se retienen").
- Se señaló esta tensión explícitamente al usuario (en vez de asumir 1440 sin más) antes de decidir, por ser un caso donde la propuesta original chocaba con una decisión de diseño ya tomada (ADR 005).

## Consecuencias

- El selector no permite comparar contra ventanas de más de 2 horas. Si el negocio pide esa capacidad más adelante, el cambio correcto es ampliar `bucket_retention_seconds` y `max_metrics_minutes` juntos (como se documentó en la opción descartada), evaluando el costo de memoria en Redis a ese momento — no es una limitación de la UI, es una limitación de retención que ya existía antes de este cambio.
- El input personalizado usa `min=1 max=120` en el propio HTML como ayuda de UX; la validación real sigue siendo la que ya hace la API (`ge=1, le=max_metrics_minutes`), sin duplicar lógica de validación en el cliente.
