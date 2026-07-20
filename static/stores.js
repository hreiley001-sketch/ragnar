// RAGNAR — stores directory + live hub.
"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let toastTimer;
function toast(msg) {
  const el = $("toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2400);
}

async function api(p, o = {}) {
  const r = await fetch(p, { ...o, headers: { "Content-Type": "application/json", ...(o.headers || {}) } });
  const d = await r.json().catch(() => null);
  if (!r.ok) throw new Error((d && (d.detail || d.error)) || "Request failed");
  return d;
}

function accentGrad(color) {
  const c = color || "var(--color-accent-fallback)";
  return `linear-gradient(135deg, color-mix(in srgb, ${c} 24%, transparent), var(--color-bg-base)), radial-gradient(circle at 30% 20%, color-mix(in srgb, ${c} 38%, transparent), transparent 60%)`;
}
function initial(name) { return (name || "?").trim()[0].toUpperCase(); }

function countdownText(iso) {
  if (!iso) return "Scheduled";
  const target = new Date(iso).getTime();
  const diff = target - Date.now();
  if (Number.isNaN(target)) return "Scheduled";
  if (diff <= 0) return "Starting soon";
  const mins = Math.floor(diff / 60000);
  const days = Math.floor(mins / 1440);
  const hours = Math.floor((mins % 1440) / 60);
  const rem = mins % 60;
  if (days > 0) return `Starts in ${days}d ${hours}h`;
  if (hours > 0) return `Starts in ${hours}h ${rem}m`;
  return `Starts in ${Math.max(rem, 1)}m`;
}

let LAST_STREAMS = [];
let IS_SIGNED_IN = false;

function bindCardLinkBehavior(nodes, onOpen) {
  nodes.forEach((el) => {
    el.addEventListener("click", onOpen);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onOpen.call(el, e);
      }
    });
  });
}

function renderLive(streams) {
  const row = $("liveRow");
  if (!streams.length) {
    $("liveTitle").classList.add("is-quiet");
    row.innerHTML = `<p class="muted live-empty">No live streams right now. Sellers can go live from their store — real broadcasting turns on once a video provider is connected.</p>`;
    return;
  }
  row.innerHTML = streams.map((s) => {
    const live = s.status === "live";
    const count = !live ? `<span class="live-chip" data-countdown="${esc(s.scheduled_at || "")}">${esc(countdownText(s.scheduled_at))}</span>` : "";
    const notify = !live
      ? `<button class="notify-btn ${s.is_notifying ? "on" : ""}" data-notify="${s.id}">${s.is_notifying ? "Notifying" : "Notify me"}</button>`
      : "";
    return `<div class="live-card" data-handle="${esc(s.seller_handle)}" role="link" tabindex="0" aria-label="Open ${esc(s.seller_name)} store">
      <div class="live-thumb" style="background:${accentGrad(s.accent_color)}">
        <span class="live-badge ${live ? "" : "sched"}">${live ? "● LIVE" : "SCHEDULED"}</span>
        ${live ? `<span class="live-views">${s.viewer_count} watching</span>` : ""}
        <svg class="live-play-icon" width="46" height="46" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="11" stroke="currentColor" stroke-width="1.2"/><path d="M10 8l6 4-6 4V8z" fill="currentColor"/></svg>
      </div>
      <div class="live-meta"><div class="lt">${esc(s.title)}</div><div class="ls"><span>${esc(s.seller_name)}</span><span>${live ? "Join stream →" : "View store →"}</span></div><div class="live-meta-actions">${count}${notify}</div></div>
    </div>`;
  }).join("");

  bindCardLinkBehavior(row.querySelectorAll("[data-handle]"), function () {
    location.href = `/store/${this.getAttribute("data-handle")}`;
  });
  row.querySelectorAll("[data-notify]").forEach((el) => el.addEventListener("click", toggleNotify));
}

async function loadLive() {
  try {
    LAST_STREAMS = await api("/api/streams");
    renderLive(LAST_STREAMS);
  } catch (err) {
    $("liveRow").innerHTML = `<p class="muted">Could not load live streams: ${esc(err.message || "Unknown error")}.</p>`;
  }
}

function refreshCountdowns() {
  document.querySelectorAll("[data-countdown]").forEach((el) => {
    const iso = el.getAttribute("data-countdown");
    el.textContent = countdownText(iso);
  });
}

async function toggleNotify(e) {
  e.stopPropagation();
  const btn = e.currentTarget;
  const streamId = Number(btn.getAttribute("data-notify"));
  if (!streamId) return;
  if (!IS_SIGNED_IN) {
    toast("Sign in to set stream reminders.");
    return;
  }
  const next = !btn.classList.contains("on");
  try {
    await api(`/api/streams/${streamId}/notify`, {
      method: "POST",
      body: JSON.stringify({ enabled: next }),
    });
    btn.classList.toggle("on", next);
    btn.textContent = next ? "Notifying" : "Notify me";
    toast(next ? "Reminder on." : "Reminder removed.");
  } catch (err) {
    toast(err.message || "Could not update reminder.");
  }
}

async function loadStores(q) {
  try {
    const stores = await api(`/api/stores${q ? `?q=${encodeURIComponent(q)}` : ""}`);
    const grid = $("storeGrid");
    if (!stores.length) { grid.innerHTML = `<p class="muted">No stores found.</p>`; return; }
    grid.innerHTML = stores.map((s) => `
      <div class="store-card" data-handle="${esc(s.handle)}" role="link" tabindex="0" aria-label="Open ${esc(s.display_name)} store">
        <div class="store-banner" style="background:${s.banner_url ? `center/cover url('${esc(s.banner_optimized || s.banner_url)}')` : accentGrad(s.accent_color)}">
          <div class="store-avatar" style="background:${s.avatar_url ? `center/cover url('${esc(s.avatar_optimized || s.avatar_url)}')` : `linear-gradient(rgba(3,8,12,.38),rgba(3,8,12,.38)), ${s.accent_color || "var(--color-accent-fallback)"}`}">${s.avatar_url ? "" : initial(s.display_name)}</div>
        </div>
        <div class="store-body">
          <div class="store-name">${esc(s.display_name)} ${s.is_live ? '<span class="live-dot"></span>' : ""} ${s.is_founding ? `<span class="badge founding">★ #${s.founding_number}</span>` : ""}</div>
          <div class="store-tag">${esc(s.tagline || "")}</div>
          <div class="store-metrics">
            <span class="metric-chip">${s.listing_count} listing${s.listing_count === 1 ? "" : "s"}</span>
            <span class="metric-chip">${s.is_live ? "Live now" : "Buy now"}</span>
          </div>
          <div class="store-foot"><span>${s.listing_count} listing${s.listing_count === 1 ? "" : "s"}</span><span>Visit →</span></div>
        </div>
      </div>`).join("");
    bindCardLinkBehavior(grid.querySelectorAll("[data-handle]"), function () {
      location.href = `/store/${this.getAttribute("data-handle")}`;
    });
  } catch (err) {
    $("storeGrid").innerHTML = `<p class="muted">Could not load stores: ${esc(err.message || "Unknown error")}.</p>`;
  }
}

let t;
document.addEventListener("DOMContentLoaded", () => {
  api("/api/auth/me").then((d) => { IS_SIGNED_IN = !!d.user; }).catch(() => { IS_SIGNED_IN = false; });
  loadLive();
  loadStores("");
  setInterval(refreshCountdowns, 30000);
  $("storeSearch").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => loadStores(e.target.value.trim()), 300); });
});
