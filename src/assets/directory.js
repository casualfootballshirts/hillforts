(function () {
  const mapEl = document.getElementById("map");
  if (!mapEl || !window.L) return;

  const labels = {
    contour: "Contour",
    "partial-contour": "Partial contour",
    promontory: "Promontory",
    hillslope: "Hillslope",
    level: "Level terrain",
    marsh: "Marsh",
    multiple: "Multiple enclosure",
    extant: "Extant",
    cropmark: "Cropmark",
    destroyed: "Likely destroyed",
    univallate: "Univallate",
    bivallate: "Bivallate",
    multivallate: "Multivallate",
  };

  L.Icon.Default.mergeOptions({
    iconUrl: "/assets/vendor/images/marker-icon.png",
    iconRetinaUrl: "/assets/vendor/images/marker-icon-2x.png",
    shadowUrl: "/assets/vendor/images/marker-shadow.png",
  });

  const map = L.map(mapEl, { scrollWheelZoom: mapEl.dataset.scroll === "1" });
  if (mapEl.dataset.scroll !== "1") {
    map.scrollWheelZoom.disable();
    map.on("click", function () {
      map.scrollWheelZoom.enable();
    });
  }

  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  if (mapEl.dataset.mode === "site") {
    const lat = parseFloat(mapEl.dataset.lat);
    const lon = parseFloat(mapEl.dataset.lon);
    const marker = L.marker([lat, lon]).addTo(map);
    const popup = document.createElement("div");
    popup.textContent = mapEl.dataset.name || "Hillfort";
    marker.bindPopup(popup);
    map.setView([lat, lon], 15);
    return;
  }

  const form = document.querySelector("[data-filters]");
  const list = document.getElementById("results");
  const countEl = document.querySelector("[data-count]");
  const dynamic = list && list.dataset.dynamic === "1";
  const staticItems = dynamic ? [] : Array.from(document.querySelectorAll("[data-site]"));
  const country = mapEl.dataset.country || "";
  const county = mapEl.dataset.county || "";

  function popupNode(site) {
    const wrap = document.createElement("div");
    wrap.className = "popup";
    const link = document.createElement("a");
    link.href = "/sites/" + site.slug + "/";
    link.textContent = site.name;
    const meta = document.createElement("div");
    meta.textContent = [site.county, site.country].filter(Boolean).join(", ");
    wrap.append(link, meta);
    return wrap;
  }

  function card(site) {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = "/sites/" + site.slug + "/";
    link.textContent = site.name;
    const meta = document.createElement("span");
    const bits = [site.county];
    (site.condition || []).forEach(function (code) {
      if (labels[code]) bits.push(labels[code]);
    });
    (site.types || []).slice(0, 2).forEach(function (code) {
      if (labels[code]) bits.push(labels[code]);
    });
    meta.textContent = bits.filter(Boolean).join(" · ");
    item.append(link, meta);
    return item;
  }

  function selected(name) {
    if (!form) return [];
    return Array.from(form.querySelectorAll('input[name="' + name + '"]:checked')).map(function (input) {
      return input.value;
    });
  }

  function filters() {
    const queryInput = form ? form.querySelector('[name="q"]') : null;
    const scheduled = form ? form.querySelector('input[name="scheduled"]:checked') : null;
    return {
      q: queryInput ? queryInput.value.trim().toLowerCase() : "",
      types: selected("type"),
      condition: selected("condition"),
      morph: selected("morph"),
      scheduled: scheduled ? scheduled.value : "",
    };
  }

  function matches(record, state) {
    if (state.q && !(record.search || "").includes(state.q)) return false;
    if (state.types.length && !state.types.some(function (value) { return record.types.indexOf(value) !== -1; })) return false;
    if (state.condition.length && !state.condition.some(function (value) { return record.condition.indexOf(value) !== -1; })) return false;
    if (state.morph.length && !state.morph.some(function (value) { return record.morph.indexOf(value) !== -1; })) return false;
    if (state.scheduled === "yes" && !record.scheduled) return false;
    if (state.scheduled === "no" && record.scheduled) return false;
    return true;
  }

  function fromItem(item) {
    return {
      slug: item.dataset.slug,
      search: item.dataset.search || "",
      types: (item.dataset.types || "").split(" ").filter(Boolean),
      condition: (item.dataset.condition || "").split(" ").filter(Boolean),
      morph: (item.dataset.morph || "").split(" ").filter(Boolean),
      scheduled: item.dataset.scheduled === "1",
    };
  }

  fetch("/data/map.json")
    .then(function (response) { return response.json(); })
    .then(function (data) {
      const sites = data.sites.filter(function (site) {
        if (country && site.country !== country) return false;
        if (county && site.county !== county) return false;
        return true;
      });
      const group = L.markerClusterGroup({
        chunkedLoading: false,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        maxClusterRadius: 55,
      });
      const markers = new Map();
      sites.forEach(function (site) {
        const marker = L.marker([site.lat, site.lon]);
        marker.bindPopup(popupNode(site));
        markers.set(site.slug, marker);
      });
      map.addLayer(group);
      if (!sites.length) map.setView([54.5, -4], 5);

      let timer = 0;
      let fitted = false;
      function apply() {
        const state = filters();
        const slugs = [];
        if (dynamic) {
          const matched = sites.filter(function (site) { return matches(site, state); });
          slugs.push.apply(slugs, matched.map(function (site) { return site.slug; }));
          if (list) {
            list.replaceChildren();
            matched.slice(0, 300).forEach(function (site) {
              list.append(card(site));
            });
          }
          if (countEl) {
            const extra = matched.length > 300 ? " Showing the first 300." : "";
            countEl.textContent = matched.length + " of " + sites.length + " sites." + extra;
          }
        } else {
          let shown = 0;
          staticItems.forEach(function (item) {
            const record = fromItem(item);
            const ok = matches(record, state);
            item.hidden = !ok;
            if (ok) {
              shown += 1;
              slugs.push(record.slug);
            }
          });
          if (countEl) countEl.textContent = shown + " of " + staticItems.length + " sites";
        }
        const next = [];
        slugs.forEach(function (slug) {
          const marker = markers.get(slug);
          if (marker) next.push(marker);
        });
        group.clearLayers();
        if (next.length) {
          group.addLayers(next);
          if (!fitted) {
            map.fitBounds(group.getBounds().pad(0.08));
            fitted = true;
          }
        }
      }

      if (form) {
        form.addEventListener("submit", function (event) { event.preventDefault(); });
        form.addEventListener("input", function () {
          window.clearTimeout(timer);
          timer = window.setTimeout(apply, 120);
        });
        form.addEventListener("reset", function () {
          window.setTimeout(apply, 0);
        });
      }
      apply();
    })
    .catch(function () {
      if (countEl) countEl.textContent = "The map data could not be loaded.";
    });
})();
