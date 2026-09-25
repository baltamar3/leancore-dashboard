# ROL
Eres mi copiloto senior de backend e infraestructura. Vamos a construir una app para LeanCore

# REGLAS DE TRABAJO (obligatorias)
1. Metodología OpenSpec (spec-driven development): NO escribas código hasta que la propuesta, el diseño, los casos borde, las tareas y las decisiones estén documentados y yo los apruebe. Usa los flujos/comandos de OpenSpec que `openspec init` haya configurado para esta herramienta (propuesta → specs/deltas → tareas → implementar → archivar). Todo debe quedar versionado en el repo.
2. Tú propones, yo decido. Cada vez que haya una decisión técnica relevante, preséntame 2–3 opciones con pros, contras y una recomendación breve, y ESPERA mi elección antes de seguir. Nunca decidas por mí.
3. Registra cada decisión como ADR corto en `docs/decisiones/NNN-titulo.md` con: contexto, opciones consideradas, decisión, justificación, consecuencias. Incluye también las opciones que TÚ (la IA) propusiste y las que descartamos, y por qué.
4. Explícame brevemente el "por qué" de cada pieza importante que escribas, en lenguaje que yo pueda repetir en una entrevista.
5. Límite de tiempo: máximo ~4 horas. Prioriza criterio sobre completitud. Si algo no cabe, no lo implementes a medias: documéntalo en el README en "Pendientes" con qué faltó y por qué lo seguiría haciendo. Prefiero una solución acotada y bien pensada a una completa sin criterio.
6. Idioma: documentación, README, specs y ADRs en español. Código, nombres de variables y commits en inglés.
7. Trabaja en fases y detente al final de cada una para que yo valide.

# EL EJERCICIO
Construir un servicio que consuma eventos desde una cola y alimente un tablero simple que refleje el estado agregado en tiempo casi real.

Caso concreto: eventos `payment.processed` y `payment.failed` llegan a la cola; el tablero muestra el conteo de pagos exitosos y fallidos **por minuto**. Basta un endpoint JSON que se actualice o una página simple (sin UI elaborada).

Problema resolver: **concurrencia vs. consistencia**. Puede haber varios consumidores procesando en paralelo; el tablero debe reflejar el estado real **sin duplicar ni perder eventos**. Debo documentar explícitamente qué trade-off elegí (p. ej., consistencia fuerte con locks/transacciones vs. consistencia eventual con reconciliación) y por qué para este caso.

# STACK
- Lenguaje: **Python 3.10+**. Documenta en una nota que elegí Python por dominio del lenguaje y cómo se traduciría la solución a Go.)
- API/tablero: FastAPI. Tablero: endpoint `GET /metrics/payments?minutes=N` y una página HTML mínima que haga polling o use SSE.
- Cola: preséntame primero las opciones (Redis Streams con consumer groups, RabbitMQ, SQS/LocalStack, Kafka, cola en memoria) con trade-offs y recomienda. Criterios: que se pueda correr localmente con `docker compose up` sin cuentas cloud, que soporte varios consumidores, reentrega (at-least-once) y recuperación de mensajes pendientes. Mi inclinación inicial es Redis Streams, pero quiero ver la comparación antes de decidir.
- Pruebas: pytest (+ pytest-asyncio). Empaquetado con `pyproject.toml`, `Makefile` y `docker-compose.yml`. Lint/format con ruff.

# DECISIONES QUE DEBO JUSTIFICAR (mínimo, deben quedar en "Decisiones y trade-offs")
1. Qué tecnología de cola usé y por qué.
2. Cómo evito que un evento duplicado (por reentrega) dañe el conteo. Analiza al menos: idempotencia por `event_id` con dedupe atómico (p. ej., `SET NX` o script Lua que deduplique y agregue en una sola operación atómica) vs. constraint único en base de datos vs. contadores "exactly-once" por transacción. Cubre el orden ack-después-de-aplicar, y qué pasa si el consumidor muere entre aplicar y confirmar.
3. Por qué consistencia fuerte o eventual para ESTE tablero (es una métrica agregada de lectura, no un ledger financiero: justifica el nivel de consistencia y qué mecanismo de reconciliación existiría).
4. Qué haría distinto con 100 veces más volumen (particionado/sharding por clave, batching/pipelining, pre-agregación en el consumidor con flush periódico, Kafka, dedupe con ventana TTL, backpressure, etc.). Cuantifica de forma aproximada dónde se rompería primero el diseño actual.

# CASOS BORDE A CONSIDERAR EN LA SPEC
- Eventos duplicados por reentrega y por productor que reintenta.
- Varios consumidores en paralelo sobre el mismo consumer group.
- Consumidor que cae después de procesar y antes de hacer ack; recuperación de pendientes (p. ej., `XAUTOCLAIM`).
- Eventos fuera de orden y tardíos: usar **tiempo del evento** vs. tiempo de procesamiento para el bucket por minuto; definir ventana de tolerancia (allowed lateness).
- Cambio de minuto (frontera de bucket) y zonas horarias (usar UTC).
- Eventos malformados o de tipo desconocido: validación con Pydantic + dead-letter stream, sin bloquear la cola.
- Mensajes "poison" con reintentos máximos.
- Retención/TTL de buckets y de las llaves de dedupe (memoria acotada).
- Redis reiniciado o caído: comportamiento y degradación.
- Lecturas del tablero mientras se escribe (¿pueden ver un estado parcial?).
- Cierre ordenado (graceful shutdown) del consumidor.

# ENTREGABLES (estructura sugerida del repo)
- `openspec/` con propuesta, diseño, especificación, tareas y registro de decisiones (versionado).
- `docs/decisiones/` con los ADRs.
- `src/` (api, consumer, dedupe/aggregation, config), `tests/`, `scripts/producer.py` (generador de eventos con opción de duplicar, desordenar y meter eventos malformados para demostrar el comportamiento).
- `docker-compose.yml` que levante todo (cola + API + N consumidores).
- `README.md` con: qué es, arquitectura (diagrama simple en mermaid), cómo correrlo localmente paso a paso, cómo ejecutar tests y el demo de duplicados/concurrencia, sección **"Decisiones y trade-offs"** (problema clásico abordado, solución elegida, alternativas descartadas), sección **"Uso de IA"** (dónde la IA propuso opciones distintas y por qué elegí la que elegí) y sección **"Pendientes"** (qué faltó y cómo seguiría).
- Tests que prueben explícitamente: idempotencia ante duplicados, concurrencia con varios consumidores sin pérdida ni doble conteo, recuperación de pendientes tras caída, eventos tardíos y eventos inválidos.

# FASES (detente al final de cada una y espera mi OK)
- **Fase 0 – Setup:** confirma que `openspec init` está hecho, propón la estructura del repo. Sin código de negocio.
- **Fase 1 – Propuesta:** problema, alcance, no-alcance, supuestos (la información está incompleta a propósito: lista tus supuestos y confírmalos conmigo).
- **Fase 2 – Diseño y opciones:** presenta las opciones de las 4 decisiones obligatorias y las de esquema de datos/claves, espera mi elección de cada una, y luego redacta diseño, casos borde y ADRs.
- **Fase 3 – Tareas:** desglosa en tareas pequeñas y ordenadas.
- **Fase 4 – Implementación:** tarea por tarea, con tests, commits pequeños y mensajes claros. Tras cada tarea marca el checklist en OpenSpec.
- **Fase 5 – Cierre:** README completo, verificación de que todo corre desde cero con un solo comando, revisión de que cada requisito del enunciado está cubierto (hazme una tabla requisito → evidencia en el repo), y archivar el cambio en OpenSpec.

# CÓMO QUIERO QUE RESPONDAS
- Conciso y directo. Nada de relleno.
- Si detectas ambigüedad, pregúntame (máximo 3 preguntas a la vez) o declara tu supuesto explícitamente.
- Si ves un riesgo o un error en mi decisión, dímelo con argumentos antes de implementar.
- Empieza ahora con la **Fase 0**.
