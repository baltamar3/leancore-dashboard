"""Dashboard HTML page: time-window selector and time-series/aggregate views."""

from src.config.settings import Settings, get_settings

_TEMPLATE: str = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>LeanCore Pagos</title>
  <link
    href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
    rel="stylesheet"
  />
  <style>
    body { padding: 2rem; }
    .metric-card { min-height: 160px; }
    .metric-value { font-size: 3rem; font-weight: 700; }
  </style>
</head>
<body>
  <div class="container">
    <h1 class="mb-4">LeanCore Pagos / Dashboard (UTC)</h1>

    <div class="d-flex flex-wrap align-items-center gap-3 mb-4">
      <div class="btn-group" role="group" aria-label="Ventana de tiempo" id="minutes-presets">
        <button type="button" class="btn btn-outline-primary" data-minutes="5">5 min</button>
        <button type="button" class="btn btn-outline-primary active" data-minutes="15">15 min</button>
        <button type="button" class="btn btn-outline-primary" data-minutes="30">30 min</button>
        <button type="button" class="btn btn-outline-primary" data-minutes="60">60 min</button>
        <button type="button" class="btn btn-outline-primary" id="custom-toggle">Personalizado</button>
      </div>
      <div class="input-group" id="custom-input-group" style="max-width: 220px; display: none;">
        <input
          type="number"
          class="form-control"
          id="custom-minutes"
          min="1"
          max="__MAX_MINUTES__"
          value="__DEFAULT_MINUTES__"
        />
        <span class="input-group-text">min</span>
      </div>

      <div class="btn-group ms-auto" role="group" aria-label="Vista" id="view-toggle">
        <button type="button" class="btn btn-outline-secondary active" data-view="timeseries">
          Serie de tiempo
        </button>
        <button type="button" class="btn btn-outline-secondary" data-view="aggregate">
          Agregado
        </button>
      </div>
    </div>

    <p class="text-muted small" id="status">Cargando...</p>

    <div id="view-timeseries">
      <table class="table table-striped table-sm" id="metrics-table">
        <thead>
          <tr><th>Minuto</th><th class="text-end">Procesados</th><th class="text-end">Fallidos</th></tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>

    <div id="view-aggregate" class="d-none">
      <div class="row g-3">
        <div class="col-6">
          <div class="card text-white bg-success metric-card">
            <div class="card-body text-center">
              <div class="card-title">Procesados</div>
              <div class="metric-value" id="aggregate-processed">-</div>
              <div id="aggregate-processed-pct"></div>
            </div>
          </div>
        </div>
        <div class="col-6">
          <div class="card text-white bg-danger metric-card">
            <div class="card-body text-center">
              <div class="card-title">Fallidos</div>
              <div class="metric-value" id="aggregate-failed">-</div>
              <div id="aggregate-failed-pct"></div>
            </div>
          </div>
        </div>
      </div>
      <p class="text-muted small mt-3" id="aggregate-empty" style="display: none;">
        Sin datos en esta ventana.
      </p>
    </div>
  </div>

  <script>
    const POLL_INTERVAL_MS = 2000;
    const DEFAULT_MINUTES = __DEFAULT_MINUTES__;
    const MAX_MINUTES = __MAX_MINUTES__;

    const state = {
      minutes: DEFAULT_MINUTES,
      view: "timeseries",
      lastData: null,
    };

    let requestSeq = 0;
    let pollTimer = null;

    const statusEl = document.querySelector("#status");
    const tbody = document.querySelector("#metrics-table tbody");
    const viewTimeSeriesEl = document.querySelector("#view-timeseries");
    const viewAggregateEl = document.querySelector("#view-aggregate");
    const customInputGroup = document.querySelector("#custom-input-group");
    const customMinutesInput = document.querySelector("#custom-minutes");

    function renderTimeSeries(data) {
      tbody.innerHTML = "";
      for (const bucket of data.buckets) {
        const row = document.createElement("tr");
        row.innerHTML =
          `<td>${bucket.minute}</td>` +
          `<td class="text-end">${bucket.processed}</td>` +
          `<td class="text-end">${bucket.failed}</td>`;
        tbody.appendChild(row);
      }
    }

    function renderAggregate(data) {
      const totals = data.buckets.reduce(
        (acc, bucket) => {
          acc.processed += bucket.processed;
          acc.failed += bucket.failed;
          return acc;
        },
        { processed: 0, failed: 0 }
      );
      const total = totals.processed + totals.failed;

      document.querySelector("#aggregate-processed").textContent = totals.processed;
      document.querySelector("#aggregate-failed").textContent = totals.failed;

      const emptyEl = document.querySelector("#aggregate-empty");
      const processedPctEl = document.querySelector("#aggregate-processed-pct");
      const failedPctEl = document.querySelector("#aggregate-failed-pct");

      if (total === 0) {
        emptyEl.style.display = "block";
        processedPctEl.textContent = "";
        failedPctEl.textContent = "";
      } else {
        emptyEl.style.display = "none";
        processedPctEl.textContent = Math.round((totals.processed / total) * 100) + "% del total";
        failedPctEl.textContent = Math.round((totals.failed / total) * 100) + "% del total";
      }
    }

    function renderCurrentView() {
      if (!state.lastData) return;
      if (state.view === "timeseries") {
        renderTimeSeries(state.lastData);
      } else {
        renderAggregate(state.lastData);
      }
    }

    function setView(view) {
      state.view = view;
      viewTimeSeriesEl.classList.toggle("d-none", view !== "timeseries");
      viewAggregateEl.classList.toggle("d-none", view !== "aggregate");
      document.querySelectorAll("#view-toggle button").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.view === view);
      });
      renderCurrentView(); // reusa lastData: no vuelve a pedir al servidor
    }

    async function refresh() {
      const seq = ++requestSeq;
      try {
        const response = await fetch(`/metrics/payments?minutes=${state.minutes}`);
        if (!response.ok) throw new Error("HTTP " + response.status);
        const data = await response.json();

        if (seq !== requestSeq) return; // respuesta obsoleta: el selector ya cambió

        state.lastData = data;
        renderCurrentView();
        statusEl.textContent = "Actualizado: " + new Date().toLocaleTimeString();
      } catch (err) {
        if (seq !== requestSeq) return;
        statusEl.textContent = "Error al actualizar: " + err.message;
      }
    }

    function restartPolling() {
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(refresh, POLL_INTERVAL_MS);
    }

    function setMinutes(rawValue) {
      const parsed = parseInt(rawValue, 10) || DEFAULT_MINUTES;
      const clamped = Math.min(Math.max(parsed, 1), MAX_MINUTES);
      state.minutes = clamped;
      document.querySelectorAll("#minutes-presets button[data-minutes]").forEach((btn) => {
        btn.classList.toggle("active", Number(btn.dataset.minutes) === clamped);
      });
      refresh();
      restartPolling();
    }

    document.querySelectorAll("#minutes-presets button[data-minutes]").forEach((btn) => {
      btn.addEventListener("click", () => {
        customInputGroup.style.display = "none";
        setMinutes(btn.dataset.minutes);
      });
    });

    document.querySelector("#custom-toggle").addEventListener("click", () => {
      customInputGroup.style.display = "flex";
      customMinutesInput.focus();
    });

    customMinutesInput.addEventListener("change", () => setMinutes(customMinutesInput.value));
    customMinutesInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") setMinutes(customMinutesInput.value);
    });

    document.querySelectorAll("#view-toggle button[data-view]").forEach((btn) => {
      btn.addEventListener("click", () => setView(btn.dataset.view));
    });

    refresh();
    restartPolling();
  </script>
</body>
</html>
"""


def _build_dashboard_html(default_minutes: int, max_minutes: int) -> str:
    """Fill in the default/max window placeholders in the template."""
    return _TEMPLATE.replace("__DEFAULT_MINUTES__", str(default_minutes)).replace(
        "__MAX_MINUTES__", str(max_minutes)
    )


_settings: Settings = get_settings()
DASHBOARD_HTML: str = _build_dashboard_html(
    _settings.default_metrics_minutes, _settings.max_metrics_minutes
)
