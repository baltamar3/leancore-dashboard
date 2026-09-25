#!/usr/bin/env bash
# Demo end-to-end: levanta el stack con 3 consumidores, publica un lote con
# duplicados/desorden/eventos malformados, y compara el conteo esperado
# contra el que expone la API (ver openspec/changes/payment-metrics-dashboard).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Levantando stack (redis + api + 3 consumidores)"
docker compose up -d --build --scale consumer=3

echo "==> Esperando a que la API responda"
for _ in $(seq 1 30); do
  if curl -s -o /dev/null http://127.0.0.1:8000/metrics/payments; then
    break
  fi
  sleep 1
done

echo "==> Publicando lote de demo (duplicados, desorden, malformados)"
python scripts/producer.py \
  --count 200 \
  --duplicate-rate 0.15 \
  --malformed-rate 0.05 \
  --out-of-order \
  --spread-seconds 30

echo "==> Esperando a que los consumidores procesen el lote"
sleep 5

echo "==> Resultado en el tablero (últimos 5 minutos):"
curl -s "http://127.0.0.1:8000/metrics/payments?minutes=5" | python -m json.tool

dlq_length=$(docker compose exec -T redis redis-cli XLEN stream:payments:dlq)
echo "==> Entradas en dead-letter (stream:payments:dlq): ${dlq_length}"
echo "==> Compara el total processed+failed de arriba contra 'eventos válidos únicos' que imprimió el productor."
