// Tab switching + small shared helpers used by every tab module.
window.Manu = window.Manu || {};

Manu.fmtDate = function (ts) {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleDateString(undefined,
    { day: "numeric", month: "short", year: "numeric" });
};

Manu.lightbox = function (photoId) {
  const box = document.getElementById("lightbox");
  document.getElementById("lightboxImg").src = "/api/photo/" + photoId;
  box.classList.remove("hidden");
};

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("lightbox").addEventListener("click", (e) => {
    e.currentTarget.classList.add("hidden");
  });

  const initialized = {};
  const tabs = document.querySelectorAll(".tab");
  tabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      const name = btn.dataset.tab;
      tabs.forEach((b) => b.classList.toggle("active", b === btn));
      document.querySelectorAll(".tabpane").forEach((p) => {
        p.classList.toggle("active", p.id === "tab-" + name);
      });
      // Lazily init a tab the first time it's opened, then refresh on re-open.
      const fn = Manu["init_" + name];
      if (fn) {
        if (!initialized[name]) { fn(); initialized[name] = true; }
        else if (Manu["refresh_" + name]) Manu["refresh_" + name]();
      }
    });
  });
});
