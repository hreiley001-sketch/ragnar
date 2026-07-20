// RAGNAR — cinematic live-commerce homepage.
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
          <strong>The next room is being forged.</strong>
          <span>Explore scheduled breaks or enter the marketplace while the arena resets.</span>
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
  $("breakerCount").textContent = String((stores || []).length || "—");
  if (!items.length) {
    $("breakerGrid").innerHTML = `
      <a class="breaker-card" data-rank="01" href="#apply">
        <div class="breaker-avatar-lg">R</div>
        <div class="breaker-card-body"><span class="section-label">Founding roster</span><h3>Your room could lead the arena.</h3><p>Applications for the first breaker class are open.</p></div>
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
        <div class="breaker-stats"><div><b>${Number(store.listing_count || 0).toLocaleString()}</b><span>Vault items</span></div><div><b>${store.is_live ? "On" : "Ready"}</b><span>Arena status</span></div></div>
      </div>
    </a>`).join("");
}

function renderMoment(listings) {
  const item = (listings || [])[0];
  if (!item) return;
  $("momentTitle").textContent = item.title;
  $("momentDescription").textContent = "A chase-worthy card currently inside the RAGNAR vault. Soon, verified live pulls will preserve the room, reaction, and ownership story here.";
  $("momentCategory").textContent = item.category || "Collectible";
  $("momentGrade").textContent = item.grading_company
    ? `${item.grading_company} ${item.grade || ""}`.trim()
    : (item.condition || "Raw");
  $("momentValue").textContent = money(item.price);
  const image = safeMediaUrl(item.image_optimized || item.image_url);
  if (image) {
    const card = $("momentCard");
    card.style.background = `center / contain no-repeat url("${image.replaceAll('"', "%22")}"), linear-gradient(145deg, #2a241a, #0b0b0a 70%)`;
    card.classList.add("with-image");
  }
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
      detail: "Waiting for the next signal from the arena", value: "Armed",
    });
  }
  $("pulseList").innerHTML = visible.map((event) => `
    <div class="pulse-item">
      <div class="pulse-time">${esc(event.time)}</div>
      <div class="pulse-event"><span class="pulse-icon">${esc(event.code)}</span><div><strong>${esc(event.title)}</strong><span>${esc(event.detail)}</span></div></div>
      <div class="pulse-value">${esc(event.value)}</div>
    </div>`).join("");
}

async function loadArena() {
  const [streamsResult, ridesResult, recentResult] = await Promise.allSettled([
    api("/api/streams"),
    api("/api/rides"),
    api("/api/listings?page_size=8&sort=newest"),
  ]);
  const streams = streamsResult.status === "fulfilled" ? streamsResult.value : [];
  const rides = ridesResult.status === "fulfilled" ? ridesResult.value : { items: [] };
  const recentData = recentResult.status === "fulfilled" ? recentResult.value : { items: [], total: 0 };

  $("vaultCount").textContent = Number(recentData.total || 0).toLocaleString();
  renderLive(streams, rides);
  renderBreaks(streams, rides);
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
    const link = $("acctLink");
    link.textContent = me.user.is_staff ? "Command hub" : "My account";
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

function initCardTilt() {
  const stage = $("arenaStage");
  const stack = $("holoStack");
  if (!stage || !stack || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  stage.addEventListener("pointermove", (event) => {
    const bounds = stage.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width - 0.5;
    const y = (event.clientY - bounds.top) / bounds.height - 0.5;
    stack.style.setProperty("--ry", `${x * 24 - 9}deg`);
    stack.style.setProperty("--rx", `${y * -16 - 4}deg`);
  });
  stage.addEventListener("pointerleave", () => {
    stack.style.setProperty("--ry", "-12deg");
    stack.style.setProperty("--rx", "-5deg");
  });
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
    const count = Math.min(74, Math.max(34, Math.floor(width / 22)));
    for (let index = 0; index < count; index += 1) {
      points.push({
        x: Math.random() * width,
        y: Math.random() * height,
        z: Math.random() * 1 + 0.2,
        speed: Math.random() * 0.18 + 0.04,
        size: Math.random() * 1.2 + 0.25,
      });
    }
  }

  function draw() {
    if (!active) return;
    context.clearRect(0, 0, width, height);
    points.forEach((point) => {
      point.y -= point.speed * point.z;
      point.x += Math.sin((point.y + point.z * 100) * 0.005) * 0.035;
      if (point.y < -10) {
        point.y = height + 10;
        point.x = Math.random() * width;
      }
      const alpha = 0.12 + point.z * 0.28;
      context.fillStyle = `rgba(184, 232, 247, ${alpha})`;
      context.beginPath();
      context.arc(point.x, point.y, point.size * point.z, 0, Math.PI * 2);
      context.fill();
    });
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
  initCardTilt();
  initArenaCanvas();
  loadArena();
  loadFoundingStatus();
  reflectAccount();
  $("applyForm").addEventListener("submit", submitApplication);
});
