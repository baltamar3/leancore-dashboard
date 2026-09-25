# payment-event-ingestion Specification

## Purpose
Consumir eventos de pago desde la cola con múltiples consumidores en paralelo, garantizando que cada evento se refleje exactamente una vez en la agregación por minuto, incluso ante reentregas, caídas de consumidor y eventos tardíos o inválidos.

## Requirements

### Requirement: Consumo con grupo de consumidores
El sistema SHALL leer el stream de eventos de pago usando un grupo de consumidores de Redis Streams, permitiendo que múltiples procesos consumidores compartan la carga sin procesar la misma entrada de forma independiente.

#### Scenario: Varios consumidores activos sobre el mismo grupo
- **WHEN** hay N consumidores (N ≥ 2) leyendo del mismo grupo y llegan M eventos nuevos al stream
- **THEN** cada uno de los M eventos es entregado exactamente a un consumidor del grupo, y el conteo agregado final refleja los M eventos sin duplicados ni faltantes

### Requirement: Idempotencia ante reentregas
El sistema SHALL aplicar cada evento a la agregación como máximo una vez, identificándolo por su `event_id`, independientemente de cuántas veces sea entregado por la cola.

#### Scenario: Evento reentregado tras timeout de ack
- **WHEN** un evento con `event_id=X` ya fue aplicado a la agregación y luego es reentregado (por ejemplo, tras un timeout de ack)
- **THEN** el reprocesamiento detecta que `X` ya fue aplicado y NO incrementa nuevamente los contadores

#### Scenario: Evento duplicado producido por el emisor
- **WHEN** el productor publica dos veces el mismo `event_id` (reintento de publicación, no de la cola)
- **THEN** el conteo agregado solo refleja una ocurrencia de ese evento

### Requirement: Orden aplicar-antes-que-confirmar
El sistema SHALL confirmar (ack) una entrada del stream únicamente después de que su efecto en la agregación fue aplicado y persistido con éxito.

#### Scenario: Consumidor cae entre aplicar y confirmar
- **WHEN** un consumidor aplica el efecto de un evento en la agregación pero el proceso termina (crash) antes de hacer ack
- **THEN** la entrada permanece pendiente en el stream y, al ser reclamada por otro consumidor, se reprocesa de forma idempotente (ver Idempotencia ante reentregas) y finalmente queda confirmada

### Requirement: Recuperación de mensajes pendientes
El sistema SHALL reclamar automáticamente las entradas que quedaron pendientes (entregadas pero no confirmadas) por más de un tiempo de inactividad configurable, y asignarlas a un consumidor activo para su reprocesamiento.

#### Scenario: Consumidor cae y su pendiente se reclama
- **WHEN** un consumidor recibe una entrada y deja de responder (caída de proceso) sin confirmarla, y transcurre el tiempo mínimo de inactividad configurado
- **THEN** otro consumidor activo reclama esa entrada y la procesa hasta confirmarla

### Requirement: Agregación por minuto en tiempo de evento (UTC)
El sistema SHALL agregar los conteos de `payment.processed` y `payment.failed` en buckets de un minuto, usando la marca de tiempo del evento (`occurred_at`, UTC) y no el momento en que fue procesado.

#### Scenario: Evento fuera de orden dentro de la ventana de tolerancia
- **WHEN** llega un evento cuyo `occurred_at` corresponde a un minuto anterior al minuto de procesamiento actual, y la diferencia es menor o igual a la ventana de tolerancia configurada (allowed lateness)
- **THEN** el evento se suma al bucket correspondiente a su `occurred_at`, no al bucket del momento de procesamiento

#### Scenario: Evento más tardío que la ventana de tolerancia pero dentro de la retención de buckets
- **WHEN** llega un evento cuyo `occurred_at` excede la ventana de tolerancia configurada, pero el bucket de ese minuto aún existe (no ha expirado su retención)
- **THEN** el evento se suma igualmente a su bucket histórico correcto, y el sistema registra que ocurrió fuera de la ventana garantizada (para visibilidad, sin bloquear el procesamiento)

#### Scenario: Evento cuyo bucket histórico ya expiró
- **WHEN** llega un evento cuyo bucket de `occurred_at` ya fue expulsado por retención
- **THEN** el sistema NO descarta el evento; lo suma al bucket del minuto de procesamiento actual y lo marca como conteo de respaldo (fallback), para no perder el evento aunque no quede en su minuto exacto

#### Scenario: Frontera de minuto (cambio de bucket)
- **WHEN** dos eventos tienen `occurred_at` en el mismo segundo de frontera pero pertenecen a minutos distintos (ej. `12:00:59.900` y `12:01:00.100`)
- **THEN** cada uno se agrega al bucket de su propio minuto en UTC, sin mezclarse

### Requirement: Validación y cuarentena de eventos inválidos
El sistema SHALL validar la forma de cada evento entrante y, si no cumple el esquema esperado o su `type` es desconocido, SHALL enviarlo a un flujo de dead-letter sin bloquear el procesamiento del resto de la cola.

#### Scenario: Evento malformado
- **WHEN** llega una entrada que no puede parsearse contra el esquema esperado (campos faltantes o de tipo incorrecto)
- **THEN** la entrada se confirma (ack) para no bloquear el stream, se copia al dead-letter stream con el motivo del error, y NO se refleja en los contadores de negocio

#### Scenario: Tipo de evento desconocido
- **WHEN** llega un evento válido en forma pero con `type` distinto de `payment.processed` o `payment.failed`
- **THEN** la entrada se envía al dead-letter stream y no afecta los contadores

### Requirement: Límite de reintentos para mensajes poison
El sistema SHALL mover al dead-letter cualquier entrada que supere un número máximo de intentos de procesamiento, para evitar que un mensaje "envenenado" bloquee indefinidamente el reclamo de pendientes.

#### Scenario: Entrada que falla repetidamente
- **WHEN** una entrada es reclamada y reprocesada más veces que el máximo de reintentos configurado sin poder aplicarse con éxito
- **THEN** se mueve al dead-letter stream con el conteo de intentos y se confirma (ack) en el stream principal

### Requirement: Cierre ordenado del consumidor
El sistema SHALL permitir que un consumidor termine su ejecución de forma ordenada ante una señal de apagado, completando el procesamiento y confirmación de las entradas ya tomadas antes de salir, sin tomar entradas nuevas.

#### Scenario: Señal de apagado durante procesamiento
- **WHEN** el consumidor recibe una señal de terminación (SIGTERM) mientras tiene entradas en curso
- **THEN** termina de aplicar y confirmar las entradas en curso, deja de leer nuevas entradas, y cierra su conexión antes de finalizar el proceso

### Requirement: Degradación ante indisponibilidad de la cola
El sistema SHALL reintentar la conexión con backoff cuando la cola no esté disponible, sin terminar el proceso del consumidor, y SHALL retomar el procesamiento normal cuando la conexión se restablezca.

#### Scenario: Cola temporalmente caída
- **WHEN** la cola (Redis) no responde durante un intervalo de tiempo
- **THEN** el consumidor reintenta la conexión periódicamente en vez de terminar, y al reconectar retoma el consumo (incluyendo pendientes) sin intervención manual
