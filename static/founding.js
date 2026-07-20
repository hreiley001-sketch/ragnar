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
  $("liveCount").textContent = String(items.length);

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

function renderBreaks(streams, rides) {
  const scheduled = (streams || []).filter((stream) => stream.status === "scheduled").map((stream) => ({
    href: `/store/${encodeURIComponent(stream.seller_handle)}`,
    when: scheduleLabel(stream.scheduled_at),
    title: stream.title,
    detail: `${stream.seller_name} · Scheduled live room`,
  }));
  const waitingRides = ((rides && rides.items) || []).filter((ride) => ride.status === "idle").map((ride) => ({
    href: `/ride/${ride.id}`,
    when: "Lobby forming",
    title: ride.title,
    detail: `${ride.seller_handle ? `@${ride.seller_handle}` : "RAGNAR House"} · ${ride.type || "Live ride"}`,
  }));
  const items = [...scheduled, ...waitingRides].slice(0, 5);
  if (!items.length) {
    $("breakList").innerHTML = `
      <div class="break-row">
        <div class="break-time">Lineup<br>loading</div>
        <div><h3>New break schedules are dropping soon.</h3><p>Follow your favorite breakers and be first into the room.</p></div>
        <a class="break-arrow" href="/stores" aria-label="Explore breakers">→</a>
      </div>`;
    return;
  }
  $("breakList").innerHTML = items.map((item) => `
    <a class="break-row" href="${esc(item.href)}">
      <div class="break-time">${esc(item.when)}</div>
      <div><h3>${esc(item.title)}</h3><p>${esc(item.detail)}</p></div>
      <span class="break-arrow">→</span>
    </a>`).join("");
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
  apply("momentTitle", "momentDescription", "momentCategory", "momentGrade", "momentValue", "momentCard");
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

  $("vaultCount").textContent = Number(recentData.total || 0).toLocaleString();
  renderLive(streams, rides);
  renderBreaks(streams, rides);
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

// The vault hero (logo + slabs) is a static composition on purpose — it does
// not track scroll or pointer position. All camera/depth motion below is
// handled by initSectionDepth() and initMomentDrama().

// A continuous scroll "camera" for everything under the hero: each section's
// content drifts in depth (translateZ) and tilts slightly (rotateX) based on
// how far it is from the center of the viewport, so the whole page keeps
// feeling like it's moving through a 3D space, not just fading in once.
function initSectionDepth() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  // :not(.reveal) avoids clobbering elements that already own their own
  // reveal transform (inline style would win over the .reveal.in class rule).
  const targets = Array.from(document.querySelectorAll(
    ".section .arena-shell:not(.reveal), .vault-activity-band .vault-activity-grid:not(.reveal)"
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
      // -1 (below viewport) .. 0 (centered) .. 1 (above viewport)
      const offset = Math.max(-1, Math.min(1, (elCenter - center) / (viewH * 0.9)));
      const depth = Math.abs(offset) * -60; // recede in Z the farther from center
      const tilt = offset * -3.2; // gentle camera tilt as it passes through
      el.style.transform = `translateZ(${depth.toFixed(1)}px) rotateX(${tilt.toFixed(2)}deg)`;
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
    // 0 when the stage is below the viewport, 1 once it's centered/passed center.
    const raw = 1 - (rect.top + rect.height * 0.5) / (viewH * 0.9);
    return Math.min(1, Math.max(0, raw));
  }

  function tick(time) {
    const progress = scrollProgress();
    const t = time / 1000;
    const idleRx = Math.sin(t * 0.55) * 3.5;
    const idleRy = Math.cos(t * 0.4) * 5;
    const idleLift = Math.sin(t * 0.7) * 8;
    const pulse = (Math.sin(t * 1.3) + 1) / 2; // 0..1 breathing glow

    const enterRy = -34 * (1 - progress);
    const scale = 0.86 + progress * 0.14;

    const rx = idleRx + pointerY * (hovering ? 10 : 0);
    const ry = idleRy + enterRy + pointerX * (hovering ? 14 : 0);

    card.style.setProperty("--mc-rx", `${rx.toFixed(2)}deg`);
    card.style.setProperty("--mc-ry", `${ry.toFixed(2)}deg`);
    card.style.setProperty("--mc-y", `${idleLift.toFixed(1)}px`);
    card.style.setProperty("--mc-scale", scale.toFixed(3));
    card.style.setProperty("--mc-glow", `${(12 + pulse * 18 + progress * 14).toFixed(1)}px`);
    card.style.setProperty("--mc-glow-a", (0.1 + pulse * 0.12 + progress * 0.1).toFixed(3));
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

function initArenaCanvas() {
  const canvas = $("arenaCanvas");
  if (!canvas || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const context = canvas.getContext("2d", { alpha: true });
  if (!context) return;
  let width = 0;
  let height = 0;
  let frame = 0;
  let active = true;
  const points = [];
  const shards = [];

  function resize() {
    const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.floor(width * ratio);
    canvas.height = Math.floor(height * ratio);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    points.length = 0;
    shards.length = 0;
    const count = Math.min(140, Math.max(60, Math.floor(width / 12)));
    for (let index = 0; index < count; index += 1) {
      points.push({
        x: Math.random() * width,
        y: Math.random() * height,
        z: Math.random() * 1 + 0.2,
        speed: Math.random() * 0.34 + 0.08,
        size: Math.random() * 1.6 + 0.3,
      });
    }
    for (let i = 0; i < 18; i += 1) {
      shards.push({
        x: Math.random() * width,
        y: Math.random() * height,
        len: 40 + Math.random() * 120,
        ang: -0.4 + Math.random() * 0.2,
        alpha: 0.03 + Math.random() * 0.05,
        drift: 0.08 + Math.random() * 0.12,
      });
    }
  }

  function draw() {
    if (!active) return;
    context.clearRect(0, 0, width, height);

    // Soft light rays
    shards.forEach((s) => {
      s.y -= s.drift;
      if (s.y < -s.len) { s.y = height + s.len; s.x = Math.random() * width; }
      context.save();
      context.translate(s.x, s.y);
      context.rotate(s.ang);
      const grad = context.createLinearGradient(0, 0, 0, s.len);
      grad.addColorStop(0, `rgba(184,240,255,0)`);
      grad.addColorStop(0.45, `rgba(143,232,255,${s.alpha})`);
      grad.addColorStop(1, `rgba(46,200,255,0)`);
      context.fillStyle = grad;
      context.fillRect(-1.2, 0, 2.4, s.len);
      context.restore();
    });

    const ice = getComputedStyle(document.documentElement).getPropertyValue("--color-accent-primary").trim() || "#3ed0ff";
    context.fillStyle = ice;
    points.forEach((point) => {
      point.y -= point.speed * point.z;
      point.x += Math.sin((point.y + point.z * 100) * 0.004) * 0.04;
      if (point.y < -10) {
        point.y = height + 10;
        point.x = Math.random() * width;
      }
      context.globalAlpha = 0.1 + point.z * 0.32;
      context.beginPath();
      context.arc(point.x, point.y, point.size * point.z, 0, Math.PI * 2);
      context.fill();
    });
    context.globalAlpha = 1;
    frame = requestAnimationFrame(draw);
  }

  document.addEventListener("visibilitychange", () => {
    active = !document.hidden;
    if (active) draw();
    else cancelAnimationFrame(frame);
  });
  window.addEventListener("resize", resize, { passive: true });
  resize();
  draw();
}

document.addEventListener("DOMContentLoaded", () => {
  initReveal();
  initSectionDepth();
  // The vault hero (logo + slabs) is intentionally static — no scroll/pointer
  // camera. All the scroll-driven 3D motion lives below it.
  initMomentDrama();
  initArenaCanvas();
  loadArena();
  loadFoundingStatus();
  reflectAccount();
  const form = $("applyForm");
  if (form) form.addEventListener("submit", submitApplication);
});
