const state = { companies: [], symbol: null, month: null, exchange: "nse", data: null, chart: null };
const $ = (id) => document.getElementById(id);
const fmt = (v) => (v == null ? "–" : Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const fmtDate = (s) => (s ? new Date(s + "T00:00:00").toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "–");

async function api(path, opts) {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || r.statusText);
  return body;
}

function toast(msg, isError = false, ms = 6000) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast" + (isError ? " error" : "");
  t.hidden = false;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => (t.hidden = true), ms);
}

function quote(exchange, q) {
  if (!q) return `<div class="quote"><span class="ex">${exchange}</span><span class="price">–</span></div>`;
  const chg = q.change == null ? "" : `<span class="chg ${q.change >= 0 ? "up" : "down"}">${q.change >= 0 ? "▲" : "▼"} ${fmt(Math.abs(q.change))} (${Math.abs(q.pct).toFixed(2)}%)</span>`;
  return `<div class="quote"><span class="ex">${exchange}</span><span class="price">₹${fmt(q.close)}</span>${chg}<span class="date">${fmtDate(q.date)}</span></div>`;
}

function renderCompanies() {
  const box = $("companies");
  box.innerHTML = "";
  for (const c of state.companies) {
    const el = document.createElement("button");
    el.className = "company" + (c.symbol === state.symbol ? " active" : "");
    el.innerHTML = `
      <div class="sym">${c.symbol}</div>
      <div class="name">${c.name} · BSE ${c.bse_code}</div>
      ${quote("NSE", c.nse)}
      ${quote("BSE", c.bse)}`;
    el.onclick = () => selectCompany(c.symbol);
    box.appendChild(el);
  }
  const latest = state.companies.map((c) => c.last_nse).filter(Boolean).sort().pop();
  $("lastUpdated").textContent = latest ? `data up to ${fmtDate(latest)}` : "no data yet – click Refresh";
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function drawChart() {
  const exchange = state.exchange;
  const d = state.data?.[exchange];
  const company = state.companies.find((x) => x.symbol === state.symbol);
  const canvas = $("chart");
  const empty = $("chartEmpty");
  for (const b of document.querySelectorAll("#exchangeToggle button")) {
    b.setAttribute("aria-pressed", b.dataset.ex === exchange);
  }
  state.chart?.destroy();
  state.chart = null;
  const has = !!d && d.labels.length > 0;
  empty.textContent = `No ${exchange.toUpperCase()} data for this month.`;
  empty.hidden = has;
  canvas.parentElement.hidden = !has;
  if (!has) return;
  const monthName = new Date(d.month + "-01T00:00:00").toLocaleDateString("en-GB", { month: "short" });
  const text = cssVar("--text"), muted = cssVar("--muted"), grid = cssVar("--border");
  // Leave headroom below the lowest price so the Low bars stay readable.
  const lo = Math.min(...d.low.filter((v) => v != null)), hi = Math.max(...d.high.filter((v) => v != null));
  const yMin = Math.max(0, Math.floor(lo - (hi - lo) * 1.5 - lo * 0.01));
  state.chart = new Chart(canvas, {
    data: {
      labels: d.labels,
      datasets: [
        { type: "line", label: "WAP", data: d.avg, borderColor: "#FFAF14", backgroundColor: "#FFAF14", borderWidth: 2.5, pointRadius: 3, tension: 0, order: 0 },
        { type: "bar", label: "High Price", data: d.high, backgroundColor: "#00B0F6", order: 1 },
        { type: "bar", label: "Low Price", data: d.low, backgroundColor: "#003274", order: 1 },
        { type: "bar", label: "Close Price", data: d.close, backgroundColor: "#8EAFC0", order: 1 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        title: { display: true, text: `${company.name} Share Price ${monthName}'${d.month.slice(2, 4)} (INR) – ${exchange.toUpperCase()}`, color: cssVar("--navy"), font: { size: 14, weight: "600" } },
        legend: { position: "bottom", labels: { color: text } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ₹${fmt(c.parsed.y)}` } },
      },
      scales: {
        x: { ticks: { color: muted }, grid: { display: false } },
        y: { min: yMin, ticks: { color: muted, callback: (v) => "₹" + v }, grid: { color: grid } },
      },
    },
  });
}

// Show chart data for the selected company; n and b are /api/chart responses.
function showCharts(n, b) {
  const c = state.companies.find((x) => x.symbol === state.symbol);
  $("companyTitle").textContent = `${c.name} (${c.symbol})`;
  const months = [...new Set([...n.months, ...b.months])].sort().reverse();
  const sel = $("monthSelect");
  sel.innerHTML = months
    .map((m) => `<option value="${m}">${new Date(m + "-01T00:00:00").toLocaleDateString("en-GB", { month: "long", year: "numeric" })}</option>`)
    .join("");
  state.month = state.month && months.includes(state.month) ? state.month : n.month || b.month;
  sel.value = state.month || "";
  state.data = { nse: n, bse: b };
  drawChart();
}

async function loadCharts() {
  const q = state.month ? `&month=${state.month}` : "";
  const [n, b] = await Promise.all([
    api(`/api/chart/${state.symbol}?exchange=nse${q}`),
    api(`/api/chart/${state.symbol}?exchange=bse${q}`),
  ]);
  showCharts(n, b);
}

async function selectCompany(sym) {
  state.symbol = sym; // keep the selected month so companies can be compared
  renderCompanies();
  await loadCharts();
}

function showCompanies(r) {
  state.companies = r.companies;
  state.symbol ??= r.companies[0].symbol;
  renderCompanies();
}

async function loadCompanies() {
  showCompanies(await api("/api/companies"));
}

async function refresh() {
  const btn = $("refreshBtn");
  btn.disabled = true;
  btn.querySelector(".spinner").hidden = false;
  btn.querySelector(".label").textContent = "Refreshing…";
  try {
    // If the latest month is on screen, follow the data into a new month.
    const months = $("monthSelect").options;
    const onLatest = !state.month || (months.length && state.month === months[0].value);
    const params = new URLSearchParams({ symbol: state.symbol || "" });
    if (state.month && !onLatest) params.set("month", state.month);
    const r = await api("/api/refresh?" + params, { method: "POST" });
    const lines = [], errors = [];
    for (const [sym, ex] of Object.entries(r.companies)) {
      for (const [name, s] of Object.entries(ex)) {
        if (s.status === "error") errors.push(`${sym} ${name.toUpperCase()}: ${s.error}`);
        else if (s.added) lines.push(`${sym} ${name.toUpperCase()}: +${s.added} day(s)`);
      }
    }
    if (errors.length) toast(["Some sources failed:", ...errors, ...lines].join("\n"), true, 12000);
    else toast(lines.length ? "Excel updated\n" + lines.join("\n") : "Already up to date – no new trading days since the latest date in the Excel.");
    // The response carries the updated data, so the page updates without a second request.
    const v = r.view;
    showCompanies(v);
    if (v.symbol === state.symbol) {
      if (onLatest) state.month = null;
      showCharts(v.charts.nse, v.charts.bse);
    } else {
      await loadCharts();
    }
  } catch (e) {
    toast("Refresh failed: " + e.message, true);
  } finally {
    btn.disabled = false;
    btn.querySelector(".spinner").hidden = true;
    btn.querySelector(".label").textContent = "Refresh";
  }
}

$("refreshBtn").onclick = refresh;
for (const b of document.querySelectorAll("#exchangeToggle button")) {
  b.onclick = () => { state.exchange = b.dataset.ex; drawChart(); };
}
$("monthSelect").onchange = (e) => { state.month = e.target.value; loadCharts(); };

loadCompanies().then(loadCharts).catch((e) => toast("Failed to load: " + e.message, true));
