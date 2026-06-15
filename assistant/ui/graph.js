// Mind Map tab — 3D force graph (with 2D toggle) of people / places / events.
window.Manu = window.Manu || {};

(function () {
  const COLORS = { person: "#7aa2f7", place: "#9ece6a", event: "#e0af68", topic: "#bb9af7" };
  let graphData = null, instance = null, is3D = true;

  async function load() {
    const res = await fetch("/api/graph");
    graphData = await res.json();
  }

  function render() {
    const el = document.getElementById("graph");
    el.innerHTML = "";
    if (!graphData || graphData.nodes.length === 0) {
      el.innerHTML = '<div class="empty">Your mind map is empty.<br>' +
        'Process some chats, calls or photos and it will fill up here.</div>';
      return;
    }
    const factory = is3D ? window.ForceGraph3D : window.ForceGraph;
    if (!factory) { el.innerHTML = '<div class="empty">Graph library not loaded.</div>'; return; }
    instance = factory()(el)
      .graphData(graphData)
      .nodeLabel((n) => `${n.name} (${n.type})`)
      .nodeColor((n) => COLORS[n.type] || "#888")
      .nodeVal((n) => n.val || 1)
      .linkColor(() => "rgba(160,170,200,0.25)")
      .linkWidth((l) => Math.min(3, (l.weight || 1) / 5))
      .onNodeClick((n) => { if (n.type === "person") showPerson(n.id); });
    if (is3D && instance.width) instance.width(el.clientWidth).height(el.clientHeight);
  }

  async function showPerson(id) {
    const panel = document.getElementById("sidePanel");
    panel.classList.remove("hidden");
    panel.innerHTML = '<div class="empty">Loading…</div>';
    const res = await fetch("/api/person/" + id);
    if (!res.ok) { panel.innerHTML = '<div class="empty">No details.</div>'; return; }
    panel.innerHTML = Manu.renderPersonPanel(await res.json(), id);
  }

  Manu.renderPersonPanel = function (p, id) {
    const thumbs = p.photos.map((ph) =>
      `<img src="${ph.thumb}" title="${(ph.caption || "").replace(/"/g, "")}" ` +
      `onclick="Manu.lightbox('${ph.photo_id}')">`).join("");
    const sessions = p.recent_sessions.map((s) =>
      `<div class="sess-line">${s.source_type} · ${Manu.fmtDate(s.start_ts)} · ${s.msg_count} msgs</div>`).join("");
    return `
      <span class="panel-close" onclick="this.parentElement.classList.add('hidden')">×</span>
      <h2>${p.name}</h2>
      ${p.relation ? `<div class="panel-relation">${p.relation}</div>` : ""}
      <div class="panel-stats">${p.session_count} conversations · ${p.message_count} messages · ${p.photos.length} photos</div>
      <div class="panel-summary" id="sum-${id}">${p.summary ||
        `<button class="ghost" onclick="Manu.writeSummary('${id}')">✨ Write relationship summary</button>`}</div>
      ${thumbs ? `<div class="thumb-grid">${thumbs}</div>` : ""}
      ${sessions ? `<h3 style="margin-top:12px;font-size:13px;color:var(--muted)">Recent</h3>${sessions}` : ""}`;
  };

  Manu.writeSummary = async function (id) {
    const box = document.getElementById("sum-" + id);
    if (box) box.innerHTML = "Thinking…";
    const res = await fetch("/api/person/" + id + "/summary", { method: "POST" });
    if (box) box.textContent = res.ok ? (await res.json()).summary : "Couldn't write a summary right now.";
  };

  Manu.init_mindmap = async function () {
    await load();
    render();
    document.getElementById("dimToggle").addEventListener("click", (e) => {
      is3D = !is3D;
      e.target.textContent = is3D ? "Switch to 2D" : "Switch to 3D";
      render();
    });
  };
  Manu.refresh_mindmap = async function () { await load(); render(); };
})();
