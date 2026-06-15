// Timeline tab — infinite-scroll mixed feed of photos, calls and chats.
window.Manu = window.Manu || {};

(function () {
  const ICONS = { call: "📞", chat: "💬", photo: "🖼" };
  let cursor = null, loading = false, done = false, started = false;

  function monthKey(ts) {
    return new Date(ts * 1000).toLocaleDateString(undefined, { month: "long", year: "numeric" });
  }

  function itemHTML(it) {
    const media = it.type === "photo" && it.thumb
      ? `<img src="${it.thumb}" onclick="Manu.lightbox('${it.photo_id}')">`
      : `<div class="tl-icon">${ICONS[it.type] || "•"}</div>`;
    return `<div class="tl-item">${media}
      <div><div class="tl-title">${it.title}</div>
      <div class="tl-sub">${it.subtitle || ""}</div></div>
      <div class="tl-date">${Manu.fmtDate(it.ts)}</div></div>`;
  }

  async function loadMore() {
    if (loading || done) return;
    loading = true;
    const url = "/api/timeline?limit=60" + (cursor ? "&before_ts=" + cursor : "");
    const data = await (await fetch(url)).json();
    const root = document.getElementById("timeline");
    if (!data.items.length && !cursor) {
      root.innerHTML = '<div class="empty">Nothing on your timeline yet.<br>' +
        'Process photos, calls or chats to see them here by date.</div>';
      done = true; loading = false; return;
    }
    let lastMonth = root.dataset.lastMonth || "";
    let html = "";
    for (const it of data.items) {
      const mk = monthKey(it.ts);
      if (mk !== lastMonth) { html += `<div class="tl-month">${mk}</div>`; lastMonth = mk; }
      html += itemHTML(it);
    }
    root.dataset.lastMonth = lastMonth;
    root.insertAdjacentHTML("beforeend", html);
    cursor = data.next_before_ts;
    if (!cursor || data.items.length < 60) done = true;
    loading = false;
  }

  Manu.init_timeline = function () {
    if (started) return;
    started = true;
    const root = document.getElementById("timeline");
    root.addEventListener("scroll", () => {
      if (root.scrollTop + root.clientHeight > root.scrollHeight - 200) loadMore();
    });
    loadMore();
  };
  Manu.refresh_timeline = function () {
    const root = document.getElementById("timeline");
    root.innerHTML = ""; root.dataset.lastMonth = "";
    cursor = null; done = false; loadMore();
  };
})();
