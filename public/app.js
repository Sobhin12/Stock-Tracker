const state = { companies: [], symbol: null, month: null, charts: {} };
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

function renderCompanies() {
  const box = $("companies");
  box.innerHTML = "";
  for (const c of state.companies) {
    const chg = c.last_close != null && c.prev_close ? ((c.last_close - c.prev_close) / c.prev_close) * 100 : null;
    const el = document.createElement("button");
    el.className = "company" + (c.symbol === state.symbol ? " active" : "");
    el.innerHTML = `
      <div class="sym">${c.symbol}</div>
      <div class="name">${c.name} · BSE ${c.bse_code}</div>
      <div class="price">₹${fmt(c.last_close)}${chg == null ? "" : `<span class="chg ${chg >= 0 ? "up" : "down"}">${chg >= 0 ? "▲" : "▼"} ${chg.toFixed(2)}%</span>`}</div>
      <div class="dates">NSE ${fmtDate(c.last_nse)} · BSE ${fmtDate(c.last_bse)}</div>`;
    el.onclick = () => selectCompany(c.symbol);
    box.appendChild(el);
  }
  const latest = state.companies.map((c) => c.last_nse).filter(Boolean).sort().pop();
  $("lastUpdated").textContent = latest ? `data up to ${fmtDate(latest)}` : "no data yet – click Refresh";
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function drawChart(exchange, d, company) {
  const canvas = $(exchange + "Chart");
  const empty = $(exchange + "Empty");
  state.charts[exchange]?.destroy();
  const has = d.labels.length > 0;
  empty.hidden = has;
  canvas.parentElement.hidden = !has;
  if (!has) return;
  const monthName = new Date(d.month + "-01T00:00:00").toLocaleDateString("en-GB", { month: "short" });
  const text = cssVar("--text"), muted = cssVar("--muted"), grid = cssVar("--border");
  // Leave headroom below the lowest price so the Low bars stay readable.
  const lo = Math.min(...d.low.filter((v) => v != null)), hi = Math.max(...d.high.filter((v) => v != null));
  const yMin = Math.max(0, Math.floor(lo - (hi - lo) * 1.5 - lo * 0.01));
  state.charts[exchange] = new Chart(canvas, {
    data: {
      labels: d.labels,
      datasets: [
        { type: "line", label: d.avg_label, data: d.avg, borderColor: "#FFAF14", backgroundColor: "#FFAF14", borderWidth: 2.5, pointRadius: 3, tension: 0, order: 0 },
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

async function loadCharts() {
  const c = state.companies.find((x) => x.symbol === state.symbol);
  $("companyTitle").textContent = `${c.name} (${c.symbol})`;
  const q = state.month ? `&month=${state.month}` : "";
  const [n, b] = await Promise.all([
    api(`/api/chart/${c.symbol}?exchange=nse${q}`),
    api(`/api/chart/${c.symbol}?exchange=bse${q}`),
  ]);
  const months = [...new Set([...n.months, ...b.months])].sort().reverse();
  const sel = $("monthSelect");
  sel.innerHTML = months
    .map((m) => `<option value="${m}">${new Date(m + "-01T00:00:00").toLocaleDateString("en-GB", { month: "long", year: "numeric" })}</option>`)
    .join("");
  state.month = state.month && months.includes(state.month) ? state.month : n.month || b.month;
  sel.value = state.month || "";
  drawChart("nse", n, c);
  drawChart("bse", b, c);
}

async function selectCompany(sym) {
  state.symbol = sym; // keep the selected month so companies can be compared
  renderCompanies();
  await loadCharts();
}

async function loadCompanies() {
  const r = await api("/api/companies");
  state.companies = r.companies;
  state.symbol ??= r.companies[0].symbol;
  renderCompanies();
  return r;
}

async function refresh() {
  const btn = $("refreshBtn");
  btn.disabled = true;
  btn.querySelector(".spinner").hidden = false;
  btn.querySelector(".label").textContent = "Refreshing…";
  try {
    const r = await api("/api/refresh", { method: "POST" });
    const lines = [], errors = [];
    for (const [sym, ex] of Object.entries(r.companies)) {
      for (const [name, s] of Object.entries(ex)) {
        if (s.status === "error") errors.push(`${sym} ${name.toUpperCase()}: ${s.error}`);
        else if (s.added) lines.push(`${sym} ${name.toUpperCase()}: +${s.added} day(s)`);
      }
    }
    if (errors.length) toast(["Some sources failed:", ...errors, ...lines].join("\n"), true, 12000);
    else toast(lines.length ? "Excel updated\n" + lines.join("\n") : "Already up to date – no new trading days since the latest date in the Excel.");
    await loadCompanies();
    await loadCharts();
  } catch (e) {
    toast("Refresh failed: " + e.message, true);
  } finally {
    btn.disabled = false;
    btn.querySelector(".spinner").hidden = true;
    btn.querySelector(".label").textContent = "Refresh";
  }
}

$("refreshBtn").onclick = refresh;
$("monthSelect").onchange = (e) => { state.month = e.target.value; loadCharts(); };
$("downloadBtn").onclick = (e) => {
  if (!state.companies.some((c) => c.last_nse)) { e.preventDefault(); toast("No workbook yet – click Refresh first.", true); }
};

loadCompanies().then(loadCharts).catch((e) => toast("Failed to load: " + e.message, true));
