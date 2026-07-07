const chatEl = document.getElementById("chat");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");
const ingestBtn = document.getElementById("ingestBtn");
const ingestPanel = document.getElementById("ingestPanel");
const ingestLog = document.getElementById("ingestLog");
const healthEl = document.getElementById("health");

let history = []; // [{role, content}]
let busy = false;

function addBubble(role, text) {
  const msg = document.createElement("div");
  msg.className = "msg " + role;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  msg.appendChild(bubble);
  chatEl.appendChild(msg);
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

// Minimal markdown: bold + inline code (we render offline, no libraries)
function renderMd(el, text) {
  let safe = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  safe = safe
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
  el.innerHTML = safe;
}

// Sources footer under an answer: only the excerpts the model actually
// cited as [n]; if it cited nothing, stay quiet rather than list guesses.
// Call sources are clickable and open their transcript.
function addSources(bubble, sources, answer) {
  const cited = sources.filter((s) => answer.includes("[" + s.n + "]"));
  if (!cited.length) return;
  const box = document.createElement("div");
  box.className = "sources";
  box.append("📎 ");
  cited.forEach((s, i) => {
    if (i) box.append(" · ");
    const chip = document.createElement("span");
    chip.textContent = "[" + s.n + "] " + s.label;
    if (s.type === "call" && s.file) {
      chip.className = "source-link";
      chip.title = "Open the call transcript";
      chip.addEventListener("click", () => openTranscript(s.file));
    }
    box.appendChild(chip);
  });
  bubble.appendChild(box);
}

async function openTranscript(file) {
  const stem = file.replace(/\.[^.]+$/, "");
  showInfo("Loading transcript…");
  try {
    const res = await fetch("/api/transcripts/" + encodeURIComponent(stem));
    if (!res.ok) { showInfo("Transcript not found."); return; }
    const data = await res.json();
    showInfo("<h3>📞 " + esc(stem) + "</h3><pre class='transcript'>" +
      esc(data.text) + "</pre>");
  } catch (e) {
    showInfo("⚠ " + esc(e.message));
  }
}

async function send() {
  const text = inputEl.value.trim();
  if (!text || busy) return;
  busy = true;
  sendBtn.disabled = true;
  inputEl.value = "";
  addBubble("user", text);
  const bubble = addBubble("assistant", "…");

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      bubble.textContent = err.detail || "Something went wrong (" + res.status + ").";
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let answer = "", buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const events = buf.split("\n\n");
      buf = events.pop();
      for (const ev of events) {
        if (!ev.startsWith("data: ")) continue;
        const data = JSON.parse(ev.slice(6));
        if (data.delta) {
          answer += data.delta;
          renderMd(bubble, answer);
          chatEl.scrollTop = chatEl.scrollHeight;
        }
        if (data.sources) addSources(bubble, data.sources, answer);
        if (data.error) bubble.textContent = "Error: " + data.error;
      }
    }
    if (answer) {
      history.push({ role: "user", content: text });
      history.push({ role: "assistant", content: answer });
      history = history.slice(-16);
    }
  } catch (e) {
    bubble.textContent = "Connection error: " + e.message;
  } finally {
    busy = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

sendBtn.addEventListener("click", send);
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});

// ---- Ingestion ----
ingestBtn.addEventListener("click", async () => {
  const res = await fetch("/api/ingest", { method: "POST" });
  if (res.status === 409) return;
  ingestPanel.classList.remove("hidden");
  pollStatus();
});

let pollTimer = null;
async function pollStatus() {
  if (pollTimer) clearTimeout(pollTimer);
  const res = await fetch("/api/status");
  const data = await res.json();
  ingestLog.textContent = data.log.join("\n");
  ingestPanel.scrollTop = ingestPanel.scrollHeight;
  ingestBtn.disabled = data.running;
  if (data.running) {
    pollTimer = setTimeout(pollStatus, 1500);
  } else {
    refreshHealth();
    setTimeout(() => ingestPanel.classList.add("hidden"), 8000);
  }
}

// ---- Info panels: Upcoming / People / Digest ----
const infoPanel = document.getElementById("infoPanel");
const infoContent = document.getElementById("infoContent");
document.getElementById("infoClose").addEventListener("click", () =>
  infoPanel.classList.add("hidden"));

function showInfo(html) {
  infoContent.innerHTML = html;
  infoPanel.classList.remove("hidden");
}

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

document.getElementById("upcomingBtn").addEventListener("click", async () => {
  showInfo("Loading…");
  const data = await (await fetch("/api/upcoming")).json();
  let html = "<h3>📅 Upcoming</h3>";
  if (!data.due.length && !data.undated.length) {
    html += "<p class='muted'>No commitments found yet — process some files first.</p>";
  }
  for (const c of data.due) {
    html += "<div class='row'><b>" + esc(c.due_date) + "</b> — " + esc(c.what) +
      (c.with_whom ? " <span class='muted'>(with " + esc(c.with_whom) + ")</span>" : "") +
      "</div>";
  }
  if (data.undated.length) {
    html += "<h4>No date, but mentioned recently</h4>";
    for (const c of data.undated) {
      html += "<div class='row'>" + esc(c.what) +
        (c.due_text ? " <span class='muted'>(" + esc(c.due_text) + ")</span>" : "") +
        "</div>";
    }
  }
  showInfo(html);
});

document.getElementById("peopleBtn").addEventListener("click", async () => {
  showInfo("Loading…");
  const data = await (await fetch("/api/contacts")).json();
  let html = "<h3>👥 People</h3>";
  if (!data.contacts.length) {
    html += "<p class='muted'>No conversations indexed yet.</p>";
  }
  for (const p of data.contacts) {
    const when = p.last_ts ? new Date(p.last_ts * 1000).toLocaleDateString() : "—";
    html += "<div class='row'><b>" + esc(p.name) + "</b> <span class='muted'>· last " +
      esc(when) + " · " + p.chunks + " memories · " + esc(p.sources.join(", ")) + "</span>";
    for (const f of p.facts.slice(0, 4)) html += "<div class='fact'>" + esc(f) + "</div>";
    html += "</div>";
  }
  showInfo(html);
});

document.getElementById("digestBtn").addEventListener("click", async () => {
  showInfo("✍️ Writing your digest — this can take a minute…");
  try {
    const res = await fetch("/api/digest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ days: 7 }),
    });
    const data = await res.json();
    if (!res.ok) { showInfo("⚠ " + esc(data.detail || "Digest failed")); return; }
    if (!data.digest) { showInfo(esc(data.message || "Nothing to digest yet.")); return; }
    infoPanel.classList.add("hidden");
    const bubble = addBubble("assistant", "");
    renderMd(bubble, "**📋 Your last 7 days**\n\n" + data.digest);
  } catch (e) {
    showInfo("⚠ " + esc(e.message));
  }
});

// ---- Restore persisted chat on load ----
async function restoreHistory() {
  try {
    const res = await fetch("/api/history?limit=40");
    const data = await res.json();
    for (const m of data.messages) {
      const bubble = addBubble(m.role === "user" ? "user" : "assistant", "");
      renderMd(bubble, m.content);
    }
    history = data.messages.slice(-16);
  } catch { /* fresh chat is fine */ }
}
restoreHistory();

// ---- Health ----
async function refreshHealth() {
  try {
    const res = await fetch("/api/health");
    const h = await res.json();
    if (!h.ollama) {
      healthEl.textContent = "⚠ Ollama not running";
      healthEl.className = "health bad";
    } else if (!h.model_available) {
      healthEl.textContent = "⚠ model missing — run: ollama pull " + h.model;
      healthEl.className = "health bad";
    } else {
      healthEl.textContent = h.chunks + " memories indexed · " + h.model;
      healthEl.className = "health ok";
    }
    if (h.ingesting) { ingestPanel.classList.remove("hidden"); pollStatus(); }
  } catch {
    healthEl.textContent = "server unreachable";
    healthEl.className = "health bad";
  }
}
refreshHealth();
setInterval(refreshHealth, 30000);
inputEl.focus();
