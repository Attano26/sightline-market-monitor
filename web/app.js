/* Sightline dashboard: reads data/sightline.json written by `python -m sightline.build`. */

const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const C = {
  ink: css("--ink"), muted: css("--muted"), line: css("--line"), accent: css("--accent"),
  forecast: css("--forecast"), up: css("--up"), flat: css("--flat"), down: css("--down"),
};
const alpha = (hex, a) => {
  const n = parseInt(hex.replace("#", ""), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
};
const SIGNAL_LABELS = {
  house_prices: "House prices", rates: "Interest rates", investment: "Growth & investment",
  construction: "Construction growth", imports: "Fenestration imports",
};
const TRADE_COLORS = () => [C.accent, C.forecast, C.flat, C.muted];
const THIS_YEAR = new Date().getFullYear();

Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
Chart.defaults.font.size = 11;
Chart.defaults.color = C.muted;
Chart.defaults.borderColor = C.line;
Chart.defaults.plugins.legend.labels.boxWidth = 10;
Chart.defaults.plugins.legend.labels.boxHeight = 10;
Chart.defaults.maintainAspectRatio = false;
Chart.defaults.animation = false;

const charts = {};
let DATA = null;

function draw(id, config) {
  const canvas = document.getElementById(id);
  const fig = canvas.closest("figure");
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
  const empty = !config;
  fig.querySelector(".cv").hidden = empty;
  const note = fig.querySelector(".empty");
  if (note) note.hidden = !empty;
  if (!empty) charts[id] = new Chart(canvas, config);
}

/* History (solid) + forecast (dashed) + 80% band. */
function forecastChart(history, forecast, { keep = 96, label = "", decimals = 1 } = {}) {
  if (!history || history.length === 0) return null;
  const hist = history.slice(-keep);
  const fc = forecast || [];
  const labels = [...hist.map((p) => p.date), ...fc.map((p) => p.date)];
  const pad = (arr) => [...Array(hist.length - 1).fill(null), hist[hist.length - 1].value, ...arr];
  const datasets = [
    { label, data: [...hist.map((p) => p.value), ...fc.map(() => null)], borderColor: C.ink, borderWidth: 1.6, pointRadius: 0, tension: 0.2 },
  ];
  if (fc.length) {
    datasets.push(
      { label: "80% range low", data: pad(fc.map((p) => p.lo)), borderWidth: 0, pointRadius: 0, fill: false },
      { label: "80% range", data: pad(fc.map((p) => p.hi)), borderWidth: 0, pointRadius: 0, fill: "-1", backgroundColor: alpha(C.forecast, 0.18) },
      { label: "Forecast", data: pad(fc.map((p) => p.value)), borderColor: C.forecast, borderDash: [5, 4], borderWidth: 1.8, pointRadius: 0 },
    );
  }
  return {
    type: "line",
    data: { labels, datasets },
    options: {
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          filter: (item) => item.raw !== null && item.dataset.label !== "80% range low",
          callbacks: {
            label: (item) => {
              if (item.dataset.label === "80% range") {
                const lo = item.chart.data.datasets[1].data[item.dataIndex];
                return ` 80% range: ${lo.toFixed(decimals)} – ${item.raw.toFixed(decimals)}`;
              }
              return ` ${item.dataset.label || "Value"}: ${item.raw.toFixed(decimals)}`;
            },
          },
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 7, maxRotation: 0 } },
        y: { grid: { color: C.line } },
      },
    },
  };
}

function importsChart(trade, codes) {
  const years = [...new Set(Object.values(trade).flat().map((p) => p.date))].sort();
  if (years.length === 0) return null;
  const colors = TRADE_COLORS();
  const datasets = Object.keys(codes).map((code, i) => {
    const byYear = Object.fromEntries((trade[code] || []).map((p) => [p.date, p.value / 1e6]));
    return { label: codes[code].split(" (")[0], data: years.map((y) => byYear[y] ?? null), backgroundColor: colors[i % colors.length], borderRadius: 2 };
  });
  return {
    type: "bar",
    data: { labels: years, datasets },
    options: {
      plugins: {
        legend: { position: "bottom" },
        tooltip: { callbacks: { label: (i) => ` ${i.dataset.label}: $${(i.raw ?? 0).toFixed(1)}M` } },
      },
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, grid: { color: C.line } } },
    },
  };
}

function imfChart(gdp, inv) {
  const years = [...new Set([...gdp, ...inv].map((p) => p.date))].sort().filter((y) => +y >= 2015);
  if (years.length === 0) return null;
  const g = Object.fromEntries(gdp.map((p) => [p.date, p.value]));
  const v = Object.fromEntries(inv.map((p) => [p.date, p.value]));
  return {
    type: "bar",
    data: {
      labels: years,
      datasets: [
        { type: "bar", label: "GDP growth %", data: years.map((y) => g[y] ?? null), yAxisID: "y",
          backgroundColor: years.map((y) => (+y >= THIS_YEAR ? alpha(C.forecast, 0.45) : C.accent)), borderRadius: 2 },
        { type: "line", label: "Investment % of GDP", data: years.map((y) => v[y] ?? null), yAxisID: "y2",
          borderColor: C.ink, borderWidth: 1.6, pointRadius: 2, pointBackgroundColor: C.ink,
          segment: { borderDash: (ctx) => (+years[ctx.p1DataIndex] >= THIS_YEAR ? [5, 4] : undefined) } },
      ],
    },
    options: {
      plugins: { legend: { position: "bottom" } },
      scales: {
        x: { grid: { display: false } },
        y: { position: "left", grid: { color: C.line }, title: { display: true, text: "GDP %" } },
        y2: { position: "right", grid: { display: false }, title: { display: true, text: "Invest. %" } },
      },
    },
  };
}

function wbChart(industry, gfcf) {
  const years = [...new Set([...industry, ...gfcf].map((p) => p.date))].sort();
  if (years.length === 0) return null;
  const a = Object.fromEntries(industry.map((p) => [p.date, p.value]));
  const b = Object.fromEntries(gfcf.map((p) => [p.date, p.value]));
  const line = (label, map, color) => ({ label, data: years.map((y) => map[y] ?? null), borderColor: color, backgroundColor: color, borderWidth: 1.6, pointRadius: 2, spanGaps: true });
  return {
    type: "line",
    data: { labels: years, datasets: [line("Industry incl. construction", a, C.accent), line("Fixed capital formation", b, C.forecast)] },
    options: { plugins: { legend: { position: "bottom" } }, scales: { x: { grid: { display: false } }, y: { grid: { color: C.line } } } },
  };
}

function scoreColor(label) {
  return label === "Expanding" ? C.up : label === "Contracting" ? C.down : C.flat;
}

function meter(value, label) {
  // value in -1..+1 (or score/100); bar grows from centre
  const pct = Math.max(-1, Math.min(1, value)) * 50;
  const left = pct >= 0 ? 50 : 50 + pct;
  return `<div class="meter"><i style="left:${left}%;width:${Math.abs(pct)}%;background:${scoreColor(label)}"></i></div>`;
}

function renderCards() {
  const host = document.getElementById("cards");
  const sorted = [...DATA.countries].sort((a, b) => b.outlook.score - a.outlook.score);
  host.innerHTML = sorted.map((c) => {
    const o = c.outlook;
    return `<button class="card" data-iso="${c.iso2}" aria-pressed="false">
      <div class="name">${c.name}</div>
      <div class="score" style="color:${scoreColor(o.label)}">${o.score > 0 ? "+" : ""}${o.score}</div>
      ${meter(o.score / 100, o.label)}
      <span class="badge ${o.label}">${o.label}</span>
      <div class="cov">${o.coverage}</div>
    </button>`;
  }).join("");
  host.querySelectorAll(".card").forEach((el) => el.addEventListener("click", () => select(el.dataset.iso)));
}

function select(iso2) {
  const c = DATA.countries.find((x) => x.iso2 === iso2);
  if (!c) return;
  document.querySelectorAll(".card").forEach((el) => el.setAttribute("aria-pressed", el.dataset.iso === iso2));
  const detail = document.getElementById("detail");
  detail.hidden = false;
  const o = c.outlook;
  document.getElementById("d-name").textContent = c.name;
  document.getElementById("d-sub").textContent = `Outlook score ${o.score > 0 ? "+" : ""}${o.score} from ${o.coverage}.`;
  const badge = document.getElementById("d-badge");
  badge.className = `badge ${o.label}`;
  badge.textContent = o.label;

  document.getElementById("d-signals").innerHTML = Object.entries(o.signals).map(([key, s]) => {
    if (!s) return `<div class="signal missing"><span class="lab">${SIGNAL_LABELS[key]}</span><span></span><span class="txt">No data for this country; signal skipped.</span></div>`;
    const lab = s.value > 0.15 ? "Expanding" : s.value < -0.15 ? "Contracting" : "Stable";
    return `<div class="signal"><span class="lab">${SIGNAL_LABELS[key]}</span>${meter(s.value, lab)}<span class="txt">${s.text}</span></div>`;
  }).join("");

  const s = c.series;
  document.getElementById("fx-unit").textContent = `${c.currency} per USD · monthly (higher = weaker ${c.currency}, dearer imports)`;
  draw("c-house", forecastChart(s.house_prices.history, s.house_prices.forecast, { keep: 40, label: "Real house prices" }));
  draw("c-rate", forecastChart(s.policy_rate.history, s.policy_rate.forecast, { keep: 96, label: "Policy rate %", decimals: 2 }));
  draw("c-fx", forecastChart(s.exchange_rate.history, s.exchange_rate.forecast, { keep: 96, label: `${c.currency}/USD`, decimals: 2 }));
  draw("c-imports", importsChart(c.trade, DATA.trade_codes));
  draw("c-imf", imfChart(s.imf_gdp_growth, s.wb_investment_ratio));
  draw("c-wb", wbChart(s.wb_industry_growth, s.wb_gfcf_growth));
  try { localStorage.setItem("sightline.country", iso2); } catch (_) { /* storage blocked */ }
}

function renderCommodities() {
  const host = document.getElementById("commodities");
  host.innerHTML = DATA.commodities.map((c) => {
    const h = c.history;
    const last = h.length ? h[h.length - 1] : null;
    const yearAgo = h.length > 12 ? h[h.length - 13] : null;
    const chg = last && yearAgo ? ((last.value / yearAgo.value - 1) * 100).toFixed(1) : null;
    const sub = last ? `$${last.value.toLocaleString(undefined, { maximumFractionDigits: 0 })} in ${last.date}${chg !== null ? ` · ${chg > 0 ? "+" : ""}${chg}% YoY` : ""}` : "no data";
    return `<figure><figcaption>${c.name}<span>${sub}</span></figcaption><div class="cv"><canvas id="cm-${c.id}"></canvas></div><p class="empty" hidden>No data.</p></figure>`;
  }).join("");
  DATA.commodities.forEach((c) => draw(`cm-${c.id}`, forecastChart(c.history, c.forecast, { keep: 72, label: c.name, decimals: 0 })));
}

async function init() {
  try {
    const res = await fetch("data/sightline.json", { cache: "no-store" });
    DATA = await res.json();
  } catch (e) {
    document.getElementById("meta").textContent = "No data yet. Run `python -m sightline.build`, then serve the web folder.";
    return;
  }
  const when = new Date(DATA.generated_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  document.getElementById("meta").innerHTML = `Updated ${when}<br>Forecasts: ${DATA.model}`;
  renderCards();
  renderCommodities();
  let start = null;
  try { start = localStorage.getItem("sightline.country"); } catch (_) { /* storage blocked */ }
  const first = DATA.countries.find((c) => c.iso2 === start) ? start : [...DATA.countries].sort((a, b) => b.outlook.score - a.outlook.score)[0].iso2;
  select(first);
}

init();
