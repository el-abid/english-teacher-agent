const FALLBACK_LEVELS = [
  { code: "A1", label: "Beginner" },
  { code: "A2", label: "Elementary" },
  { code: "B1", label: "Intermediate" },
  { code: "B2", label: "Upper-intermediate" },
  { code: "C1", label: "Advanced" },
  { code: "C2", label: "Proficient" },
];

const PHASE_LABEL = {
  placement: "placement check",
  teaching: "lesson",
  exam_offer: "exam offered",
  exam: "exam in progress",
  review: "results",
  done: "finished",
  idle: "ready",
};

const STORAGE_KEY = "english-teacher.thread";
const store = {
  thread: localStorage.getItem(STORAGE_KEY),
  busy: false,
  lastReply: "",
  levels: FALLBACK_LEVELS,
};

const byId = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatText(value) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/^\s*[-*]\s+/gm, "• ")
    .replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      /* keep statusText */
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

/* ------------------------------------------------------------------- chat */
function addBubble(role, text) {
  const chat = byId("chat");
  const wrapper = document.createElement("div");
  wrapper.className = `msg ${role}`;

  const from = document.createElement("p");
  from.className = "from";
  from.textContent = role === "student" ? "You" : role === "teacher" ? "Ms. Rivera" : "System";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = formatText(text);

  wrapper.append(from, bubble);
  chat.append(wrapper);
  scrollChatToBottom();
  return wrapper;
}

function scrollChatToBottom() {
  // Layout settles over a few frames (fonts, wrapped text, the composer), so
  // pin the newest message for a short window instead of once.
  const chat = byId("chat");
  const pin = () => {
    chat.scrollTop = chat.scrollHeight;
  };
  pin();
  for (let tick = 1; tick <= 10; tick += 1) setTimeout(pin, tick * 40);
}

let thinkingBubble = null;

function setThinking(on) {
  if (on) {
    if (thinkingBubble) return;
    thinkingBubble = document.createElement("div");
    thinkingBubble.className = "msg teacher thinking";
    thinkingBubble.innerHTML =
      '<p class="from">Ms. Rivera</p><div class="bubble"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>';
    byId("chat").append(thinkingBubble);
    scrollChatToBottom();
  } else if (thinkingBubble) {
    thinkingBubble.remove();
    thinkingBubble = null;
  }
}

function setBusy(on) {
  store.busy = on;
  byId("sendBtn").disabled = on;
  byId("startBtn").disabled = on;
  byId("input").disabled = on;
}

/* ----------------------------------------------------------------- status */
function renderSkills(mastery) {
  const list = byId("skills");
  list.innerHTML = "";
  Object.entries(mastery || {}).forEach(([skill, percent]) => {
    const item = document.createElement("li");
    item.innerHTML = `
      <span class="name">${escapeHtml(skill)}</span>
      <span class="bar"><span style="width:${Math.max(2, percent)}%"></span></span>
      <span class="value">${percent}%</span>`;
    list.append(item);
  });
}

function renderResult(result) {
  const box = byId("resultBox");
  if (!result) {
    box.hidden = true;
    return;
  }
  const failures = (result.failed_points || []).slice(0, 3);
  box.className = `result ${result.passed ? "pass" : "fail"}`;
  box.innerHTML = `
    <strong>Last exam: ${result.passed ? "passed" : "not passed"} · ${result.score}%</strong>
    <p class="muted">${escapeHtml(result.summary || "")}</p>
    ${
      failures.length
        ? `<ul>${failures.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul>`
        : ""
    }`;
  box.hidden = false;
}

function updateStatus(snapshot) {
  byId("statusCard").hidden = false;
  byId("resetBtn").hidden = false;
  byId("levelChip").textContent = snapshot.level || "—";
  byId("phaseChip").textContent = PHASE_LABEL[snapshot.phase] || snapshot.phase || "ready";
  byId("topicLabel").textContent = snapshot.topic || "Warm-up";

  const total = snapshot.topics_total || 5;
  const done = Math.min(snapshot.lessons_completed || 0, total);
  byId("topicBar").style.width = `${Math.round((done / total) * 100)}%`;
  byId("topicCount").textContent = `${done} of ${total} topics completed at ${snapshot.level}`;

  renderSkills(snapshot.mastery);
  renderResult(snapshot.exam_result);
  byId("threadTag").textContent = snapshot.thread_id || "";
}

/* --------------------------------------------------------------- session */
function showBoot() {
  byId("boot").hidden = false;
  byId("composer").hidden = true;
  byId("chat").innerHTML = "";
  store.thread = null;
  store.lastReply = "";
  localStorage.removeItem(STORAGE_KEY);
}

function finishSession(snapshot) {
  byId("composer").hidden = true;
  addBubble(
    "notice",
    snapshot.graduated
      ? "You finished C2. Start over if you want to keep practising."
      : "Session paused. Start over to begin a new one.",
  );
}

function adopt(snapshot, { replay = false } = {}) {
  store.thread = snapshot.thread_id;
  localStorage.setItem(STORAGE_KEY, snapshot.thread_id);
  byId("boot").hidden = true;
  updateStatus(snapshot);

  if (replay) {
    byId("chat").innerHTML = "";
    store.lastReply = "";
    const history = snapshot.history || [];
    history.forEach((line) => {
      addBubble(line.role === "student" ? "student" : "teacher", line.text);
    });
    const spoken = history.filter((line) => line.role === "teacher");
    store.lastReply = spoken.length ? spoken[spoken.length - 1].text : "";
  }

  if (snapshot.reply && snapshot.reply !== store.lastReply) {
    addBubble("teacher", snapshot.reply);
    store.lastReply = snapshot.reply;
  }

  if (snapshot.awaiting) {
    byId("composer").hidden = false;
    byId("input").focus();
  } else {
    finishSession(snapshot);
  }

  scrollChatToBottom();
}

function renderLevelPicker() {
  const picker = byId("levelPicker");
  picker.querySelectorAll(".level").forEach((node) => node.remove());
  store.levels.forEach(({ code, label }) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "level";
    button.dataset.code = code;
    button.setAttribute("aria-pressed", code === "B1" ? "true" : "false");
    button.innerHTML = `<strong>${escapeHtml(code)}</strong><span>${escapeHtml(label)}</span>`;
    button.addEventListener("click", () => {
      picker.querySelectorAll(".level").forEach((node) => node.setAttribute("aria-pressed", "false"));
      button.setAttribute("aria-pressed", "true");
    });
    picker.append(button);
  });
}

function selectedLevel() {
  const active = document.querySelector('.level[aria-pressed="true"]');
  return active ? active.dataset.code : "B1";
}

async function startSession(event) {
  event.preventDefault();
  byId("bootError").hidden = true;
  setBusy(true);

  try {
    const snapshot = await api("/api/sessions", {
      method: "POST",
      body: JSON.stringify({
        name: byId("nameInput").value,
        goal: byId("goalInput").value,
        level: selectedLevel(),
      }),
    });
    byId("chat").innerHTML = "";
    adopt(snapshot);
  } catch (error) {
    byId("bootError").textContent = error.message;
    byId("bootError").hidden = false;
  } finally {
    setBusy(false);
  }
}

async function sendMessage(event) {
  event.preventDefault();
  const input = byId("input");
  const text = input.value.trim();
  if (!text || store.busy) return;

  input.value = "";
  input.style.height = "auto";
  addBubble("student", text);
  setBusy(true);
  setThinking(true);

  try {
    const snapshot = await api(`/api/sessions/${store.thread}/messages`, {
      method: "POST",
      body: JSON.stringify({ message: text }),
    });
    adopt(snapshot);
  } catch (error) {
    if (error.status === 404 || error.status === 409) {
      addBubble("system", `${error.message}. Starting a new session.`);
      showBoot();
    } else {
      addBubble("system", error.message);
      input.value = text;
    }
  } finally {
    setThinking(false);
    setBusy(false);
    if (byId("composer").hidden === false) input.focus();
  }
}

/* ------------------------------------------------------------------- boot */
function settleChatScroll() {
  // Styles and webfonts can land after the transcript is built, which changes
  // the chat height. Re-pin to the newest message once the page is settled.
  scrollChatToBottom();
  if (document.readyState === "complete") return;
  window.addEventListener("load", scrollChatToBottom, { once: true });
  document.fonts?.ready.then(scrollChatToBottom).catch(() => {});
}

async function boot() {
  try {
    store.levels = await api("/api/levels");
  } catch {
    store.levels = FALLBACK_LEVELS;
  }
  renderLevelPicker();

  if (store.thread) {
    try {
      const snapshot = await api(`/api/sessions/${store.thread}`);
      adopt(snapshot, { replay: true });
      settleChatScroll();
      return;
    } catch {
      store.thread = null;
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  byId("boot").hidden = false;
}

byId("startForm").addEventListener("submit", startSession);
byId("composer").addEventListener("submit", sendMessage);

byId("input").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    byId("composer").requestSubmit();
  }
});

byId("input").addEventListener("input", (event) => {
  const field = event.target;
  field.style.height = "auto";
  field.style.height = `${Math.min(field.scrollHeight, 180)}px`;
});

byId("resetBtn").addEventListener("click", () => {
  localStorage.removeItem(STORAGE_KEY);
  window.location.reload();
});

boot();
