const PROVIDER_COLORS = {
  Groq: "#F97316",
  Gemini: "#60A5FA",
  OpenRouter: "#C084FC",
};

function fmtCost(v) {
  if (v === 0) return "$0.00";
  if (v < 0.0001) return "<$0.0001";
  return `$${v.toFixed(4)}`;
}

function fmtTokens(v) {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1000) return `${(v / 1000).toFixed(1)}K`;
  return `${v}`;
}

async function loadAnalytics() {
  const res = await fetch("/api/analytics/summary");
  const data = await res.json();

  const t = data.totals || {};
  document.getElementById("statMessages").textContent = t.messages || 0;
  document.getElementById("statTokens").textContent = fmtTokens(t.tokens || 0);
  document.getElementById("statCost").textContent = fmtCost(t.cost || 0);
  document.getElementById("statLatency").textContent = `${Math.round(t.avg_latency || 0)}ms`;
  document.getElementById("statSessions").textContent = data.session_count || 0;
  document.getElementById("statRouted").textContent = t.routed_messages || 0;

  renderProviderChart(data.by_provider || []);
  renderDailyChart(data.by_day || []);
  renderTable(data.by_provider || []);
}

function renderProviderChart(rows) {
  const container = document.getElementById("providerChart");
  if (rows.length === 0) {
    container.innerHTML = `<div class="a-bar-empty">No usage yet.</div>`;
    return;
  }

  const maxCost = Math.max(...rows.map((r) => r.cost), 0.0001);

  container.innerHTML = rows
    .map((r) => {
      const pct = Math.max((r.cost / maxCost) * 100, 2);
      const color = PROVIDER_COLORS[r.provider] || "#5EEAD4";
      return `
        <div class="a-bar-row">
          <div class="a-bar-row-label">
            <span>${r.provider} · ${r.model}</span>
            <span>${fmtCost(r.cost)}</span>
          </div>
          <div class="a-bar-track">
            <div class="a-bar-fill" style="width:${pct}%; background:${color}"></div>
          </div>
        </div>`;
    })
    .join("");
}

function renderDailyChart(rows) {
  const container = document.getElementById("dailyChart");
  if (rows.length === 0) {
    container.innerHTML = `<div class="a-bar-empty">No activity yet.</div>`;
    return;
  }

  const maxMessages = Math.max(...rows.map((r) => r.messages), 1);

  container.innerHTML = rows
    .map((r) => {
      const pct = Math.max((r.messages / maxMessages) * 100, 4);
      const day = new Date(r.day + "T00:00:00");
      const label = day.toLocaleDateString(undefined, { month: "short", day: "numeric" });
      return `
        <div class="a-day-bar-wrap">
          <div class="a-day-tip">${label} · ${r.messages} msg</div>
          <div class="a-day-bar" style="height:${pct}%"></div>
        </div>`;
    })
    .join("");
}

function renderTable(rows) {
  const tbody = document.getElementById("providerTableBody");
  const empty = document.getElementById("tableEmpty");

  if (rows.length === 0) {
    tbody.innerHTML = "";
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";

  tbody.innerHTML = rows
    .map(
      (r) => `
      <tr>
        <td>${r.provider}</td>
        <td>${r.model}</td>
        <td>${r.messages}</td>
        <td>${fmtTokens(r.tokens)}</td>
        <td>${fmtCost(r.cost)}</td>
        <td>${Math.round(r.avg_latency)}ms</td>
      </tr>`
    )
    .join("");
}

loadAnalytics();
