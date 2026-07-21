// RAGNAR — arctic vault homepage with scroll-driven camera.
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value == null ? "" : value).replace(
  /[&<>"']/g,
  (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]),
);
const money = (value) => value == null
  ? "—"
  : "$" + Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 });

let toastTimer;
function toast(message) {
  const el = $("toast");
  if (!el) return;
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error((data && (data.detail || data.error)) || `Request failed (${response.status})`);
  }
  return data;
}

function safeMediaUrl(value) {
  if (!value) return "";
  try {
    const url = new URL(value, location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch (_) {
    return "";
  }
}

function initial(value) {
  return (value || "R").trim().slice(0, 1).toUpperCase();
}

function relativeTime(value) {
  if (!value) return "just now";
  const time = new Date(value).getTime();
  if (!Number.isFinite(time)) return "recent";
  const diff = Math.max(0, Date.now() - time);
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function scheduleLabel(value) {
  if (!value) return "Schedule pending";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Schedule pending";
  const diff = date.getTime() - Date.now();
  if (diff <= 0) return "Starting soon";
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return `In ${Math.max(1, Math.floor(diff / 60000))} min`;
  if (hours < 24) return `In ${hours} hr`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" }) +
    " · " + date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function attachBackgrounds(root = document) {
  root.querySelectorAll("[data-bg]").forEach((element) => {
    const url = safeMediaUrl(element.dataset.bg);
    if (url) {
      element.style.backgroundImage = `url("${url.replaceAll('"', "%22")}")`;
      element.classList.add("has-image");
    }
  });
}

function liveCategory(title, explicitCategory) {
  const text = `${explicitCategory || ""} ${title || ""}`.toLowerCase();
  if (text.includes("basketball") || text.includes("nba")) return "basketball";
  if (text.includes("football") || text.includes("nfl")) return "football";
  if (text.includes("baseball") || text.includes("mlb")) return "baseball";
  if (text.includes("soccer") || text.includes("football club")) return "soccer";
  if (text.includes("pokémon") || text.includes("pokemon")) return "pokemon";
  if (["magic", "mtg", "yu-gi", "yugioh", "one piece", "lorcana", "tcg"].some((term) => text.includes(term))) return "tcg";
  return "other";
}

function initCategoryFilters() {
  const buttons = document.querySelectorAll("[data-live-category]");
  const cards = document.querySelectorAll("#liveArena .live-card");
  const empty = $("categoryEmpty");
  buttons.forEach((button) => button.addEventListener("click", () => {
    const selected = button.dataset.liveCategory;
    let visible = 0;
    buttons.forEach((item) => item.classList.toggle("active", item === button));
    cards.forEach((card) => {
      const show = selected === "all" || card.dataset.category === selected;
      card.hidden = !show;
      if (show) visible += 1;
    });
    if (empty) empty.hidden = visible > 0;
  }));
}

function renderLive(streams, rides) {
  const liveStreams = (streams || []).filter((stream) => stream.status === "live").map((stream) => ({
    href: `/store/${encodeURIComponent(stream.seller_handle)}`,
    title: stream.title,
    seller: stream.seller_name,
    handle: stream.seller_handle,
    viewers: stream.viewer_count || 0,
    image: stream.thumbnail_url,
    code: "LIVE",
    category: liveCategory(stream.title),
  }));
  const liveRides = ((rides && rides.items) || [])
    .filter((ride) => !["idle", "archived"].includes(ride.status))
    .map((ride) => ({
      href: `/ride/${ride.id}`,
      title: ride.title,
      seller: ride.seller_handle ? `@${ride.seller_handle}` : "RAGNAR House",
      handle: ride.seller_handle || "ragnar",
      viewers: ride.viewer_count || 0,
      image: ride.listing && ride.listing.image_url,
      code: String(ride.current_phase || "ride").slice(0, 4).toUpperCase(),
      detail: ride.current_bid != null ? `${money(ride.current_bid)} high bid` : "Live auction",
      category: liveCategory(ride.title, ride.listing && ride.listing.category),
    }));
  const items = [...liveRides, ...liveStreams].slice(0, 6);

  if (!items.length) {
    $("liveArena").innerHTML = `
      <div class="arena-empty">
        <div>
          <span class="section-label">Between main events</span>
          <strong>The next room is forming.</strong>
          <span>Explore scheduled breaks or enter the marketplace while the vault resets.</span>
          <div style="margin-top:22px"><a class="arena-btn small" href="/stores">View the lineup <span class="arrow">→</span></a></div>
        </div>
      </div>`;
    return;
  }

  $("liveArena").innerHTML = items.map((item) => `
    <a class="live-card" data-category="${esc(item.category)}" href="${esc(item.href)}">
      <div class="live-card-media" data-bg="${esc(item.image || "")}"></div>
      <div class="live-card-code">${esc(item.code)}</div>
      <div class="live-card-top">
        <span class="live-badge"><i class="signal-dot"></i>Live</span>
        <span class="viewer-badge">${Number(item.viewers).toLocaleString()} watching</span>
      </div>
      <div class="live-card-body">
        <h3>${esc(item.title)}</h3>
        <p>${esc(item.detail || "Live break in progress")}</p>
        <div class="live-card-foot">
          <span class="breaker-id"><span class="breaker-avatar">${esc(initial(item.seller))}</span>${esc(item.seller)}</span>
          <span class="enter-label">Enter room ↗</span>
        </div>
      </div>
    </a>`).join("");
  attachBackgrounds($("liveArena"));
  initCategoryFilters();
}

function renderBreaks() {
  // "Next on the floor" removed from homepage — keep stub for callers.
}

function renderBreakers(stores) {
  const items = (stores || []).slice(0, 4);
  const strip = $("breakerStrip");
  if (strip) {
    const top = (stores || []).slice(0, 5);
    if (!top.length) {
      strip.innerHTML = `<a class="breaker-chip" href="#apply"><span class="breaker-chip-av">R</span><div><strong>Claim the floor</strong><span>Applications open</span></div></a>`;
    } else {
      strip.innerHTML = top.map((store) => `
        <a class="breaker-chip" href="/store/${encodeURIComponent(store.handle)}">
          <span class="breaker-chip-av">${store.avatar_optimized || store.avatar_url
            ? `<img src="${esc(store.avatar_optimized || store.avatar_url)}" alt="" loading="lazy" />`
            : esc(initial(store.display_name))}</span>
          <div>
            <strong>${esc(store.display_name)}</strong>
            <span>${store.is_live ? "Live now" : (store.is_founding ? `Founding #${store.founding_number || "—"}` : `@${esc(store.handle)}`)}</span>
          </div>
        </a>`).join("");
    }
  }

  if (!items.length) {
    $("breakerGrid").innerHTML = `
      <a class="breaker-card" data-rank="01" href="#apply">
        <div class="breaker-avatar-lg">R</div>
        <div class="breaker-card-body"><span class="section-label">Founding roster</span><h3>Your room could lead the vault.</h3><p>Applications for elite sellers are open.</p></div>
      </a>`;
    return;
  }
  $("breakerGrid").innerHTML = items.map((store, index) => `
    <a class="breaker-card" data-rank="${String(index + 1).padStart(2, "0")}" href="/store/${encodeURIComponent(store.handle)}">
      ${store.is_live ? '<span class="breaker-live"><i class="signal-dot"></i>Live</span>' : ""}
      <div class="breaker-avatar-lg">${store.avatar_optimized || store.avatar_url
        ? `<img src="${esc(store.avatar_optimized || store.avatar_url)}" alt="" loading="lazy" />`
        : esc(initial(store.display_name))}</div>
      <div class="breaker-card-body">
        <span class="section-label">${store.is_founding ? `Founding // ${String(store.founding_number || 0).padStart(3, "0")}` : `@${esc(store.handle)}`}</span>
        <h3>${esc(store.display_name)}</h3>
        <p>${esc(store.tagline || "Collect. Break. Conquer.")}</p>
        <div class="breaker-stats"><div><b>${Number(store.listing_count || 0).toLocaleString()}</b><span>Vault items</span></div><div><b>${store.is_live ? "On" : "Ready"}</b><span>Status</span></div></div>
      </div>
    </a>`).join("");
}

function renderMoment(listings) {
  const item = (listings || [])[0];
  if (!item) return;
  const apply = (titleId, descId, catId, gradeId, valueId, cardId) => {
    const t = $(titleId); if (t) t.textContent = item.title;
    const d = $(descId);
    if (d) {
      d.textContent = "A chase-worthy card currently inside the RAGNAR vault. Verified live pulls will preserve the room, reaction, and ownership story here.";
    }
    const c = $(catId); if (c) c.textContent = item.category || "Collectible";
    const g = $(gradeId);
    if (g) {
      g.textContent = item.grading_company
        ? `${item.grading_company} ${item.grade || ""}`.trim()
        : (item.condition || "Raw");
    }
    const v = $(valueId); if (v) v.textContent = money(item.price);
    const image = safeMediaUrl(item.image_optimized || item.image_url);
    const card = $(cardId);
    if (card && image) {
      card.style.background = `center / contain no-repeat url("${image.replaceAll('"', "%22")}"), var(--moment-fallback)`;
      card.classList.add("with-image");
    }
  };
  // Stage-2 copy stays editorial; only the pulls archive is data-bound.
  apply("momentTitleLarge", "momentDescriptionLarge", "momentCategoryLarge", "momentGradeLarge", "momentValueLarge", "momentCardLarge");
}

function renderPulse(streams, rides, listings, stores) {
  const events = [];
  (streams || []).filter((stream) => stream.status === "live").forEach((stream) => events.push({
    code: "LV", time: relativeTime(stream.started_at), title: `${stream.seller_name} went live`,
    detail: stream.title, value: `${stream.viewer_count || 0} watching`,
  }));
  ((rides && rides.items) || []).filter((ride) => !["idle", "archived"].includes(ride.status)).forEach((ride) => events.push({
    code: "RD", time: "live", title: `${ride.title} is in ${ride.current_phase || "session"}`,
    detail: ride.current_bidder ? `${ride.current_bidder} controls the room` : "The room is open",
    value: ride.current_bid != null ? money(ride.current_bid) : "Enter",
  }));
  (listings || []).slice(0, 4).forEach((listing) => events.push({
    code: "VL", time: relativeTime(listing.created_at), title: "New card entered the vault",
    detail: listing.title, value: money(listing.price),
  }));
  (stores || []).filter((store) => store.is_live).slice(0, 2).forEach((store) => events.push({
    code: "BR", time: "now", title: `${store.display_name} controls the floor`,
    detail: store.tagline || `@${store.handle}`, value: "Live",
  }));
  const visible = events.slice(0, 7);
  if (!visible.length) {
    visible.push({
      code: "RG", time: "now", title: "RAGNAR systems online",
      detail: "Waiting for the next signal from the vault", value: "Armed",
    });
  }
  const list = $("pulseList");
  if (!list) return;
  list.innerHTML = visible.map((event) => `
    <div class="pulse-item">
      <div class="pulse-time">${esc(event.time)}</div>
      <div class="pulse-event"><span class="pulse-icon">${esc(event.code)}</span><div><strong>${esc(event.title)}</strong><span>${esc(event.detail)}</span></div></div>
      <div class="pulse-value">${esc(event.value)}</div>
    </div>`).join("");
}

async function loadArena() {
  const [streamsResult, ridesResult, storesResult, featuredResult, recentResult] = await Promise.allSettled([
    api("/api/streams"),
    api("/api/rides"),
    api("/api/stores"),
    api("/api/listings?featured=true&page_size=8"),
    api("/api/listings?page_size=8&sort=newest"),
  ]);
  const streams = streamsResult.status === "fulfilled" ? streamsResult.value : [];
  const rides = ridesResult.status === "fulfilled" ? ridesResult.value : { items: [] };
  const stores = storesResult.status === "fulfilled" ? storesResult.value : [];
  const featured = featuredResult.status === "fulfilled" ? featuredResult.value.items : [];
  const recentData = recentResult.status === "fulfilled" ? recentResult.value : { items: [], total: 0 };
  const recent = recentData.items || [];

  renderLive(streams, rides);
  renderBreakers(stores);
  renderMoment(featured.length ? featured : recent);
  renderPulse(streams, rides, recent, stores);
}

async function loadFoundingStatus() {
  try {
    const status = await api("/api/founding/status");
    $("claimed").textContent = Number(status.claimed || 0).toLocaleString();
    $("cap").textContent = Number(status.cap || 250).toLocaleString();
    if (status.remaining <= 0) {
      $("counter").innerHTML = "<span>Founding class full · waitlist access only</span>";
    }
  } catch (_) {
    $("counter").innerHTML = "<span>Founding roster status temporarily encrypted</span>";
  }
}

async function reflectAccount() {
  try {
    const me = await api("/api/auth/me");
    if (!me.user) return;
    const link = $("headerAcctLink") || $("acctLink");
    if (!link) return;
    const lbl = link.querySelector(".lbl");
    const text = me.user.is_staff ? "Command hub" : "My account";
    if (lbl) lbl.textContent = text; else link.textContent = text;
    link.href = me.user.is_staff ? "/admin" : "/account";
  } catch (_) {
    // Anonymous homepage remains fully usable.
  }
}

async function submitApplication(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const formData = new FormData(form);
  const payload = {
    name: formData.get("name"),
    email: formData.get("email"),
    handle_wanted: formData.get("handle_wanted") || null,
    monthly_volume: formData.get("monthly_volume") || null,
    categories: formData.get("categories") || null,
    current_platforms: formData.get("current_platforms") || null,
    message: formData.get("message") || null,
  };
  const status = $("formStatus");
  const button = form.querySelector("button[type='submit']");
  status.className = "arena-status";
  status.textContent = "Transmitting application…";
  button.disabled = true;
  try {
    await api("/api/founding/apply", { method: "POST", body: JSON.stringify(payload) });
    form.closest(".apply-panel").hidden = true;
    $("successBox").hidden = false;
    $("successBox").scrollIntoView({ behavior: "smooth", block: "center" });
    toast("Application received.");
  } catch (error) {
    status.className = "arena-status error";
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

function initReveal() {
  const elements = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window) || matchMedia("(prefers-reduced-motion: reduce)").matches) {
    elements.forEach((element) => element.classList.add("in"));
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("in");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.09, rootMargin: "0px 0px -5% 0px" });
  elements.forEach((element) => observer.observe(element));
}

// Continuous vault environment: one scroll-progress drives depth, light,
// architecture, and stage. GPU-friendly CSS custom properties only — no
// particle spam. Content exists inside the world.
function initVaultEnvironment() {
  const root = document.documentElement;
  const body = document.body;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let ticking = false;

  function apply() {
    ticking = false;
    const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    const progress = Math.min(1, Math.max(0, window.scrollY / max));
    root.style.setProperty("--vault-p", progress.toFixed(4));

    // Stage thresholds map to the cinematic journey.
    let stage = 1;
    if (progress > 0.18) stage = 2;
    if (progress > 0.42) stage = 3;
    if (progress > 0.68) stage = 4;
    if (body.dataset.vaultStage !== String(stage)) {
      body.dataset.vaultStage = String(stage);
    }

    if (reduce) return;

    // Gentle parallax for env layers (transforms only).
    const y = window.scrollY;
    root.style.setProperty("--vault-far-y", `${(y * 0.04).toFixed(1)}px`);
    root.style.setProperty("--vault-mid-y", `${(y * 0.08).toFixed(1)}px`);
    root.style.setProperty("--vault-arch-y", `${(y * 0.12).toFixed(1)}px`);
    root.style.setProperty("--vault-glass-y", `${(y * 0.16).toFixed(1)}px`);
  }

  function requestApply() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(apply);
  }

  window.addEventListener("scroll", requestApply, { passive: true });
  window.addEventListener("resize", requestApply, { passive: true });
  apply();
}

// Pointer-reactive camera: the whole environment leans gently toward the
// cursor (lerped, transform-only) so the world feels physical, not painted.
function initVaultCamera() {
  const camera = $("vaultCamera");
  if (!camera) return;
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  if (matchMedia("(pointer: coarse)").matches) return; // touch devices: scroll parallax only

  let targetX = 0;
  let targetY = 0;
  let currentX = 0;
  let currentY = 0;
  let raf = null;

  function tick() {
    currentX += (targetX - currentX) * 0.045;
    currentY += (targetY - currentY) * 0.045;
    camera.style.setProperty("--cam-x", `${currentX.toFixed(2)}px`);
    camera.style.setProperty("--cam-y", `${currentY.toFixed(2)}px`);
    if (Math.abs(targetX - currentX) < 0.05 && Math.abs(targetY - currentY) < 0.05) {
      raf = null;
      return;
    }
    raf = requestAnimationFrame(tick);
  }

  window.addEventListener("pointermove", (event) => {
    const nx = event.clientX / window.innerWidth - 0.5;
    const ny = event.clientY / window.innerHeight - 0.5;
    targetX = nx * -48;
    targetY = ny * -30;
    if (!raf) raf = requestAnimationFrame(tick);
  }, { passive: true });
}

function initSectionDepth() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const targets = Array.from(document.querySelectorAll(
    ".vault-stage .arena-shell:not(.reveal)"
  ));
  if (!targets.length) return;

  let ticking = false;

  function apply() {
    ticking = false;
    const viewH = window.innerHeight || 1;
    const center = viewH / 2;
    targets.forEach((el) => {
      const rect = el.getBoundingClientRect();
      const elCenter = rect.top + rect.height / 2;
      const offset = Math.max(-1, Math.min(1, (elCenter - center) / (viewH * 0.9)));
      const depth = Math.abs(offset) * -36;
      const tilt = offset * -1.6;
      el.style.transform = `translate3d(0,0,${depth.toFixed(1)}px) rotateX(${tilt.toFixed(2)}deg)`;
    });
  }

  function requestApply() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(apply);
  }

  window.addEventListener("scroll", requestApply, { passive: true });
  window.addEventListener("resize", requestApply, { passive: true });
  requestApply();
}

function initVaultKey() {
  const key = $("vaultKey");
  const stage = $("vaultKeyStage");
  if (!key || !stage || matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  let raf = null;

  function progress() {
    const rect = stage.getBoundingClientRect();
    const viewH = window.innerHeight || 1;
    const raw = 1 - (rect.top + rect.height * 0.35) / (viewH * 0.95);
    return Math.min(1, Math.max(0, raw));
  }

  function tick(time) {
    const p = progress();
    const t = time / 1000;
    const reveal = Math.pow(p, 0.85);
    const floatY = Math.sin(t * 0.7) * 6;
    const rotY = -28 + reveal * 28 + Math.sin(t * 0.35) * 4;
    const rotX = 8 - reveal * 6 + Math.cos(t * 0.4) * 2;
    const scale = 0.72 + reveal * 0.28;
    const glow = 0.15 + reveal * 0.55 + (Math.sin(t * 1.2) + 1) * 0.08;

    key.style.setProperty("--vk-y", `${floatY.toFixed(1)}px`);
    key.style.setProperty("--vk-ry", `${rotY.toFixed(2)}deg`);
    key.style.setProperty("--vk-rx", `${rotX.toFixed(2)}deg`);
    key.style.setProperty("--vk-scale", scale.toFixed(3));
    key.style.setProperty("--vk-opacity", Math.min(1, 0.15 + reveal * 0.95).toFixed(3));
    key.style.setProperty("--vk-glow", glow.toFixed(3));
    stage.classList.toggle("is-revealed", p > 0.45);

    raf = requestAnimationFrame(tick);
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (raf) cancelAnimationFrame(raf);
      raf = null;
    } else if (!raf) {
      raf = requestAnimationFrame(tick);
    }
  });

  raf = requestAnimationFrame(tick);
}

// The "hall of thunder" chase-card: idle floating motion running constantly,
// a scroll-driven 3D reveal as it enters the viewport, and a mouse-reactive
// tilt + light-sheen sweep on hover. Never fully static.
function initMomentDrama() {
  const card = $("momentCardLarge");
  const stage = card && card.closest(".moment-visual");
  if (!card || !stage || matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  if (!card.querySelector(".moment-card-sheen")) {
    const sheen = document.createElement("div");
    sheen.className = "moment-card-sheen";
    card.appendChild(sheen);
  }

  let pointerX = 0;
  let pointerY = 0;
  let hovering = false;
  let raf = null;

  function scrollProgress() {
    const rect = stage.getBoundingClientRect();
    const viewH = window.innerHeight || 1;
    const raw = 1 - (rect.top + rect.height * 0.5) / (viewH * 0.9);
    return Math.min(1, Math.max(0, raw));
  }

  function tick(time) {
    const progress = scrollProgress();
    const t = time / 1000;
    const idleRx = Math.sin(t * 0.55) * 2.5;
    const idleRy = Math.cos(t * 0.4) * 3.5;
    const idleLift = Math.sin(t * 0.7) * 5;
    const pulse = (Math.sin(t * 1.3) + 1) / 2;

    const enterRy = -24 * (1 - progress);
    const scale = 0.9 + progress * 0.1;

    const rx = idleRx + pointerY * (hovering ? 8 : 0);
    const ry = idleRy + enterRy + pointerX * (hovering ? 10 : 0);

    card.style.setProperty("--mc-rx", `${rx.toFixed(2)}deg`);
    card.style.setProperty("--mc-ry", `${ry.toFixed(2)}deg`);
    card.style.setProperty("--mc-y", `${idleLift.toFixed(1)}px`);
    card.style.setProperty("--mc-scale", scale.toFixed(3));
    card.style.setProperty("--mc-glow", `${(10 + pulse * 12 + progress * 10).toFixed(1)}px`);
    card.style.setProperty("--mc-glow-a", (0.08 + pulse * 0.08 + progress * 0.08).toFixed(3));
    card.style.setProperty("--mc-sheen", `${(-60 + ((t * 14) % 220)).toFixed(1)}%`);

    raf = requestAnimationFrame(tick);
  }

  stage.addEventListener("pointermove", (event) => {
    const bounds = stage.getBoundingClientRect();
    pointerX = (event.clientX - bounds.left) / bounds.width - 0.5;
    pointerY = (event.clientY - bounds.top) / bounds.height - 0.5;
    hovering = true;
  });
  stage.addEventListener("pointerleave", () => {
    hovering = false;
    pointerX = 0;
    pointerY = 0;
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (raf) cancelAnimationFrame(raf);
      raf = null;
    } else if (!raf) {
      raf = requestAnimationFrame(tick);
    }
  });

  raf = requestAnimationFrame(tick);
}

document.addEventListener("DOMContentLoaded", () => {
  initReveal();
  initVaultEnvironment();
  initVaultCamera();
  initSectionDepth();
  initVaultKey();
  initMomentDrama();
  loadArena();
  loadFoundingStatus();
  reflectAccount();
  const form = $("applyForm");
  if (form) form.addEventListener("submit", submitApplication);
});
