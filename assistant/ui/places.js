// Places tab — offline map: country outlines from a vendored GeoJSON drawn on a
// canvas (equirectangular projection), with photo-location pins. No tiles, no
// internet. Click a pin to see that place's photos in the strip below.
window.Manu = window.Manu || {};

(function () {
  let world = null, places = [], view = null, hit = [];

  // Equirectangular: lon [-180,180] -> x, lat [90,-90] -> y, fitted to the view box.
  function project(lon, lat, v) {
    return [v.x + (lon - v.lon0) / (v.lon1 - v.lon0) * v.w,
            v.y + (v.lat0 - lat) / (v.lat0 - v.lat1) * v.h];
  }

  function computeView(canvas) {
    // Default: whole world. If all pins cluster (e.g. India), zoom to their bbox.
    let lon0 = -180, lon1 = 180, lat0 = 85, lat1 = -60;
    if (places.length) {
      const lons = places.map((p) => p.lon), lats = places.map((p) => p.lat);
      let mnLon = Math.min(...lons), mxLon = Math.max(...lons);
      let mnLat = Math.min(...lats), mxLat = Math.max(...lats);
      const padX = Math.max(8, (mxLon - mnLon) * 0.3);
      const padY = Math.max(8, (mxLat - mnLat) * 0.3);
      lon0 = mnLon - padX; lon1 = mxLon + padX;
      lat0 = mxLat + padY; lat1 = mnLat - padY;
    }
    return { lon0, lon1, lat0, lat1, x: 0, y: 0, w: canvas.width, h: canvas.height };
  }

  function draw() {
    const canvas = document.getElementById("placesCanvas");
    canvas.width = canvas.clientWidth; canvas.height = canvas.clientHeight;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#0b0d13"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    view = computeView(canvas);

    // Country outlines
    if (world) {
      ctx.strokeStyle = "rgba(120,140,180,0.35)";
      ctx.fillStyle = "rgba(40,50,75,0.5)";
      ctx.lineWidth = 0.6;
      for (const feat of world.features) {
        const polys = feat.geometry.type === "Polygon"
          ? [feat.geometry.coordinates] : feat.geometry.coordinates;
        for (const poly of polys) {
          for (const ring of poly) {
            ctx.beginPath();
            ring.forEach(([lon, lat], i) => {
              const [x, y] = project(lon, lat, view);
              i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
            });
            ctx.closePath(); ctx.fill(); ctx.stroke();
          }
        }
      }
    }

    // Pins (radius scales with photo count)
    hit = [];
    for (const p of places) {
      const [x, y] = project(p.lon, p.lat, view);
      const r = Math.min(22, 6 + Math.sqrt(p.count) * 2);
      ctx.beginPath(); ctx.arc(x, y, r, 0, 7);
      ctx.fillStyle = "rgba(122,162,247,0.75)"; ctx.fill();
      ctx.fillStyle = "#fff"; ctx.font = "11px sans-serif";
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(p.count, x, y);
      hit.push({ x, y, r, place: p });
    }
  }

  function onClick(e) {
    const rect = e.target.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    for (const h of hit) {
      if ((mx - h.x) ** 2 + (my - h.y) ** 2 <= h.r * h.r) { showStrip(h.place); return; }
    }
  }

  function showStrip(place) {
    document.getElementById("placesHint").textContent =
      `${place.name} — ${place.count} photos`;
    document.getElementById("placesStrip").innerHTML = place.photo_ids.map((id) =>
      `<img src="/api/thumb/${id}" onclick="Manu.lightbox('${id}')">`).join("");
  }

  async function load() {
    if (!world) {
      try { world = await (await fetch("/ui/vendor/world-110m.geojson")).json(); }
      catch (e) { world = { features: [] }; }
    }
    places = await (await fetch("/api/places")).json();
    const hint = document.getElementById("placesHint");
    if (!places.length) {
      hint.textContent = "No photo locations yet. Photos with GPS info will appear here as pins.";
    }
    draw();
  }

  Manu.init_places = function () {
    document.getElementById("placesCanvas").addEventListener("click", onClick);
    window.addEventListener("resize", () => { if (places.length || world) draw(); });
    load();
  };
  Manu.refresh_places = load;
})();
