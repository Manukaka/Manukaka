// People tab — card grid; clicking a card reuses the mind-map person panel.
window.Manu = window.Manu || {};

(function () {
  async function load() {
    const grid = document.getElementById("peopleGrid");
    const people = await (await fetch("/api/people")).json();
    if (!people.length) {
      grid.innerHTML = '<div class="empty">No people yet.<br>' +
        'Process chats, calls or tagged photos to see the people in your life.</div>';
      return;
    }
    grid.innerHTML = people.map((p) => `
      <div class="person-card" onclick="Manu.openPerson('${p.id}')">
        <div class="pname">${p.name}</div>
        <div class="pmeta">${p.msg_count} messages · ${p.photo_count} photos</div>
      </div>`).join("");
  }

  Manu.openPerson = async function (id) {
    const panel = document.getElementById("peoplePanel");
    panel.classList.remove("hidden");
    panel.innerHTML = '<div class="empty">Loading…</div>';
    const res = await fetch("/api/person/" + id);
    panel.innerHTML = res.ok ? Manu.renderPersonPanel(await res.json(), id)
                             : '<div class="empty">No details.</div>';
  };

  Manu.init_people = load;
  Manu.refresh_people = load;
})();
