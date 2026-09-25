DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>Pagos por minuto</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; }
    table { border-collapse: collapse; width: 100%; max-width: 640px; }
    th, td { border: 1px solid #ccc; padding: 0.4rem 0.8rem; text-align: right; }
    th:first-child, td:first-child { text-align: left; }
    caption { text-align: left; margin-bottom: 0.5rem; color: #555; }
  </style>
</head>
<body>
  <h1>Pagos procesados / fallidos por minuto (UTC)</h1>
  <table id="metrics-table">
    <caption id="status">Cargando...</caption>
    <thead>
      <tr><th>Minuto</th><th>Procesados</th><th>Fallidos</th></tr>
    </thead>
    <tbody></tbody>
  </table>

  <script>
    const POLL_INTERVAL_MS = 2000;
    const tbody = document.querySelector("#metrics-table tbody");
    const status = document.querySelector("#status");

    async function refresh() {
      try {
        const response = await fetch("/metrics/payments?minutes=15");
        if (!response.ok) throw new Error("HTTP " + response.status);
        const data = await response.json();
        tbody.innerHTML = "";
        for (const bucket of data.buckets) {
          const row = document.createElement("tr");
          row.innerHTML =
            `<td>${bucket.minute}</td><td>${bucket.processed}</td><td>${bucket.failed}</td>`;
          tbody.appendChild(row);
        }
        status.textContent = "Actualizado: " + new Date().toLocaleTimeString();
      } catch (err) {
        status.textContent = "Error al actualizar: " + err.message;
      }
    }

    refresh();
    setInterval(refresh, POLL_INTERVAL_MS);
  </script>
</body>
</html>
"""
