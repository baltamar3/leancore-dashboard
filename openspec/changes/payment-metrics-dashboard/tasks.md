# Tasks

## 1. Scaffolding y configuración base

- [x] 1.1 Crear estructura de paquetes (`src/api`, `src/consumer`, `src/aggregation`, `src/config`, `tests/unit`, `tests/integration`, `scripts/`) con sus `__init__.py`; verificar con `python -c "import src"` sin errores.
- [x] 1.2 Crear `pyproject.toml` (fastapi, uvicorn, redis, pydantic, pydantic-settings, pytest, pytest-asyncio, fakeredis, ruff) y `Makefile` con targets `install`, `lint`, `test`, `run-api`, `run-consumer`; verificar que `pip install -e .` (o el gestor elegido) instala sin errores.
- [x] 1.3 Configurar ruff y verificar que `ruff check .` corre limpio sobre el esqueleto inicial.
- [x] 1.4 Crear `src/config/settings.py` (pydantic-settings) con host/puerto Redis, nombres de stream/grupo/dlq, TTL de dedupe, allowed lateness y retención de bucket como constantes configurables, más `.env.example`; verificar que `Settings()` carga valores por defecto sin `.env` presente.
- [x] 1.5 Crear `docker-compose.yml` inicial solo con el servicio Redis (`appendonly yes`); verificar `docker compose up -d redis && redis-cli ping` responde `PONG`.

## 2. Modelos y validación de eventos

- [x] 2.1 Definir el modelo Pydantic `PaymentEvent` (`event_id`, `type` enum `payment.processed`/`payment.failed`, `occurred_at` datetime UTC, `payment_id`); test unitario que verifica que un evento válido se parsea correctamente.
- [x] 2.2 Test unitario: evento malformado (campo faltante o tipo incorrecto) y evento con `type` desconocido fallan la validación — cubre los escenarios "Evento malformado" y "Tipo de evento desconocido" de `specs/payment-event-ingestion`.

## 3. Dedupe y agregación en Redis

- [ ] 3.1 Implementar el script Lua de dedupe+incremento y el wrapper Python que lo registra/ejecuta; test unitario con fakeredis: la primera aplicación de un `event_id` incrementa el bucket correspondiente.
- [ ] 3.2 Test unitario (fakeredis): aplicar el mismo `event_id` dos veces → el segundo no reincrementa — cubre "Evento reentregado tras timeout de ack" y "Evento duplicado producido por el emisor".
- [ ] 3.3 Implementar el cálculo de bucket de minuto a partir de `occurred_at` (UTC, truncado a minuto); test unitario de frontera de minuto (ej. `12:00:59.9` vs `12:01:00.1` deben caer en buckets distintos).
- [ ] 3.4 Implementar la lógica de ventana de tardíos (evento dentro de allowed lateness → bucket histórico; fuera de lateness pero bucket vivo → bucket histórico + marca de fallback; bucket ya expirado → bucket actual + contador de fallback); tests unitarios para los tres casos.
- [ ] 3.5 Implementar `get_metrics(minutes)` que lee los Hashes de los últimos N minutos y rellena con cero los minutos sin eventos; test unitario que verifica los ceros.

## 4. Consumidor

- [ ] 4.1 Implementar creación idempotente de stream y grupo (`XGROUP CREATE ... MKSTREAM`) al arrancar; test de integración (Redis real) que verifica que arrancar dos veces no falla.
- [ ] 4.2 Implementar el loop principal (`XREADGROUP` → aplicar dedupe+agregación → `XACK` solo tras éxito); test de integración: publicar N eventos, correr un consumidor, verificar que el conteo final agregado es igual a N.
- [ ] 4.3 Implementar recuperación de pendientes con `XAUTOCLAIM` (min-idle-time configurable) al inicio de cada ciclo de lectura; test de integración que simula un consumidor caído a mitad de proceso y verifica que otro consumidor reclama y completa el conteo.
- [ ] 4.4 Implementar el flujo de dead-letter: eventos inválidos y mensajes "poison" (delivery count vía `XPENDING` supera el máximo configurado) se copian a `stream:payments:dlq` y se confirman en el stream principal; test de integración que verifica que un evento malformado no afecta los contadores y sí aparece en la `dlq`.
- [ ] 4.5 Implementar cierre ordenado ante SIGTERM/SIGINT (terminar entradas en curso, dejar de leer nuevas, cerrar conexión); test que verifica que no quedan entradas "en vuelo" sin confirmar tras la señal.
- [ ] 4.6 Implementar reconexión con backoff acotado si Redis no responde; test que simula una desconexión y verifica que el proceso no termina y retoma el consumo al reconectar.
- [ ] 4.7 Prueba de concurrencia central del ejercicio: correr 2-3 consumidores en paralelo sobre el mismo grupo contra un lote de eventos que incluye duplicados intencionales, y verificar que el conteo final es exacto (sin duplicar ni perder ninguno).

## 5. API y tablero

- [ ] 5.1 Implementar `GET /metrics/payments?minutes=N` sobre `get_metrics`; test con `TestClient` para una ventana válida.
- [ ] 5.2 Validar el parámetro `minutes` (rango permitido, valor por defecto si se omite, error 422 si es inválido o está fuera de rango); tests para ambos casos.
- [ ] 5.3 Manejar indisponibilidad de Redis en el endpoint devolviendo 503 controlado; test que simula un fallo de conexión.
- [ ] 5.4 Página HTML mínima que hace polling cada 2s al endpoint de métricas; verificación manual (navegador o `curl`) de que la página carga y los valores se actualizan.

## 6. Generador de eventos de prueba

- [ ] 6.1 Implementar `scripts/producer.py` con publicación normal de eventos `payment.processed`/`payment.failed` con `occurred_at` actual; verificar que `XLEN` del stream aumenta según lo publicado.
- [ ] 6.2 Agregar flags `--duplicate-rate`, `--out-of-order` y `--malformed-rate` que reproduzcan esos tres casos borde; verificación manual de que el consumidor reacciona como describen las specs (dedupe, bucket correcto, envío a `dlq`).

## 7. Orquestación completa y demo end-to-end

- [ ] 7.1 Completar `docker-compose.yml` con los servicios `api` y `consumer` (soportando `--scale consumer=N`); verificar que `docker compose up --build` levanta los tres servicios sin errores.
- [ ] 7.2 Crear un comando de demo (`make demo` o `scripts/demo.sh`) que levanta el stack, corre el producer con duplicados/desorden/malformados, y consulta el endpoint; verificar que el conteo final coincide con el número de eventos únicos válidos publicados.
- [ ] 7.3 Verificar que `make test` (unit + integration) pasa en limpio contra `docker compose up -d redis`.

## 8. Documentación mínima para ejecutar

- [ ] 8.1 Escribir un README funcional (qué es, diagrama de arquitectura en mermaid, pasos para correr localmente, cómo correr tests y el demo de duplicados/concurrencia); verificar siguiendo los pasos documentados desde un checkout limpio.
