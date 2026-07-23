// RAGNAR — item page (eBay-style listing detail: buy, watch, offers, seller, comps).
"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const ID = decodeURIComponent(location.pathname.split("/listing/")[1] || "").replace(/\/$/, "");

let toastTimer;
function toast(m) { const e = $("toast"); e.textContent = m; e.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => e.classList.remove("show"), 2600); }

async function api(p, o = {}) {
  const r = await fetch(p, { ...o, headers: { "Content-Type": "application/json", ...(o.headers || {}) } });
  let d = null; try { d = await r.json(); } catch (_) {}
  if (!r.ok) { const e = new Error((d && (d.detail || d.error)) || `Request failed (${r.status})`); e.status = r.status; throw e; }
  return d;
}

const CREST = `<svg class="placeholder-crest" viewBox="0 0 120 80" xmlns="http://www.w3.org/2000/svg" fill="none"><rect x="34" y="16" width="52" height="48" rx="6" stroke="var(--crest-primary)" stroke-width="2.5"/><circle cx="49" cy="31" r="5" fill="var(--crest-accent)"/><path d="M39 58 L55 40 L65 51 L73 43 L81 58 Z" fill="var(--crest-primary)"/></svg>`;

let LISTING = null;
let myOffer = null;
let watching = false;

function showAuthNote(msg) {
  const n = $("authNote");
  if (n) { n.className = "form-status error auth-note"; n.innerHTML = `${esc(msg)} <a href="/login">Sign in →</a>`; }
}

/* ---------- Photo (left column) ---------- */
function renderPhoto(l) {
  const badges = [`<span class="badge">${esc(l.category)}</span>`];
  if (l.is_graded && l.grading_company) badges.push(`<span class="badge grade">${esc(l.grading_company)} ${esc(l.grade)}</span>`);
  else if (l.condition) badges.push(`<span class="badge">${esc(l.condition)}</span>`);
  if (l.is_founding_seller) badges.push(`<span class="badge founding">★ Founding</span>`);
  if (l.is_featured) badges.push(`<span class="badge featured">FEATURED</span>`);
  if (l.status === "sold") badges.push(`<span class="badge soldout">SOLD</span>`);
  const box = $("photoBox");
  const photo = l.image_optimized || l.image_url;
  box.innerHTML = `<div class="photo-badges">${badges.join("")}</div>${photo ? `<img src="${esc(photo)}" alt="${esc(l.title)}" />` : CREST}`;
  const im = box.querySelector("img");
  if (im) im.addEventListener("error", () => { im.remove(); box.insertAdjacentHTML("beforeend", CREST); }, { once: true });
}

/* ---------- Main (right column) ---------- */
function offerBoxHtml() {
  return `<div class="card offer-box">
    <h3>Make an offer</h3>
    <div class="offer-row">
      <input id="offerAmount" type="number" min="0.01" step="0.01" placeholder="Amount ($)" />
      <input id="offerMsg" maxlength="500" placeholder="Message to the seller (optional)" />
      <button id="offerSend" class="btn btn-primary" type="button">Send offer</button>
    </div>
    <div id="offerFormStatus" class="form-status offer-form-status"></div>
    <div id="offerMine" class="offer-mine"></div>
  </div>`;
}

function sellerCardHtml(l) {
  const s = l.seller;
  const name = s ? (s.display_name || s.handle) : (l.seller_name || "Seller");
  const founding = (s && s.is_founding) || l.is_founding_seller;
  const foundingBadge = founding ? `<span class="badge founding">★ Founding${s && s.founding_number ? " #" + esc(s.founding_number) : ""}</span>` : "";
  const initial = esc((name || "?").trim().charAt(0).toUpperCase());
  const av = s && s.avatar_url
    ? `<div class="seller-av"><img src="${esc(s.avatar_url)}" alt="${esc(name)}" /></div>`
    : `<div class="seller-av" style="--store-accent:${esc((s && s.accent_color) || "var(--color-accent-fallback)")}">${initial}</div>`;
  if (!s) {
    return `<div class="card seller-card">${av}
      <div class="seller-meta">
        <div class="seller-name">${esc(name)} ${foundingBadge}</div>
        <div class="seller-stars muted">No ratings yet</div>
      </div>
    </div>`;
  }
  const url = `/store/${encodeURIComponent(s.handle)}`;
  return `<div class="card seller-card">${av}
    <div class="seller-meta">
      <div class="seller-name"><a href="${esc(url)}">${esc(name)}</a> ${foundingBadge}</div>
      <div class="seller-stars" id="sellerStars">…</div>
    </div>
    <div class="seller-links">
      <a class="btn btn-ghost btn-sm" href="${esc(url)}">Visit store</a>
      <button class="btn btn-ghost btn-sm" id="followBtn" type="button" data-handle="${esc(s.handle)}">Follow seller</button>
      <a class="btn btn-ghost btn-sm" href="${esc(url)}#message">Message seller</a>
    </div>
  </div>`;
}

function renderMain(l) {
  const sold = l.status === "sold";
  const sub = [l.set_name, l.card_number, l.year].filter((v) => v != null && v !== "").map(esc).join(" · ");
  const ship = l.shipping > 0 ? `+ ${money(l.shipping)} shipping` : "Free shipping";
  $("itemMain").innerHTML = `
    ${sold ? `<div class="sold-banner">SOLD — this item is no longer available</div>` : ""}
    <h1>${esc(l.title)}</h1>
    ${sub ? `<div class="item-sub">${sub}</div>` : ""}
    <div class="price-line"><span class="item-price">${money(l.price)}</span><span class="ship-note">${ship}</span></div>
    <div class="views">👁 ${Number(l.view_count || 0).toLocaleString()} views${!sold && l.quantity > 1 ? ` · ${Number(l.quantity)} available` : ""}</div>
    <div class="action-row">
      <button id="buyBtn" class="btn btn-primary" type="button" ${sold ? "disabled" : ""}>Buy now</button>
      <button id="cartBtn" class="btn btn-ghost" type="button" ${sold ? "disabled" : ""}>Add to cart</button>
      <button id="watchBtn" class="btn btn-ghost" type="button" aria-pressed="false">♡ Watch</button>
      <button id="collectBtn" class="btn btn-ghost" type="button">＋ Collection</button>
      <button id="shareBtn" class="btn btn-ghost" type="button">⤴ Share</button>
    </div>
    <div id="feeLine" class="fee-breakdown" style="margin:10px 0 12px"></div>
    <div id="authNote" class="form-status auth-note"></div>
    ${sold ? "" : offerBoxHtml()}
    ${sellerCardHtml(l)}
    ${l.description ? `<h3 class="desc-head">Description</h3><p class="item-desc">${esc(l.description)}</p>` : ""}`;

  if (!sold) $("buyBtn").addEventListener("click", () => buy());
  if (!sold) $("cartBtn").addEventListener("click", addToCart);
  $("watchBtn").addEventListener("click", toggleWatch);
  $("collectBtn").addEventListener("click", addToCollection);
  $("shareBtn").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href); toast("Link copied"); }
    catch (_) { toast("Could not copy the link."); }
  });
  loadFeeLine(l);
  bindFollow(l);
  if (!sold) {
    $("offerSend").addEventListener("click", submitOffer);
    $("offerAmount").addEventListener("keydown", (e) => { if (e.key === "Enter") submitOffer(); });
    $("offerMsg").addEventListener("keydown", (e) => { if (e.key === "Enter") submitOffer(); });
  }
}

/* ---------- Buy ---------- */
async function buy(offerId) {
  try {
    const o = { method: "POST" };
    if (offerId) o.body = JSON.stringify({ offer_id: offerId });
    const r = await api(`/api/payments/checkout/${encodeURIComponent(ID)}`, o);
    if (r && r.url) { toast("Opening checkout…"); window.open(r.url, "_blank", "noopener"); }
  } catch (e) {
    if (e.status === 401) showAuthNote("Sign in to buy this item.");
    else toast(e.message);
  }
}

async function addToCart() {
  try {
    await api("/api/cart/add", { method: "POST", body: JSON.stringify({ listing_id: Number(ID) }) });
    toast("Added to cart.");
  } catch (e) {
    if (e.status === 401) showAuthNote("Sign in to use your cart.");
    else toast(e.message || "Could not add to cart.");
  }
}

async function addToCollection() {
  try {
    const title = (LISTING && LISTING.title) || "Card";
    await api("/api/collection/add", {
      method: "POST",
      body: JSON.stringify({ listing_id: Number(ID), title }),
    });
    toast("Saved to your collection.");
  } catch (e) {
    if (e.status === 401) showAuthNote("Sign in to save to collection.");
    else toast(e.message || "Could not save.");
  }
}

async function loadFeeLine(l) {
  const el = $("feeLine");
  if (!el || !l || l.price == null) return;
  try {
    const founding = !!(l.is_founding_seller || (l.seller && l.seller.is_founding));
    const q = await api(`/api/fees/quote?price=${encodeURIComponent(l.price)}&founding=${founding ? "true" : "false"}`);
    el.innerHTML = `Fee clarity — platform <b>${(q.platform_rate * 100).toFixed(1)}%</b> (${money(q.platform_fee)}) + card processing <b>${money(q.processing_fee)}</b> (2.9% + $0.30). Seller keeps <b>${money(q.seller_net)}</b>.`;
  } catch (_) {
    el.textContent = "Platform fee 5% (4% Founding) + card processing 2.9% + $0.30.";
  }
}

function bindFollow(l) {
  const btn = $("followBtn");
  if (!btn || !l.seller) return;
  btn.addEventListener("click", async () => {
    try {
      const r = await api("/api/social/follow", {
        method: "POST",
        body: JSON.stringify({ handle: l.seller.handle }),
      });
      btn.textContent = r.following ? "Following" : "Follow seller";
      toast(r.following ? "Following seller." : "Unfollowed.");
    } catch (e) {
      if (e.status === 401) showAuthNote("Sign in to follow sellers.");
      else toast(e.message || "Follow failed.");
    }
  });
}

/* ---------- Watch ---------- */
function paintWatch() {
  const b = $("watchBtn");
  if (b) {
    b.textContent = watching ? "❤ Watching" : "♡ Watch";
    b.setAttribute("aria-pressed", watching ? "true" : "false");
  }
}
async function initWatch() {
  try { const st = await api(`/api/watch/status?ids=${encodeURIComponent(ID)}`); watching = !!(st && st[ID]); paintWatch(); } catch (_) {}
}
async function toggleWatch() {
  try {
    const r = await api("/api/watch", { method: "POST", body: JSON.stringify({ listing_id: Number(ID) }) });
    watching = !!r.watching;
    paintWatch();
    toast(watching ? "Added to your watchlist." : "Removed from your watchlist.");
  } catch (e) {
    if (e.status === 401) showAuthNote("Sign in to watch items.");
    else toast(e.message);
  }
}

/* ---------- Offers ---------- */
function offerStatusHtml(o) {
  const chip = `<span class="offer-chip ${esc(o.status)}">${esc(o.status)}</span>`;
  let extra = "";
  if (o.status === "countered" && o.counter_amount != null) {
    extra = `<div class="offer-actions">Seller countered at <strong>${money(o.counter_amount)}</strong>
      <button class="btn btn-sm btn-primary" data-resp="accept" type="button">Accept</button>
      <button class="btn btn-sm btn-ghost" data-resp="decline" type="button">Decline</button></div>`;
  } else if (o.status === "accepted") {
    extra = `<div class="offer-actions">Accepted at <strong>${money(o.counter_amount != null ? o.counter_amount : o.amount)}</strong>
      <button id="payOfferBtn" class="btn btn-sm btn-primary" type="button">Pay now</button></div>`;
  }
  return `Your offer: <strong>${money(o.amount)}</strong>${chip}${extra}`;
}

function paintOffer() {
  const el = $("offerMine");
  if (!el || !myOffer) return;
  el.innerHTML = offerStatusHtml(myOffer);
  el.querySelectorAll("[data-resp]").forEach((b) => b.addEventListener("click", () => buyerRespond(b.getAttribute("data-resp"))));
  const pay = $("payOfferBtn");
  if (pay) pay.addEventListener("click", () => buy(myOffer.id));
}

async function loadMyOffers() {
  try {
    const r = await api("/api/offers/mine");
    const mine = ((r && r.items) || []).filter((o) => String(o.listing_id) === String(ID));
    if (!mine.length) return;
    const rank = { accepted: 3, countered: 2, open: 1, declined: 0 };
    mine.sort((a, b) => ((rank[b.status] || 0) - (rank[a.status] || 0)) || (b.id - a.id));
    myOffer = mine[0];
    paintOffer();
  } catch (_) { /* anon or unavailable — skip quietly */ }
}

async function submitOffer() {
  const amt = parseFloat($("offerAmount").value);
  const st = $("offerFormStatus");
  if (!(amt > 0)) { st.className = "form-status error"; st.textContent = "Enter an offer amount."; return; }
  const msg = $("offerMsg").value.trim();
  st.className = "form-status"; st.textContent = "Sending offer…";
  try {
    const o = await api("/api/offers", { method: "POST", body: JSON.stringify({ listing_id: Number(ID), amount: amt, message: msg || null }) });
    myOffer = o;
    paintOffer();
    st.className = "form-status ok"; st.textContent = "Offer sent!";
    $("offerAmount").value = ""; $("offerMsg").value = "";
    toast("Offer sent to the seller.");
  } catch (e) {
    if (e.status === 401) { st.className = "form-status error"; st.innerHTML = `Sign in to make offers — <a href="/login">log in</a>.`; }
    else { st.className = "form-status error"; st.textContent = e.message; }
  }
}

async function buyerRespond(action) {
  if (!myOffer) return;
  try {
    const r = await api(`/api/offers/${myOffer.id}/buyer-respond`, { method: "POST", body: JSON.stringify({ action }) });
    myOffer = (r && r.id) ? r : { ...myOffer, status: action === "accept" ? "accepted" : "declined" };
    paintOffer();
    toast(action === "accept" ? "Counter accepted — you can pay now." : "Counter declined.");
  } catch (e) { toast(e.message); }
}

/* ---------- Seller rating ---------- */
async function loadRating(l) {
  const el = $("sellerStars");
  if (!el || !l.seller) return;
  try {
    const r = await api(`/api/orders/store/${encodeURIComponent(l.seller.handle)}/rating`);
    el.innerHTML = (r && r.count > 0)
      ? `★ ${Number(r.avg_stars).toFixed(1)} <span class="muted">(${Number(r.count)})</span>`
      : `<span class="muted">No ratings yet</span>`;
  } catch (_) { el.innerHTML = `<span class="muted">No ratings yet</span>`; }
}

/* ---------- Sold history ---------- */
function sparkline(series) {
  if (!series || series.length < 2) return "";
  const prices = series.map((p) => Number(p.price));
  const min = Math.min(...prices), max = Math.max(...prices);
  const span = (max - min) || 1;
  const W = 600, H = 44, P = 3;
  const pts = prices.map((p, i) =>
    `${((i / (prices.length - 1)) * (W - P * 2) + P).toFixed(1)},${(H - P - ((p - min) / span) * (H - P * 2)).toFixed(1)}`
  ).join(" ");
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="var(--ice)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" /></svg>`;
}

function renderHistory(h) {
  const wrap = $("historyWrap");
  if (!h || !h.count) {
    wrap.innerHTML = `<div class="card history-card">
      <div class="history-head"><span>Sold history</span></div>
      <p class="muted flush">No recorded sales for this card yet — you may hold the first of its name.</p>
    </div>`;
    wrap.hidden = false;
    return;
  }
  const rows = (h.recent || []).map((r) => {
    const date = r.sold_at ? new Date(r.sold_at).toLocaleDateString() : "—";
    const g = r.grading_company ? `${esc(r.grading_company)} ${esc(r.grade)}` : (r.condition ? esc(r.condition) : "Raw");
    const src = r.source ? ` · <span class="muted">${esc(r.source)}</span>` : "";
    return `<li><span>${esc(date)} · ${g}${src}</span><strong>${money(r.price)}</strong></li>`;
  }).join("");
  wrap.innerHTML = `<div class="card history-card">
    <div class="history-head"><span>Sold history</span><span class="history-count">${Number(h.count)} recorded sale${h.count === 1 ? "" : "s"}</span></div>
    <div class="history-stats">
      <div><span class="hs-num">${money(h.suggested_price)}</span><span class="hs-label">Suggested</span></div>
      <div><span class="hs-num">${money(h.average)}</span><span class="hs-label">Average</span></div>
      <div><span class="hs-num">${money(h.low)} – ${money(h.high)}</span><span class="hs-label">Low – High</span></div>
      <div><span class="hs-num">${money(h.last_price)}</span><span class="hs-label">Last sold</span></div>
    </div>
    ${sparkline(h.series)}
    ${rows ? `<ul class="history-list">${rows}</ul>` : ""}
  </div>`;
  wrap.hidden = false;
}

async function loadHistory(l) {
  const params = new URLSearchParams();
  if (l.category) params.set("category", l.category);
  if (l.card_number) params.set("card_number", l.card_number);
  if (l.player_or_character) params.set("player_or_character", l.player_or_character);
  params.set("graded", l.is_graded ? "true" : "false");
  if (l.is_graded && l.grading_company) params.set("grading_company", l.grading_company);
  if (l.is_graded && l.grade != null) params.set("grade", l.grade);
  try {
    renderHistory(await api(`/api/sales/history?${params.toString()}`));
  } catch (err) {
    const wrap = $("historyWrap");
    wrap.innerHTML = `<div class="card history-card">
      <div class="history-head"><span>Sold history</span></div>
      <p class="muted flush">Sold history is temporarily unavailable: ${esc(err.message || "Unknown error")}.</p>
    </div>`;
    wrap.hidden = false;
  }
}

/* ---------- Boot ---------- */
function showNotFound() {
  $("pageState").innerHTML = `<h2>Listing not found</h2>
    <p class="muted">This item may have been removed, or the link is wrong.</p>
    <a class="btn btn-primary" href="/">← Back to the marketplace</a>`;
  $("pageState").hidden = false;
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!ID) { showNotFound(); return; }
  let l;
  try { l = await api(`/api/listings/${encodeURIComponent(ID)}/full`); }
  catch (e) {
    if (e.status === 404) { showNotFound(); return; }
    $("pageState").innerHTML = `<h2>Something went wrong</h2><p class="muted">${esc(e.message)}</p><a class="btn btn-ghost" href="">Try again</a>`;
    return;
  }
  LISTING = l;
  document.title = `${l.title} — RAGNAR`;
  $("pageState").hidden = true;
  $("itemGrid").hidden = false;
  renderPhoto(l);
  renderMain(l);
  initWatch();
  loadMyOffers();
  loadRating(l);
  loadHistory(l);
});
