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
function addSources(bubble, sources, answer) {
  const cited = sources.filter((s) => answer.includes("[" + s.n + "]"));
  if (!cited.length) return;
  const box = document.createElement("div");
  box.className = "sources";
  box.textContent = "📎 " + cited.map((s) => "[" + s.n + "] " + s.label).join(" · ");
  bubble.appendChild(box);
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
