// RAGNAR storefront — talks to the FastAPI backend on the same origin.
"use strict";

const API = "";
let META = null;
const state = { page: 1, pageSize: 24, lastItems: [], compareIds: [] };
let activeListingsRequest = null;
const COMPARE_STORAGE_KEY = "ragnar:compare:listings";
const FREE_SHIP_TOKEN = "free shipping";

/* ---------------- helpers ---------------- */
const $ = (id) => document.getElementById(id);
const money = (n) =>
  n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const escapeHtml = (s) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, options) {
  const headers = { "Content-Type": "application/json", ...(options?.headers || {}) };
  const res = await fetch(API + path, {
    headers,
    ...options,
  });
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const detail = data && (data.detail || data.error);
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return data;
}

function filterParams(includePaging = true) {
  const p = new URLSearchParams();
  const q = $("f-q").value.trim();
  if (q) p.set("q", q);
  const map = {
    category: "f-category",
    set_name: "f-set",
    condition: "f-condition",
    grading_company: "f-grader",
    graded: "f-graded",
    min_grade: "f-mingrade",
    min_price: "f-minprice",
    max_price: "f-maxprice",
  };
  for (const [key, id] of Object.entries(map)) {
    const v = $(id).value;
    if (v !== "" && v != null) p.set(key, v);
  }
  if ($("f-founding").checked) p.set("founding_only", "true");
  if ($("f-sort").value !== "newest") p.set("sort", $("f-sort").value);
  if (includePaging) {
    p.set("page", String(state.page));
    p.set("page_size", String(state.pageSize));
  }
  return p;
}

function syncUrlFromFilters() {
  const p = filterParams(false);
  if (state.compareIds.length) p.set("cmp", state.compareIds.slice(0, 3).join(","));
  const qs = p.toString();
  const next = qs ? `/marketplace?${qs}` : "/marketplace";
  if (location.pathname + location.search !== next) {
    history.replaceState(null, "", next);
  }
}

function persistCompareState() {
  try {
    localStorage.setItem(COMPARE_STORAGE_KEY, JSON.stringify(state.compareIds.slice(0, 3)));
  } catch (_) {}
}

function normalizeCompareIds(raw) {
  const ids = [];
  for (const v of raw || []) {
    const n = Number(v);
    if (!Number.isFinite(n) || n <= 0) continue;
    if (!ids.includes(n)) ids.push(n);
    if (ids.length >= 3) break;
  }
  return ids;
}

function hydrateCompareState() {
  const p = new URLSearchParams(location.search);
  const fromUrl = (p.get("cmp") || "").split(",").map((v) => v.trim()).filter(Boolean);
  if (fromUrl.length) {
    state.compareIds = normalizeCompareIds(fromUrl);
    persistCompareState();
    return;
  }
  try {
    const stored = JSON.parse(localStorage.getItem(COMPARE_STORAGE_KEY) || "[]");
    state.compareIds = normalizeCompareIds(stored);
  } catch (_) {
    state.compareIds = [];
  }
}

async function apiForm(path, formData) {
  const res = await fetch(API + path, { method: "POST", body: formData });
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const detail = data && (data.detail || data.error);
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return data;
}

let toastTimer = null;
function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2800);
}

function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

const CREST = `<svg class="placeholder-crest" viewBox="0 0 120 80" xmlns="http://www.w3.org/2000/svg"><g fill="#7fa8c9"><path d="M60 30 L18 20 L30 27 L14 26 L28 33 L16 34 L30 40 L60 40 Z"/><path d="M60 30 L102 20 L90 27 L106 26 L92 33 L104 34 L90 40 L60 40 Z"/><path d="M60 24 L48 30 L44 44 L52 42 L48 54 L60 66 L72 54 L68 42 L76 44 L72 30 Z"/></g><g fill="#6fd6ff"><circle cx="55" cy="42" r="1.8"/><circle cx="65" cy="42" r="1.8"/></g></svg>`;

/* ---------------- fee math (mirrors backend fees.py) ---------------- */
function keepInfo(price, founding) {
  const f = META.fees;
  const rate = founding ? f.founding_rate : f.standard_rate;
  const keep = price - price * rate - (price * f.processing_rate + f.processing_flat);
  const ebayNet = price - (price * f.ebay_rate + f.ebay_flat);
  return { keep, savings: keep - ebayNet, rate };
}

/* ---------------- selects + hero ---------------- */
function fillSelect(el, values, keepFirst = true) {
  const first = keepFirst && el.options.length ? el.options[0].outerHTML : "";
  el.innerHTML = first + values.map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join("");
}

function renderHero() {
  const f = META.fees;
  $("heroStats").innerHTML = `
    <div class="stat hot"><div class="stat-num">0%</div><div class="stat-label">Founding ${f.founding_cap} fee</div></div>
    <div class="stat"><div class="stat-num">${(f.founding_rate * 100).toFixed(0)}%</div><div class="stat-label">Founding rate after</div></div>
    <div class="stat"><div class="stat-num">${(f.standard_rate * 100).toFixed(0)}%</div><div class="stat-label">Standard fee</div></div>`;
}

function renderIntegrations() {
  const el = $("integrations");
  if (!el || !META.integrations) return;
  const i = META.integrations;
  const dot = (on) => `<span class="int-dot ${on ? "on" : "off"}"></span>`;
  el.innerHTML = `integrations: ${dot(i.recognition !== "heuristic")}recognition (${escapeHtml(i.recognition)})`
    + ` · ${dot(i.live_pricing)}live pricing`
    + ` · ${dot(i.external_comps)}external comps`
    + ` · ${dot((META.payments || {}).live)}payments`;
}

async function refreshFoundingCounter() {
  try {
    const s = await api("/api/sellers/founding-status");
    $("foundingCounter").textContent = `Founding ${s.claimed}/${s.cap}`;
    $("foundingCounter").title = `${s.remaining} Founding Seller slots left`;
  } catch (_) {}
}

/* ---------------- listings ---------------- */
function currentQuery() {
  return filterParams(true).toString();
}

function loadingCards(count = 8) {
  return Array.from({ length: count }, () => `<article class="listing skeleton">
    <div class="listing-img"></div>
    <div class="listing-body">
      <div class="line w80"></div>
      <div class="line w60"></div>
      <div class="line w40"></div>
    </div>
  </article>`).join("");
}

function listingCard(l) {
  const badges = [`<span class="badge">${escapeHtml(l.category)}</span>`];
  if (l.is_graded && l.grading_company) badges.push(`<span class="badge grade">${escapeHtml(l.grading_company)} ${l.grade}</span>`);
  else if (l.condition) badges.push(`<span class="badge">${escapeHtml(l.condition)}</span>`);
  if (l.is_founding_seller) badges.push(`<span class="badge founding">★ Founding</span>`);
  if (l.is_featured) badges.push(`<span class="badge founding">FEATURED</span>`);

  const sub = [l.set_name, l.card_number].filter(Boolean).map(escapeHtml).join(" · ");
  const { keep, savings } = keepInfo(l.price, l.is_founding_seller);
  const src = l.thumb_url || l.image_url;
  const img = src
    ? `<img src="${escapeHtml(src)}" alt="${escapeHtml(l.title)}" loading="lazy" onerror="this.outerHTML='${CREST.replace(/'/g, "&#39;")}'" />`
    : CREST;

  return `<article class="listing">
    <a class="listing-link" href="/listing/${l.id}">
      <div class="listing-img">
        <div class="listing-badges">${badges.join("")}</div>
        <button class="watch-heart" type="button" data-watch="${l.id}" aria-label="Watch ${escapeHtml(l.title)}" aria-pressed="false">♡</button>
        ${img}
      </div>
      <div class="listing-body listing-body-main">
        <div class="listing-title">${escapeHtml(l.title)}</div>
        ${sub ? `<div class="listing-sub">${sub}</div>` : ""}
        <div class="listing-price-row">
          <span class="listing-price">${money(l.price)}</span>
          <span class="listing-keep">keep ${money(keep)}<br><span style="color:var(--muted)">+${money(savings)} vs eBay</span></span>
        </div>
        <div class="listing-meta">
          <span>${l.shipping ? "+ " + money(l.shipping) + " ship" : "Free shipping"}</span>
          ${l.view_count ? `<span>👁 ${l.view_count} watching</span>` : ""}
        </div>
      </div>
    </a>
    <div class="listing-body listing-body-foot">
      <div class="listing-foot">
        <div class="listing-seller"><span class="seller-dot"></span>${escapeHtml(l.seller_name)}</div>
        <div style="display:flex;gap:6px;">
          <button class="btn btn-ghost btn-sm compare-btn ${state.compareIds.includes(l.id) ? "on" : ""}" type="button" data-compare="${l.id}" aria-pressed="${state.compareIds.includes(l.id) ? "true" : "false"}">Compare</button>
          <button class="btn btn-sm buy-btn" type="button" data-buy="${l.id}">Buy</button>
        </div>
      </div>
    </div>
  </article>`;
}

async function hydrateWatchHearts(scope) {
  const hearts = [...(scope || document).querySelectorAll("[data-watch]")];
  if (!hearts.length) return;
  try {
    const ids = hearts.map((h) => h.getAttribute("data-watch")).join(",");
    const map = await api(`/api/watch/status?ids=${ids}`);
    hearts.forEach((h) => {
      const on = !!map[h.getAttribute("data-watch")];
      if (on) {
        h.textContent = "❤";
        h.classList.add("on");
      } else {
        h.textContent = "♡";
        h.classList.remove("on");
      }
      h.setAttribute("aria-pressed", on ? "true" : "false");
    });
  } catch (_) {}
}

async function toggleWatch(btn) {
  try {
    const r = await api("/api/watch", { method: "POST", body: JSON.stringify({ listing_id: Number(btn.getAttribute("data-watch")) }) });
    btn.textContent = r.watching ? "❤" : "♡";
    btn.classList.toggle("on", r.watching);
    btn.setAttribute("aria-pressed", r.watching ? "true" : "false");
    toast(r.watching ? "Added to your watchlist." : "Removed from watchlist.");
  } catch (e) {
    if (String(e.message).toLowerCase().includes("sign in")) toast("Sign in to watch items — /login");
    else toast(e.message);
  }
}

async function loadFeatured() {
  try {
    const d = await api("/api/listings?featured=true&page_size=8");
    if (!d.items.length) return;
    $("featuredWrap").hidden = false;
    $("featuredGrid").innerHTML = d.items.map(listingCard).join("");
    hydrateWatchHearts($("featuredGrid"));
  } catch (_) {}
}

async function buyListing(id) {
  try {
    const r = await api(`/api/payments/checkout/${id}`, { method: "POST" });
    if (r.url) { toast("Opening secure Stripe checkout…"); window.open(r.url, "_blank", "noopener"); }
  } catch (err) { toast(err.message); }
}

async function loadListings() {
  const grid = $("grid");
  if (activeListingsRequest) activeListingsRequest.abort();
  activeListingsRequest = new AbortController();
  grid.innerHTML = loadingCards();
  $("resultCount").textContent = "Loading listings…";
  try {
    const data = await api(`/api/listings?${currentQuery()}`, { signal: activeListingsRequest.signal });
    state.lastItems = data.items || [];
    if (!data.items.length) {
      grid.innerHTML = `<div class="empty">No cards match your search. Try widening the filters.</div>`;
      $("resultCount").textContent = "0 cards";
    } else {
      grid.innerHTML = data.items.map(listingCard).join("");
      $("resultCount").textContent = `${data.total} card${data.total === 1 ? "" : "s"} in the vault`;
      hydrateWatchHearts(grid);
    }
    renderCompareTray();
    setCompareButtonState();
    updatePresetState();
    $("pageInfo").textContent = data.pages ? `Page ${data.page} of ${data.pages}` : "";
    $("prevPage").disabled = data.page <= 1;
    $("nextPage").disabled = data.page >= data.pages;
    syncUrlFromFilters();
  } catch (err) {
    if (err.name === "AbortError") return;
    grid.innerHTML = `<div class="empty">Could not load listings: ${escapeHtml(err.message)}</div>`;
    $("resultCount").textContent = "Listings unavailable";
  }
}
function resetAndLoad() { state.page = 1; loadListings(); }

function copySearchLink() {
  const p = filterParams(false).toString();
  const url = `${location.origin}/marketplace${p ? `?${p}` : ""}`;
  navigator.clipboard.writeText(url)
    .then(() => toast("Search link copied."))
    .catch(() => toast(url));
}

function goToSurprise() {
  const items = state.lastItems || [];
  if (!items.length) {
    toast("No results to choose from yet.");
    return;
  }
  const pick = items[Math.floor(Math.random() * items.length)];
  location.href = `/listing/${pick.id}`;
}

function applyQuickPreset(name) {
  const active = isPresetActive(name);
  if (name === "budget") {
    $("f-minprice").value = "";
    $("f-maxprice").value = active ? "" : "100";
  }
  if (name === "graded9") {
    $("f-graded").value = active ? "" : "true";
    $("f-mingrade").value = active ? "" : "9";
  }
  if (name === "freeship") {
    const q = ($("f-q").value || "").trim();
    const hasToken = q.toLowerCase().includes(FREE_SHIP_TOKEN);
    if (active || hasToken) {
      const next = q.replace(/free shipping/ig, " ").replace(/\s{2,}/g, " ").trim();
      $("f-q").value = next;
      const hs = $("heroSearch"); if (hs) hs.value = next;
    } else {
      const next = q ? `${q} ${FREE_SHIP_TOKEN}` : FREE_SHIP_TOKEN;
      $("f-q").value = next;
      const hs = $("heroSearch"); if (hs) hs.value = next;
    }
  }
  if (name === "founding") {
    $("f-founding").checked = !active;
  }
  resetAndLoad();
}

function isPresetActive(name) {
  if (name === "budget") return $("f-maxprice").value === "100";
  if (name === "graded9") return $("f-graded").value === "true" && $("f-mingrade").value === "9";
  if (name === "freeship") return ((($("f-q").value || "") + "").toLowerCase().includes(FREE_SHIP_TOKEN));
  if (name === "founding") return $("f-founding").checked;
  return false;
}

function updatePresetState() {
  document.querySelectorAll("[data-preset]").forEach((btn) => btn.classList.remove("active"));
  ["budget", "graded9", "freeship", "founding"].forEach((preset) => {
    if (!isPresetActive(preset)) return;
    const b = document.querySelector(`[data-preset="${preset}"]`);
    if (b) b.classList.add("active");
  });
}

function setCompareButtonState() {
  document.querySelectorAll("[data-compare]").forEach((btn) => {
    const id = Number(btn.getAttribute("data-compare"));
    const on = state.compareIds.includes(id);
    btn.classList.toggle("on", on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  });
}

function renderCompareTray() {
  const tray = $("compareTray");
  if (!tray) return;
  const count = state.compareIds.length;
  tray.hidden = count === 0;
  const label = $("compareCount");
  if (label) label.textContent = `${count} selected`;
  const openBtn = $("openCompareBtn");
  if (openBtn) openBtn.disabled = count < 2;
}

function toggleCompare(id) {
  const n = Number(id);
  if (!Number.isFinite(n)) return;
  const idx = state.compareIds.indexOf(n);
  if (idx >= 0) state.compareIds.splice(idx, 1);
  else {
    if (state.compareIds.length >= 3) {
      toast("You can compare up to 3 cards at once.");
      return;
    }
    state.compareIds.push(n);
  }
  persistCompareState();
  renderCompareTray();
  setCompareButtonState();
  syncUrlFromFilters();
}

function compareRows(items) {
  const get = (k) => items.map((i) => (i[k] == null || i[k] === "" ? "—" : i[k]));
  const gradeScore = (i) => {
    if (i.is_graded && Number.isFinite(Number(i.grade))) return Number(i.grade);
    const c = String(i.condition || "").toLowerCase();
    if (c.includes("near mint")) return 8;
    if (c.includes("lightly")) return 6;
    if (c.includes("moderately")) return 4;
    if (c.includes("heavily")) return 2;
    if (c.includes("damaged")) return 1;
    return null;
  };
  return [
    { label: "Title", values: get("title") },
    {
      label: "Price",
      values: get("price").map((v) => (v === "—" ? v : money(v))),
      scores: items.map((i) => (Number.isFinite(Number(i.price)) ? Number(i.price) : null)),
      best: "min",
    },
    { label: "Category", values: get("category") },
    { label: "Set", values: get("set_name") },
    { label: "Card #", values: get("card_number") },
    {
      label: "Grade",
      values: items.map((i) => (i.is_graded ? `${i.grading_company || ""} ${i.grade || ""}`.trim() : (i.condition || "—"))),
      scores: items.map((i) => gradeScore(i)),
      best: "max",
    },
    { label: "Seller", values: get("seller_name") },
    {
      label: "Shipping",
      values: get("shipping").map((v) => (v === "—" ? v : (Number(v) > 0 ? money(v) : "Free"))),
      scores: items.map((i) => (Number.isFinite(Number(i.shipping)) ? Number(i.shipping) : null)),
      best: "min",
    },
  ];
}

function compareCellClass(row, idx) {
  if (!row || !row.scores || !row.best) return "";
  const numeric = row.scores.filter((v) => v != null && Number.isFinite(v));
  if (!numeric.length) return "";
  const target = row.best === "max" ? Math.max(...numeric) : Math.min(...numeric);
  const val = row.scores[idx];
  if (val == null || !Number.isFinite(val)) return "";
  return val === target ? "cmp-cell best" : "cmp-cell faded";
}

async function openCompare() {
  const ids = state.compareIds.slice(0, 3);
  if (ids.length < 2) {
    toast("Pick at least 2 cards to compare.");
    return;
  }
  const map = new Map((state.lastItems || []).map((i) => [i.id, i]));
  const items = [];
  for (const id of ids) {
    if (map.has(id)) items.push(map.get(id));
    else {
      try { items.push(await api(`/api/listings/${id}`)); } catch (_) {}
    }
  }
  const table = $("compareTable");
  if (!table) return;
  const rows = compareRows(items);
  const cols = items.map((it) => `<div class="cmp-cell head">${escapeHtml(it.title || `Listing ${it.id}`)}</div>`).join("");
  let html = `<div class="cmp-cell head">Field</div>${cols}`;
  for (const row of rows) {
    html += `<div class="cmp-cell label">${escapeHtml(row.label)}</div>`;
    for (let i = 0; i < row.values.length; i++) {
      const klass = compareCellClass(row, i) || "cmp-cell";
      html += `<div class="${klass}">${escapeHtml(row.values[i])}</div>`;
    }
    for (let i = row.values.length; i < 3; i++) html += `<div class="cmp-cell">—</div>`;
  }
  table.innerHTML = html;
  const modal = $("compareModal");
  if (modal) modal.hidden = false;
}

function closeCompare() {
  const modal = $("compareModal");
  if (modal) modal.hidden = true;
}

function clearCompare() {
  state.compareIds = [];
  persistCompareState();
  renderCompareTray();
  setCompareButtonState();
  syncUrlFromFilters();
}

function applyFilters(f) {
  if (f.q !== undefined) { $("f-q").value = f.q || ""; const hs = $("heroSearch"); if (hs) hs.value = f.q || ""; }
  if (f.category) $("f-category").value = f.category;
  if (f.grading_company) $("f-grader").value = f.grading_company;
  if (f.condition) $("f-condition").value = f.condition;
  if (f.graded !== undefined && f.graded !== null && f.graded !== "") $("f-graded").value = String(f.graded);
  if (f.min_grade !== undefined) $("f-mingrade").value = String(f.min_grade);
  if (f.min_price !== undefined) $("f-minprice").value = f.min_price;
  if (f.max_price !== undefined) $("f-maxprice").value = f.max_price;
  if (f.sort) $("f-sort").value = f.sort;
  if (f.founding_only !== undefined) $("f-founding").checked = String(f.founding_only) === "true";
  syncCatChips();
  resetAndLoad();
}

/* ---------------- category browse chips ---------------- */
const CAT_EMOJI = [
  [/pok/i, "⚡"], [/magic|mtg/i, "🔮"], [/yu-?gi/i, "🐉"], [/one piece/i, "🏴‍☠️"],
  [/lorcana/i, "🏰"], [/basketball/i, "🏀"], [/baseball/i, "⚾"], [/football/i, "🏈"],
  [/soccer|fifa/i, "⚽"], [/hockey/i, "🏒"], [/sport/i, "🏅"],
];
function catEmoji(c) { for (const [re, e] of CAT_EMOJI) if (re.test(c)) return e; return "🃏"; }
function catLabel(c) {
  if (c.includes("—")) return c.split("—").pop().trim();
  if (c.includes(":")) return c.split(":")[0].trim();
  return c;
}
function syncCatChips() {
  const cur = $("f-category").value;
  document.querySelectorAll("#catChips .cat-chip").forEach((b) => b.classList.toggle("active", b.dataset.cat === cur));
}
async function loadLiveRail() {
  const wrap = $("liveRailWrap"), rail = $("liveRail");
  if (!wrap || !rail) return;
  try {
    const streams = await api("/api/streams?status=live");
    if (!streams || !streams.length) { wrap.hidden = true; return; }
    rail.innerHTML = streams.map((s) => {
      const bg = s.thumbnail_url
        ? `center/cover url('${escapeHtml(s.thumbnail_url)}')`
        : `linear-gradient(135deg, ${escapeHtml(s.accent_color || "#2563eb")}, #0b1220)`;
      return `<a class="lr-card" href="/store/${encodeURIComponent(s.seller_handle)}">
        <div class="lr-thumb" style="background:${bg}">
          <span class="lr-badge">● LIVE</span>
          <span class="lr-views">👁 ${s.viewer_count || 0}</span>
        </div>
        <div class="lr-body">
          <div class="lr-title">${escapeHtml(s.title)}</div>
          <div class="lr-seller">${escapeHtml(s.seller_name)}</div>
        </div>
      </a>`;
    }).join("");
    wrap.hidden = false;
  } catch (_) { wrap.hidden = true; }
}

function buildCatChips() {
  const box = $("catChips"); if (!box) return;
  const mkChip = (val, label) => {
    const b = document.createElement("button");
    b.className = "cat-chip"; b.type = "button"; b.dataset.cat = val; b.textContent = label;
    b.addEventListener("click", () => { $("f-category").value = val; syncCatChips(); resetAndLoad(); });
    return b;
  };
  box.innerHTML = "";
  box.appendChild(mkChip("", "🗂️ All"));
  (META.categories || []).forEach((c) => box.appendChild(mkChip(c, `${catEmoji(c)} ${catLabel(c)}`)));
  syncCatChips();
}

function hydrateFromUrl() {
  const p = new URLSearchParams(location.search);
  if (![...p.keys()].length) return false;
  const f = {};
  ["q", "category", "grading_company", "condition", "sort"].forEach((k) => { if (p.get(k)) f[k] = p.get(k); });
  ["min_grade", "min_price", "max_price"].forEach((k) => { if (p.get(k)) f[k] = Number(p.get(k)); });
  if (p.get("graded")) f.graded = p.get("graded");
  if (p.get("founding_only")) f.founding_only = p.get("founding_only");
  const page = Number(p.get("page") || "1");
  if (Number.isFinite(page) && page > 0) state.page = page;
  applyFilters(f);
  return true;
}

async function aiSearch() {
  const q = $("f-q").value.trim();
  if (!q) { toast("Type what you want — e.g. 'PSA 10 Charizards under $5k'"); return; }
  try {
    const r = await api(`/api/ai/search?q=${encodeURIComponent(q)}`);
    applyFilters(r.filters || {});
    toast(`AI search applied (${r.source})`);
  } catch (e) { toast(e.message); }
}

/* ---------------- sales history ---------------- */
function sparkline(series) {
  if (!series || series.length < 2) return "";
  const prices = series.map((p) => p.price);
  const min = Math.min(...prices), max = Math.max(...prices);
  const span = max - min || 1;
  const W = 240, H = 44, n = series.length;
  const pts = series.map((p, i) => {
    const x = (i / (n - 1)) * (W - 4) + 2;
    const y = H - 2 - ((p.price - min) / span) * (H - 6);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
    <polyline points="${pts}" fill="none" stroke="#6fd6ff" stroke-width="2" />
  </svg>`;
}

function marketBlock(market) {
  if (!market || market.market == null) return "";
  const chg = market.change_7d;
  const chgHtml = chg == null ? "" : ` <span style="color:${chg >= 0 ? "#9be7c4" : "#ff9a9a"}">${chg >= 0 ? "▲" : "▼"} ${Math.abs(chg)}% 7d</span>`;
  return `<div class="market-row">
    <span class="market-label">Live market${market.source ? ` · ${escapeHtml(market.source)}` : ""}</span>
    <span class="market-val">${money(market.market)}${chgHtml}</span>
  </div>`;
}

function renderHistory(h, label, market) {
  const panel = $("historyPanel");
  const mkt = marketBlock(market);
  if (!h || !h.count) {
    panel.hidden = false;
    panel.innerHTML = `<div class="history-head"><span>Sold history</span></div>${mkt}
      <p class="muted">No comparable sold data yet${label ? ` for ${escapeHtml(label)}` : ""}. As RAGNAR sales complete (or an external comps provider is configured), comps appear here.</p>`;
    return;
  }
  panel.hidden = false;
  panel._mkt = mkt;
  const recent = h.recent.map((r) => {
    const tag = r.grading_company ? `${escapeHtml(r.grading_company)} ${r.grade}` : (r.condition ? escapeHtml(r.condition) : "raw");
    const date = new Date(r.sold_at).toLocaleDateString();
    return `<li><span>${date} · ${tag}</span><strong>${money(r.price)}</strong></li>`;
  }).join("");
  panel.innerHTML = `
    <div class="history-head"><span>Sold history</span><span class="history-count">${h.count} comps</span></div>
    ${mkt}
    <div class="history-stats">
      <div><span class="hs-num">${money(h.suggested_price)}</span><span class="hs-label">suggested</span></div>
      <div><span class="hs-num">${money(h.average)}</span><span class="hs-label">avg</span></div>
      <div><span class="hs-num">${money(h.low)}–${money(h.high)}</span><span class="hs-label">range</span></div>
      <div><span class="hs-num">${money(h.last_price)}</span><span class="hs-label">last sold</span></div>
    </div>
    ${sparkline(h.series)}
    <ul class="history-list">${recent}</ul>
    <button type="button" id="useSuggested" class="btn btn-ghost btn-sm">Use suggested price (${money(h.suggested_price)})</button>`;
  const btn = $("useSuggested");
  if (btn) btn.addEventListener("click", () => { $("form-price").value = h.suggested_price; updateFeePreview(); toast("Suggested price applied."); });
}

function historyQueryFromForm() {
  const p = new URLSearchParams();
  const cat = $("form-category").value; if (cat) p.set("category", cat);
  const setn = document.querySelector('input[name="set_name"]').value.trim(); if (setn) p.set("set_name", setn);
  const num = document.querySelector('input[name="card_number"]').value.trim(); if (num) p.set("card_number", num);
  const player = document.querySelector('input[name="player_or_character"]').value.trim(); if (player) p.set("player_or_character", player);
  const graded = $("form-graded").checked; p.set("graded", graded ? "true" : "false");
  if (graded) {
    const gc = $("form-grader").value; if (gc) p.set("grading_company", gc);
    const g = document.querySelector('input[name="grade"]').value; if (g) p.set("grade", g);
  }
  return p.toString();
}

async function fetchMarketForForm() {
  if (!META.integrations || !META.integrations.live_pricing) return null;
  const player = document.querySelector('input[name="player_or_character"]').value.trim()
    || document.querySelector('input[name="title"]').value.trim();
  const setn = document.querySelector('input[name="set_name"]').value.trim();
  const cat = $("form-category").value;
  const q = [player, setn].filter(Boolean).join(" ");
  if (!q) return null;
  try {
    const p = new URLSearchParams({ q }); if (cat) p.set("category", cat);
    return await api(`/api/pricing/search?${p.toString()}`);
  } catch (_) { return null; }
}

async function checkComps() {
  try {
    const label = document.querySelector('input[name="player_or_character"]').value.trim()
      || document.querySelector('input[name="title"]').value.trim();
    const [h, market] = await Promise.all([
      api(`/api/sales/history?${historyQueryFromForm()}`),
      fetchMarketForForm(),
    ]);
    renderHistory(h, label, market);
  } catch (err) { toast("Could not load sold history: " + err.message); }
}

async function suggestPrice() {
  const out = $("suggestOut");
  const q = (n) => { const el = document.querySelector(`[name="${n}"]`); return el ? el.value.trim() : ""; };
  if (!q("player_or_character") && !q("title")) { out.textContent = "Add a card name/player first, then I can suggest a price."; return; }
  out.textContent = "Pricing…";
  const graded = $("form-graded").checked;
  const payload = {
    title: q("title"), player_or_character: q("player_or_character"),
    set_name: q("set_name"), card_number: q("card_number"),
    category: $("form-category").value || null, is_graded: graded,
    grading_company: graded ? ($("form-grader").value || null) : null,
    grade: graded ? (q("grade") || null) : null,
  };
  try {
    const r = await api("/api/pricing/suggest", { method: "POST", body: JSON.stringify(payload) });
    if (r.suggested_price != null) {
      $("form-price").value = r.suggested_price;
      updateFeePreview();
      const range = (r.low != null && r.high != null) ? ` · range $${r.low}–$${r.high}` : "";
      out.innerHTML = `✨ Suggested <strong>$${r.suggested_price}</strong>${range} — ${r.basis.join(" + ")}. Tweak freely.`;
      toast("Suggested price applied.");
    } else {
      out.textContent = r.note || "Not enough data to suggest a price yet.";
    }
  } catch (e) { out.textContent = "Couldn't suggest a price: " + e.message; }
}

/* ---------------- scan-to-post ---------------- */
function applyScanFields(f) {
  const set = (name, val) => { const el = document.querySelector(`[name="${name}"]`); if (el && val != null && val !== "") el.value = val; };
  set("title", f.title);
  if (f.category) $("form-category").value = f.category;
  set("set_name", f.set_name);
  set("card_number", f.card_number);
  set("player_or_character", f.player_or_character);
  set("year", f.year);
  $("form-graded").checked = !!f.is_graded;
  syncGradedFields();
  if (f.is_graded) {
    if (f.grading_company) $("form-grader").value = f.grading_company;
    set("grade", f.grade);
  } else if (f.condition) {
    $("form-condition").value = f.condition;
  }
}

async function handleScanFile(file) {
  if (!file) return;
  const preview = $("scanPreview");
  preview.src = URL.createObjectURL(file);
  preview.hidden = false;
  const result = $("scanResult");
  result.hidden = false;
  result.className = "scan-result loading";
  result.textContent = "Scanning card…";
  try {
    const fd = new FormData();
    fd.append("file", file);
    const r = await apiForm("/api/scan", fd);
    applyScanFields(r.fields);
    if (r.image_url) $("form-image").value = r.image_url;
    const conf = Math.round(r.confidence * 100);
    const tone = conf >= 70 ? "ok" : "warn";
    result.className = `scan-result ${tone}`;
    result.innerHTML = `<strong>${conf}% match</strong> · ${escapeHtml(r.provider)}<br><span class="muted">${escapeHtml(r.notes)}</span>`;
    renderHistory(r.sales_history, r.fields.player_or_character || r.fields.title, r.market_price);
    updateFeePreview();
    toast("Card scanned — details pre-filled. Confirm and publish.");
  } catch (err) {
    result.className = "scan-result error";
    result.textContent = "Scan failed: " + err.message;
  }
}

/* ---------------- seller apply ---------------- */
async function applyFounding() {
  const handle = $("form-handle").value.trim();
  const name = $("form-seller").value.trim();
  if (!handle || !name) { toast("Enter a seller handle and display name first."); return; }
  try {
    const s = await api("/api/sellers/apply", {
      method: "POST",
      body: JSON.stringify({ handle, display_name: name, apply_for_founding: true }),
    });
    showSellerState(s);
    await refreshFoundingCounter();
    updateFeePreview();
    toast(s.is_founding ? `You're Founding Seller #${s.founding_number}! 0% fees during your intro window.` : "Seller created (Founding slots full — standard rate).");
  } catch (err) {
    if (String(err.message).includes("already taken")) {
      try { const s = await api(`/api/sellers/${encodeURIComponent(handle)}`); showSellerState(s); updateFeePreview(); toast("Welcome back — seller loaded."); return; } catch (_) {}
    }
    toast(err.message);
  }
}

async function connectPayouts() {
  const handle = $("form-handle").value.trim();
  const name = $("form-seller").value.trim();
  if (!handle) { toast("Enter your seller handle first (and Apply if you're new)."); return; }
  try {
    // Make sure the seller exists (no-op error if already there).
    try { await api("/api/sellers/apply", { method: "POST", body: JSON.stringify({ handle, display_name: name || handle, apply_for_founding: false }) }); } catch (_) {}
    const r = await api(`/api/payments/connect/${encodeURIComponent(handle)}`, { method: "POST" });
    if (r.onboarding_url) { toast("Opening Stripe onboarding…"); window.open(r.onboarding_url, "_blank", "noopener"); }
  } catch (err) { toast(err.message); }
}

function showSellerState(s) {
  const el = $("sellerState");
  el.hidden = false;
  if (s.is_founding) {
    el.className = "seller-state founding";
    el.innerHTML = `★ <strong>Founding Seller #${s.founding_number}</strong> · ${s.intro_active ? `0% intro fee — ${s.intro_days_left} days & ${money(s.intro_sales_remaining)} left` : `permanent ${(s.effective_rate * 100).toFixed(0)}% rate`}`;
  } else {
    el.className = "seller-state";
    el.innerHTML = `Standard seller · ${(s.effective_rate * 100).toFixed(0)}% fee`;
  }
  el.dataset.founding = s.is_founding ? "1" : "0";
}

/* ---------------- drawer + form ---------------- */
function openDrawer() { $("listDrawer").classList.add("open"); $("listDrawer").setAttribute("aria-hidden", "false"); updateFeePreview(); }
function closeDrawer() { $("listDrawer").classList.remove("open"); $("listDrawer").setAttribute("aria-hidden", "true"); }

function syncGradedFields() {
  const graded = $("form-graded").checked;
  $("gradedFields").hidden = !graded;
  $("rawFields").hidden = graded;
  $("form-condition").required = !graded;
  $("form-grader").required = graded;
}

function sellerIsFounding() { return $("sellerState").dataset.founding === "1"; }

function updateFeePreview() {
  const price = parseFloat($("form-price").value);
  const el = $("feePreview");
  if (!price || price <= 0) { el.innerHTML = "Enter a price to see what you keep on RAGNAR vs eBay."; return; }
  const founding = sellerIsFounding();
  const { keep, savings, rate } = keepInfo(price, founding);
  el.innerHTML = `On a ${money(price)} sale you keep <strong>${money(keep)}</strong> (${(rate * 100).toFixed(0)}% platform fee${founding ? ", Founding" : ""}). <span class="vs">≈ ${money(savings)} more than eBay.</span>`;
}

async function submitListing(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const graded = $("form-graded").checked;
  const payload = {
    title: fd.get("title"), category: fd.get("category"),
    set_name: fd.get("set_name") || null, card_number: fd.get("card_number") || null,
    player_or_character: fd.get("player_or_character") || null,
    year: fd.get("year") ? Number(fd.get("year")) : null,
    is_graded: graded,
    condition: graded ? null : fd.get("condition"),
    grading_company: graded ? fd.get("grading_company") : null,
    grade: graded && fd.get("grade") ? Number(fd.get("grade")) : null,
    price: Number(fd.get("price")), quantity: fd.get("quantity") ? Number(fd.get("quantity")) : 1,
    image_url: fd.get("image_url") || null, description: fd.get("description") || null,
    seller_name: fd.get("seller_name") || null,
    seller_handle: fd.get("seller_handle") || null,
  };
  const status = $("formStatus");
  status.className = "form-status"; status.textContent = "Publishing…";
  try {
    const created = await api("/api/listings", { method: "POST", body: JSON.stringify(payload) });
    status.className = "form-status ok"; status.textContent = "Published!";
    toast(`"${created.title}" is live in the vault.`);
    e.target.reset();
    $("scanPreview").hidden = true; $("scanResult").hidden = true; $("historyPanel").hidden = true;
    $("sellerState").hidden = true; $("sellerState").dataset.founding = "0";
    syncGradedFields(); updateFeePreview(); closeDrawer(); resetAndLoad();
  } catch (err) {
    status.className = "form-status error"; status.textContent = err.message;
  }
}

/* ---------------- backend status ---------------- */
async function checkBackend() {
  const el = $("backendStatus");
  try { await api("/health"); el.textContent = "online"; el.className = "status-badge online"; }
  catch (_) { el.textContent = "offline"; el.className = "status-badge offline"; }
}

/* ---------------- init ---------------- */
async function init() {
  try {
    await checkBackend();
    META = await api("/api/meta");
    hydrateCompareState();

    fillSelect($("f-category"), META.categories);
    fillSelect($("f-condition"), META.conditions);
    fillSelect($("f-grader"), META.grading_companies);
    fillSelect($("form-category"), META.categories, false);
    fillSelect($("form-condition"), META.conditions, false);
    fillSelect($("form-grader"), META.grading_companies, false);

    buildCatChips();
    loadLiveRail();
    renderHero();
    renderIntegrations();
    refreshFoundingCounter();

  // Marketplace hero search (mirrors the sidebar search).
  const heroSearch = $("heroSearch");
  if (heroSearch) {
    const heroGo = () => { $("f-q").value = heroSearch.value; resetAndLoad(); };
    heroSearch.addEventListener("input", debounce(heroGo, 350));
    heroSearch.addEventListener("keydown", (e) => { if (e.key === "Enter") heroGo(); });
    $("heroSearchBtn").addEventListener("click", heroGo);
    $("heroAiBtn").addEventListener("click", () => { $("f-q").value = heroSearch.value; aiSearch(); });
  }

  $("aiSearchBtn").addEventListener("click", aiSearch);
  $("f-q").addEventListener("input", debounce(resetAndLoad, 300));
  $("f-q").addEventListener("input", () => { const hs = $("heroSearch"); if (hs) hs.value = $("f-q").value; });
  $("f-category").addEventListener("change", syncCatChips);
  ["f-category", "f-condition", "f-grader", "f-graded", "f-mingrade", "f-sort"].forEach((id) => $(id).addEventListener("change", resetAndLoad));
  ["f-set", "f-minprice", "f-maxprice"].forEach((id) => $(id).addEventListener("input", debounce(resetAndLoad, 300)));
  $("f-founding").addEventListener("change", resetAndLoad);
  $("resetFilters").addEventListener("click", () => {
    ["f-q", "f-set", "f-minprice", "f-maxprice"].forEach((id) => ($(id).value = ""));
    ["f-category", "f-condition", "f-grader", "f-graded", "f-mingrade"].forEach((id) => ($(id).value = ""));
    const hs = $("heroSearch"); if (hs) hs.value = "";
    $("f-founding").checked = false; $("f-sort").value = "newest"; syncCatChips(); resetAndLoad();
  });

  $("prevPage").addEventListener("click", () => { if (state.page > 1) { state.page--; loadListings(); } });
  $("nextPage").addEventListener("click", () => { state.page++; loadListings(); });
  $("copySearchLinkBtn").addEventListener("click", copySearchLink);
  $("surpriseBtn").addEventListener("click", goToSurprise);
  document.querySelectorAll("[data-preset]").forEach((btn) => btn.addEventListener("click", () => applyQuickPreset(btn.getAttribute("data-preset"))));
  const openCompareBtn = $("openCompareBtn");
  if (openCompareBtn) openCompareBtn.addEventListener("click", openCompare);
  const clearCompareBtn = $("clearCompareBtn");
  if (clearCompareBtn) clearCompareBtn.addEventListener("click", clearCompare);
  const closeCompareBtn = $("closeCompareBtn");
  if (closeCompareBtn) closeCompareBtn.addEventListener("click", closeCompare);
  const compareScrim = $("compareScrim");
  if (compareScrim) compareScrim.addEventListener("click", closeCompare);

  const gridClicks = (e) => {
    const heart = e.target.closest("[data-watch]");
    if (heart) { e.preventDefault(); e.stopPropagation(); toggleWatch(heart); return; }
    const cmp = e.target.closest("[data-compare]");
    if (cmp) { e.preventDefault(); e.stopPropagation(); toggleCompare(cmp.getAttribute("data-compare")); return; }
    const buy = e.target.closest("[data-buy]");
    if (buy) buyListing(buy.getAttribute("data-buy"));
  };
  $("grid").addEventListener("click", gridClicks);
  const fg = $("featuredGrid");
  if (fg) fg.addEventListener("click", gridClicks);
  loadFeatured();

  $("openListBtn").addEventListener("click", openDrawer);
  $("closeListBtn").addEventListener("click", closeDrawer);
  $("drawerScrim").addEventListener("click", closeDrawer);
  $("connectPayoutsBtn").addEventListener("click", connectPayouts);

  $("scanDrop").addEventListener("click", () => $("scanInput").click());
  $("scanInput").addEventListener("change", (e) => handleScanFile(e.target.files[0]));
  $("scanDrop").addEventListener("dragover", (e) => { e.preventDefault(); $("scanDrop").classList.add("drag"); });
  $("scanDrop").addEventListener("dragleave", () => $("scanDrop").classList.remove("drag"));
  $("scanDrop").addEventListener("drop", (e) => { e.preventDefault(); $("scanDrop").classList.remove("drag"); handleScanFile(e.dataTransfer.files[0]); });

  $("form-graded").addEventListener("change", syncGradedFields);
  $("form-price").addEventListener("input", updateFeePreview);
  $("checkCompsBtn").addEventListener("click", checkComps);
  $("suggestPriceBtn").addEventListener("click", suggestPrice);
  $("applyFoundingBtn").addEventListener("click", applyFounding);
  $("listForm").addEventListener("submit", submitListing);

  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const tgt = e.target;
      if (tgt && (tgt.tagName === "INPUT" || tgt.tagName === "TEXTAREA" || tgt.tagName === "SELECT")) return;
      e.preventDefault();
      const hs = $("heroSearch");
      if (hs) hs.focus();
    }
    if (e.key === "Escape") { closeDrawer(); closeCompare(); }
  });

    syncGradedFields();
    renderCompareTray();
    updatePresetState();
    if (!hydrateFromUrl()) await loadListings();
  } catch (err) {
    $("backendStatus").textContent = "offline";
    $("backendStatus").className = "status-badge offline";
    $("resultCount").textContent = "Marketplace unavailable";
    $("grid").innerHTML = `<div class="empty">Could not load marketplace data: ${escapeHtml(err.message || "Unknown error")}.</div>`;
    toast("Could not initialize the marketplace.");
  }
}

document.addEventListener("DOMContentLoaded", init);
