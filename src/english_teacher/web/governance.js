const byId = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function fillList(id, items) {
  byId(id).innerHTML = (items || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
}

function renderOwners(owners) {
  const rows = [
    ["Business owner", owners.business],
    ["Technical owner", owners.technical],
  ];
  byId("owners").innerHTML = rows
    .map(
      ([label, owner]) => `
      <article class="gov-owner">
        <p class="stat-label">${escapeHtml(label)}</p>
        <strong>${escapeHtml(owner.name)}</strong>
        <p class="muted small">${escapeHtml(owner.role)}</p>
        <a class="small" href="${escapeHtml(owner.contact)}" rel="noreferrer">${escapeHtml(
          owner.contact,
        )}</a>
      </article>`,
    )
    .join("");
}

function renderCard(card) {
  const suspended = card.status !== "active";
  byId("cardName").textContent = card.name;
  byId("cardSummary").textContent = card.description;
  byId("cardVersion").textContent = `v${card.version}`;
  byId("cardStatus").textContent = card.status;
  byId("cardStatus").classList.toggle("warn", suspended);
  document.title = `${card.name} · Agent Card`;

  const banner = byId("cardBanner");
  if (suspended) {
    banner.hidden = false;
    banner.innerHTML = `<strong>Agent suspended.</strong> ${escapeHtml(
      card.kill_switch?.reason || "Kill switch active.",
    )} New sessions and turns are refused until an operator clears it.`;
  } else {
    banner.hidden = true;
  }

  const facts = [
    { label: "Agent id", value: card.id },
    { label: "Runtime model", value: card.model?.name || "—" },
    { label: "Languages", value: (card.languages || []).map((l) => l.name).join(" · ") },
    {
      label: "Teachers",
      value: (card.languages || []).map((l) => l.teacher).join(" · "),
    },
    {
      label: "Schema",
      value: `Agent Card ${card.schema_version} · API v${card.version}`,
    },
  ];
  byId("cardFacts").innerHTML = facts
    .map(
      (fact) => `
      <article class="card stat">
        <p class="stat-label">${escapeHtml(fact.label)}</p>
        <p class="stat-value compact">${escapeHtml(fact.value)}</p>
      </article>`,
    )
    .join("");

  renderOwners(card.owners);
  fillList("responsibilities", card.responsibilities);
  fillList("limitsIn", card.limits.in_scope);
  fillList("limitsOut", card.limits.out_of_scope);
  fillList("guardrails", card.limits.guardrails);

  byId("resources").innerHTML = (card.resources || [])
    .map(
      (resource) => `
      <tr>
        <td>${escapeHtml(resource.name)}</td>
        <td><span class="tag">${escapeHtml(resource.type)}</span></td>
        <td class="detail">${escapeHtml(resource.purpose)}</td>
      </tr>`,
    )
    .join("");

  const data = card.data_handling;
  const security = card.security;
  byId("dataStudent").textContent = data.student_data;
  byId("dataLogging").textContent = data.prompts;
  byId("dataSecrets").textContent = data.secrets;
  byId("secTransport").textContent = security.transport;
  byId("secAdmin").textContent = security.admin_auth;
  byId("secStudent").textContent = security.student_auth;

  const versioning = card.versioning;
  byId("verScheme").textContent = `${versioning.scheme} · ${versioning.tag_pattern}`;
  byId("verMajor").textContent = versioning.major;
  byId("verMinor").textContent = versioning.minor;
  byId("verPatch").textContent = versioning.patch;

  byId("endpoints").innerHTML = Object.entries(card.endpoints || {})
    .map(
      ([name, path]) => `
      <tr>
        <td>${escapeHtml(name.replaceAll("_", " "))}</td>
        <td class="mono">${escapeHtml(path)}</td>
      </tr>`,
    )
    .join("");

  const repo = "https://github.com/el-abid/english-teacher-agent/blob/main";
  byId("runbookLink").href = `${repo}/${card.runbook}`;
  byId("changelogLink").href = `${repo}/${card.changelog}`;
}

async function load() {
  try {
    const response = await fetch("/api/agent-card", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderCard(await response.json());
  } catch (error) {
    byId("cardBanner").hidden = false;
    byId("cardBanner").textContent = `Could not load the Agent Card: ${error.message}`;
    byId("cardStatus").textContent = "unavailable";
    byId("cardStatus").classList.add("warn");
  }
}

load();
