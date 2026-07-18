// RAGNAR — stores directory + live hub.
"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(p) { const r = await fetch(p); if (!r.ok) throw new Error("Request failed"); return r.json(); }

function accentGrad(color) {
  const c = color || "#6f93b4";
  return `linear-gradient(135deg, ${c}33, #0a0d12), radial-gradient(circle at 30% 20%, ${c}55, transparent 60%)`;
}
function initial(name) { return (name || "?").trim()[0].toUpperCase(); }

async function loadLive() {
  try {
    const streams = await api("/api/streams");
    const row = $("liveRow");
    if (!streams.length) {
      $("liveTitle").style.opacity = ".6";
      row.innerHTML = `<p class="muted" style="grid-column:1/-1;">No live streams right now. Sellers can go live from their store — real broadcasting turns on once a video provider is connected.</p>`;
      return;
    }
    row.innerHTML = streams.map((s) => {
      const live = s.status === "live";
      return `<div class="live-card" data-handle="${esc(s.seller_handle)}">
        <div class="live-thumb" style="background:${accentGrad(s.accent_color)}">
          <span class="live-badge ${live ? "" : "sched"}">${live ? "● LIVE" : "SCHEDULED"}</span>
          ${live ? `<span class="live-views">👁 ${s.viewer_count}</span>` : ""}
          <svg width="46" height="46" viewBox="0 0 24 24" fill="none" style="opacity:.85"><circle cx="12" cy="12" r="11" stroke="#eaf3fb" stroke-width="1.2"/><path d="M10 8l6 4-6 4V8z" fill="#eaf3fb"/></svg>
        </div>
        <div class="live-meta"><div class="lt">${esc(s.title)}</div><div class="ls">${esc(s.seller_name)}</div></div>
      </div>`;
    }).join("");
    row.querySelectorAll("[data-handle]").forEach((el) => el.addEventListener("click", () => { location.href = `/store/${el.getAttribute("data-handle")}`; }));
  } catch (_) { $("liveRow").innerHTML = `<p class="muted">Could not load live streams.</p>`; }
}

async function loadStores(q) {
  try {
    const stores = await api(`/api/stores${q ? `?q=${encodeURIComponent(q)}` : ""}`);
    const grid = $("storeGrid");
    if (!stores.length) { grid.innerHTML = `<p class="muted">No stores found.</p>`; return; }
    grid.innerHTML = stores.map((s) => `
      <div class="store-card" data-handle="${esc(s.handle)}">
        <div class="store-banner" style="background:${s.banner_url ? `center/cover url('${esc(s.banner_url)}')` : accentGrad(s.accent_color)}">
          <div class="store-avatar" style="background:${s.avatar_url ? `center/cover url('${esc(s.avatar_url)}')` : (s.accent_color || "#6f93b4")}">${s.avatar_url ? "" : initial(s.display_name)}</div>
        </div>
        <div class="store-body">
          <div class="store-name">${esc(s.display_name)} ${s.is_live ? '<span class="live-dot"></span>' : ""} ${s.is_founding ? `<span class="badge founding">★ #${s.founding_number}</span>` : ""}</div>
          <div class="store-tag">${esc(s.tagline || "")}</div>
          <div class="store-foot"><span>${s.listing_count} listing${s.listing_count === 1 ? "" : "s"}</span><span>Visit →</span></div>
        </div>
      </div>`).join("");
    grid.querySelectorAll("[data-handle]").forEach((el) => el.addEventListener("click", () => { location.href = `/store/${el.getAttribute("data-handle")}`; }));
  } catch (_) { $("storeGrid").innerHTML = `<p class="muted">Could not load stores.</p>`; }
}

let t;
document.addEventListener("DOMContentLoaded", () => {
  loadLive();
  loadStores("");
  $("storeSearch").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => loadStores(e.target.value.trim()), 300); });
});
