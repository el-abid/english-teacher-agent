const byId = (id) => document.getElementById(id);
const state = { kind: "", timer: null };

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function money(value) {
  const n = Number(value || 0);
  if (n === 0) return "$0";
  return n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`;
}

function tokens(value) {
  const n = Number(value || 0);
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

function clock(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function renderCards(data) {
  const t = data.totals || {};
  const a = data.alerts || {};
  const budget = Number(a.daily_token_budget || 0);
  const used = Number(a.tokens_today || 0);
  const percent = budget > 0 ? Math.min(100, Math.round((used / budget) * 100)) : 0;

  const cards = [
    { label: "Tutor turns today", value: t.turns ?? 0, note: "one per student message" },
    { label: "Model calls", value: t.llm_calls ?? 0, note: "Gemini generations" },
    {
      label: "Tokens today",
      value: tokens((t.input_tokens || 0) + (t.output_tokens || 0)),
      note: `${tokens(t.input_tokens)} in · ${tokens(t.output_tokens)} out`,
    },
    { label: "Estimated cost", value: money(t.cost_usd), note: "today, at configured prices" },
    {
      label: "Errors",
      value: t.errors ?? 0,
      note: t.errors ? "check the Errors filter" : "none today",
      warn: (t.errors ?? 0) > 0,
    },
    {
      label: "Daily budget",
      value: budget ? `${percent}%` : "off",
      note: budget ? `${tokens(used)} of ${tokens(budget)} tokens` : "set ENGLISH_TEACHER_DAILY_TOKEN_BUDGET",
      warn: budget > 0 && percent >= 100,
    },
  ];

  byId("cards").innerHTML = cards
    .map(
      (card) => `
      <article class="card stat${card.warn ? " warn" : ""}">
        <p class="stat-label">${escapeHtml(card.label)}</p>
        <p class="stat-value">${escapeHtml(card.value)}</p>
        <p class="muted small">${escapeHtml(card.note)}</p>
      </article>`,
    )
    .join("");

  byId("tracingChip").textContent = `tracing: ${data.tracing || "off"}`;
  byId("alertsChip").textContent = a.email_configured
    ? `alerts: ${a.recipient}`
    : "alerts: email off";

  const banner = byId("alertBanner");
  if (budget > 0 && used >= budget) {
    banner.hidden = false;
    banner.innerHTML = `<strong>Daily token budget reached.</strong> ${tokens(used)} of ${tokens(
      budget,
    )} tokens used${a.email_configured ? `, alert mailed to ${escapeHtml(a.recipient)}` : ""}.`;
  } else if (!a.email_configured) {
    banner.hidden = false;
    banner.innerHTML =
      "<strong>Email alerts are off.</strong> Add <code>ALERT_EMAIL_TO</code> and the <code>ALERT_SMTP_*</code> variables to be warned about budget overruns and failures.";
  } else {
    banner.hidden = true;
  }
}

function renderRows(events) {
  const rows = byId("rows");
  const empty = byId("empty");
  rows.innerHTML = events
    .map(
      (event) => `
      <tr class="${event.status === "error" ? "bad" : event.kind === "alert" ? "warn" : ""}">
        <td class="mono">${escapeHtml(clock(event.ts))}</td>
        <td><span class="tag">${escapeHtml(event.kind)}</span></td>
        <td>${escapeHtml(event.name)}</td>
        <td>${escapeHtml(event.user_id || "—")}</td>
        <td class="mono muted">${escapeHtml(event.thread_id || "—")}</td>
        <td class="num">${event.latency_ms ? `${(event.latency_ms / 1000).toFixed(1)}s` : "—"}</td>
        <td class="num">${event.input_tokens ? tokens(event.input_tokens) : "—"}</td>
        <td class="num">${event.output_tokens ? tokens(event.output_tokens) : "—"}</td>
        <td class="num">${event.cost_usd ? money(event.cost_usd) : "—"}</td>
        <td class="detail">${escapeHtml(event.detail || "")}</td>
      </tr>`,
    )
    .join("");
  empty.hidden = events.length > 0;
}

async function load() {
  try {
    const query = `/api/dashboard?limit=100${state.kind ? `&kind=${state.kind}` : ""}`;
    const response = await fetch(query, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderCards(data);
    renderRows(data.events || []);
  } catch (error) {
    byId("empty").hidden = false;
    byId("empty").textContent = `Could not load the dashboard: ${error.message}`;
    byId("rows").innerHTML = "";
  }
}

function schedule() {
  if (state.timer) clearInterval(state.timer);
  state.timer = byId("autoRefresh").checked ? setInterval(load, 5000) : null;
}

byId("filters").addEventListener("click", (event) => {
  const button = event.target.closest(".filter");
  if (!button) return;
  state.kind = button.dataset.kind || "";
  byId("filters")
    .querySelectorAll(".filter")
    .forEach((node) => node.setAttribute("aria-pressed", String(node === button)));
  load();
});

byId("autoRefresh").addEventListener("change", schedule);

load();
schedule();
