// RAGNAR — individual store page (branded, listings, live, self-serve customize).
"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const HANDLE = decodeURIComponent(location.pathname.split("/store/")[1] || "").replace(/\/$/, "");
const TOKEN_KEY = `ragnar_store_token_${HANDLE}`;

let toastTimer;
function toast(m) { const e = $("toast"); e.textContent = m; e.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => e.classList.remove("show"), 2600); }

async function api(p, o = {}) {
  const r = await fetch(p, { ...o, headers: { "Content-Type": "application/json", ...(o.headers || {}) } });
  let d = null; try { d = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error((d && (d.detail || d.error)) || `Request failed (${r.status})`);
  return d;
}
const accentGrad = (c) => `linear-gradient(135deg, ${c || "#6f93b4"}44, #0a0d12), radial-gradient(circle at 30% 20%, ${c || "#6f93b4"}66, transparent 60%)`;
const CREST = `<svg class="placeholder-crest" viewBox="0 0 120 80" xmlns="http://www.w3.org/2000/svg"><g fill="#7fa8c9"><path d="M60 30 L18 20 L30 27 L14 26 L28 33 L16 34 L30 40 L60 40 Z"/><path d="M60 30 L102 20 L90 27 L106 26 L92 33 L104 34 L90 40 L60 40 Z"/><path d="M60 24 L48 30 L44 44 L52 42 L48 54 L60 66 L72 54 L68 42 L76 44 L72 30 Z"/></g><g fill="#6fd6ff"><circle cx="55" cy="42" r="1.8"/><circle cx="65" cy="42" r="1.8"/></g></svg>`;

let STORE = null;
let DESIGN_PRESET = "";

const PRESET_HINTS = {
  whatnot: "Preset: Whatnot-style live seller. Prioritize high-energy live-break language, stream-first CTAs, bold accent contrast, and urgency for drops.",
  ebay: "Preset: eBay-style catalog seller. Prioritize trust signals, clean catalog readability, collector confidence tone, and stable buy-now browsing.",
};

function loadFont(family) {
  if (!family) return;
  const id = "gf-" + family.replace(/\W+/g, "-");
  if (document.getElementById(id)) return;
  const link = document.createElement("link");
  link.id = id;
  link.rel = "stylesheet";
  link.href = "https://fonts.googleapis.com/css2?family=" +
    encodeURIComponent(family).replace(/%20/g, "+") + ":wght@400;600;700&display=swap";
  document.head.appendChild(link);
}

function applyFont(family) {
  loadFont(family);
  // Valid fallback generics — "inherit" is NOT allowed inside a font-family list.
  const stack = family ? `'${family}', system-ui, sans-serif` : "";
  ["storeName", "storeTag"].forEach((id) => {
    const el = $(id);
    if (el) el.style.fontFamily = stack;
  });
}

function applyStore(s) {
  STORE = s;
  if (s.accent_color) document.documentElement.style.setProperty("--ice", s.accent_color);
  applyFont(s.font_family || "");
  document.title = `${s.display_name} — RAGNAR`;
  $("storeName").textContent = s.display_name;
  $("storeTag").textContent = s.tagline || "";
  $("storeBio").textContent = s.bio || "";
  $("storeHero").style.background = s.banner_url ? `center/cover url('${s.banner_optimized || s.banner_url}')` : accentGrad(s.accent_color);
  const av = $("storeAv");
  if (s.avatar_url) { av.style.background = `center/cover url('${s.avatar_optimized || s.avatar_url}')`; av.textContent = ""; }
  else { av.style.background = s.accent_color || "#6f93b4"; av.textContent = (s.display_name || "?").trim()[0].toUpperCase(); }
  // prefill customize
  $("c-tagline").value = s.tagline || "";
  $("c-bio").value = s.bio || "";
  $("c-banner").value = s.banner_url || "";
  $("c-avatar").value = s.avatar_url || "";
  if (s.accent_color) $("c-accent").value = s.accent_color;
  setFontSelection(s.font_family || "");
}

// Populate the heading-font picker from the Google Fonts (or fallback) list.
async function loadFontOptions() {
  const sel = $("c-font");
  if (!sel) return;
  try {
    const d = await api("/api/meta/fonts?limit=80");
    const cur = sel.value;
    sel.innerHTML = '<option value="">Default</option>' +
      (d.items || []).map((f) => `<option value="${esc(f.family)}">${esc(f.family)}</option>`).join("");
    if (cur) setFontSelection(cur);
  } catch (_) { /* keep the Default option */ }
}

// Ensure the current family is selectable even if it's not in the fetched list.
function setFontSelection(family) {
  const sel = $("c-font");
  if (!sel) return;
  if (family && !Array.from(sel.options).some((o) => o.value === family)) {
    const opt = document.createElement("option");
    opt.value = family; opt.textContent = family;
    sel.appendChild(opt);
  }
  sel.value = family || "";
}

function listingCard(l) {
  const badges = [`<span class="badge">${esc(l.category)}</span>`];
  if (l.is_graded && l.grading_company) badges.push(`<span class="badge grade">${esc(l.grading_company)} ${l.grade}</span>`);
  else if (l.condition) badges.push(`<span class="badge">${esc(l.condition)}</span>`);
  const sub = [l.set_name, l.card_number].filter(Boolean).map(esc).join(" · ");
  const src = l.thumb_url || l.image_url;
  const img = src
    ? `<img src="${esc(src)}" alt="${esc(l.title)}" loading="lazy" onerror="this.outerHTML='${CREST.replace(/'/g, "&#39;")}'" />`
    : CREST;
  const sold = l.status === "sold";
  return `<article class="listing">
    <a class="listing-link" href="/listing/${l.id}">
      <div class="listing-img"><div class="listing-badges">${badges.join("")}${sold ? '<span class="badge">SOLD</span>' : ""}</div>${img}</div>
    </a>
    <div class="listing-body">
      <a class="listing-title store-listing-link" href="/listing/${l.id}">${esc(l.title)}</a>${sub ? `<div class="listing-sub">${sub}</div>` : ""}
      <div class="listing-spacer"></div>
      <div class="listing-foot">
        <span class="listing-price">${money(l.price)}</span>
        ${sold ? "" : `<button class="btn btn-sm buy-btn" data-buy="${l.id}">Buy</button>`}
      </div>
    </div>
  </article>`;
}

async function buyListing(id) {
  try { const r = await api(`/api/payments/checkout/${id}`, { method: "POST" }); if (r.url) { toast("Opening checkout…"); window.open(r.url, "_blank", "noopener"); } }
  catch (e) { toast(e.message); }
}

async function loadLive() {
  try {
    const streams = (await api("/api/streams")).filter((s) => s.seller_handle === HANDLE);
    const strip = $("liveStrip");
    if (!streams.length) { strip.innerHTML = ""; return; }
    strip.innerHTML = streams.map((s) => `<div class="live-pill">${s.status === "live" ? '<span class="live-dot"></span> LIVE' : "⏱ SCHEDULED"} · ${esc(s.title)} ${s.status === "live" ? `<span class="muted">(${s.viewer_count} watching)</span>` : ""}</div>`).join("");
    const liveEmbed = streams.find((s) => s.status === "live" && s.embed_url);
    if (liveEmbed) strip.insertAdjacentHTML("afterend", `<div class="embed-wrap"><iframe src="${esc(liveEmbed.embed_url)}" allowfullscreen></iframe></div>`);
  } catch (_) {}
}

async function loadListings() {
  try {
    const items = await api(`/api/stores/${encodeURIComponent(HANDLE)}/listings?include_sold=true`);
    $("listCount").textContent = `${items.filter((i) => i.status === "active").length} listings`;
    $("grid").innerHTML = items.length ? items.map(listingCard).join("") : `<div class="empty">This store has no listings yet.</div>`;
    $("grid").querySelectorAll("[data-buy]").forEach((b) => b.addEventListener("click", () => buyListing(b.getAttribute("data-buy"))));
  } catch (err) {
    $("grid").innerHTML = `<div class="empty">Could not load listings: ${esc(err.message || "Unknown error")}.</div>`;
  }
}

async function saveStore() {
  const token = $("storeToken").value.trim();
  if (!token) { toast("Enter your store token."); return; }
  localStorage.setItem(TOKEN_KEY, token);
  const body = {
    tagline: $("c-tagline").value.trim() || null,
    bio: $("c-bio").value.trim() || null,
    banner_url: $("c-banner").value.trim() || null,
    avatar_url: $("c-avatar").value.trim() || null,
    accent_color: $("c-accent").value || null,
    font_family: $("c-font").value || null,
  };
  const st = $("cStatus"); st.className = "form-status"; st.textContent = "Saving…";
  try {
    const updated = await api(`/api/stores/${encodeURIComponent(HANDLE)}`, { method: "PATCH", headers: { "X-Store-Token": token }, body: JSON.stringify(body) });
    applyStore(updated);
    st.className = "form-status ok"; st.textContent = "Saved!";
    toast("Store updated.");
  } catch (e) { st.className = "form-status error"; st.textContent = e.message; }
}

function addDesignMsg(html, who) {
  const el = document.createElement("div");
  el.className = "design-msg " + who;
  el.innerHTML = html;
  $("designFeed").appendChild(el);
  $("designFeed").scrollTop = $("designFeed").scrollHeight;
  return el;
}

async function runDesigner() {
  const prompt = $("designPrompt").value.trim();
  if (!prompt) return;
  addDesignMsg(esc(prompt), "me");
  $("designPrompt").value = "";
  const thinking = addDesignMsg("Designing…", "ai");
  try {
    const current = { accent_color: $("c-accent").value, tagline: $("c-tagline").value, bio: $("c-bio").value, font_family: $("c-font").value };
    const presetHint = PRESET_HINTS[DESIGN_PRESET] || "";
    const mergedPrompt = presetHint ? `${presetHint}\nUser request: ${prompt}` : prompt;
    const r = await api("/api/ai/design", { method: "POST", body: JSON.stringify({ prompt: mergedPrompt, current }) });
    if (r.accent_color) $("c-accent").value = r.accent_color;
    if (r.tagline) $("c-tagline").value = r.tagline;
    if (r.bio) $("c-bio").value = r.bio;
    if (r.font_family) setFontSelection(r.font_family);
    // Live preview (not persisted until Save).
    applyStore({ ...STORE, accent_color: r.accent_color || STORE.accent_color, tagline: r.tagline || STORE.tagline, bio: r.bio || STORE.bio, font_family: r.font_family || STORE.font_family });
    thinking.remove();
    const sw = r.accent_color ? `<span class="design-swatch" style="background:${esc(r.accent_color)}"></span>` : "";
    addDesignMsg(sw + esc(r.reply || "Updated the preview.") + (r.source ? ` <span class="muted" style="font-size:11px">(${esc(r.source)})</span>` : ""), "ai");
  } catch (e) {
    thinking.remove();
    addDesignMsg("Design failed: " + esc(e.message), "ai");
  }
}

function pickPreset(e) {
  const btn = e.target.closest("[data-preset]");
  if (!btn) return;
  DESIGN_PRESET = btn.getAttribute("data-preset") || "";
  document.querySelectorAll("#designPresetRow [data-preset]").forEach((el) => {
    el.classList.toggle("active", el === btn);
  });
  addDesignMsg(`Preset selected: ${DESIGN_PRESET === "whatnot" ? "Whatnot-style live seller" : "eBay-style catalog seller"}.`, "ai");
}

async function loadSocial() {
  // Followers + rating (public)
  try {
    const f = await api(`/api/social/followers/${encodeURIComponent(HANDLE)}`);
    $("followerCount").textContent = `${f.followers} follower${f.followers === 1 ? "" : "s"}`;
  } catch (_) {}
  try {
    const r = await api(`/api/orders/store/${encodeURIComponent(HANDLE)}/rating`);
    $("storeRating").textContent = r.count ? `★ ${r.avg_stars} (${r.count})` : "No ratings yet";
  } catch (_) {}
  // My follow state + message gate
  try {
    const me = await api("/api/auth/me");
    if (me.user) {
      $("msgGate").hidden = true;
      $("msgForm").hidden = false;
      try {
        const mine = await api("/api/social/follows/mine");
        if ((mine.items || []).some((s) => s.handle === HANDLE)) {
          $("followBtn").textContent = "❤ Following";
          $("followBtn").classList.add("btn-primary");
          $("followBtn").setAttribute("aria-pressed", "true");
        }
      } catch (_) {}
    } else {
      $("msgGate").innerHTML = `<a href="/login">Sign in</a> to message this store.`;
    }
  } catch (_) { $("msgGate").innerHTML = `<a href="/login">Sign in</a> to message this store.`; }
}

async function toggleFollow() {
  try {
    const r = await api("/api/social/follow", { method: "POST", body: JSON.stringify({ handle: HANDLE }) });
    $("followBtn").textContent = r.following ? "❤ Following" : "♡ Follow";
    $("followBtn").classList.toggle("btn-primary", r.following);
    $("followBtn").setAttribute("aria-pressed", r.following ? "true" : "false");
    $("followerCount").textContent = `${r.followers} follower${r.followers === 1 ? "" : "s"}`;
    toast(r.following ? "Following this store — you'll get drop alerts." : "Unfollowed.");
  } catch (e) {
    toast(String(e.message).includes("Sign in") ? "Sign in to follow stores — /login" : e.message);
  }
}

async function sendStoreMessage() {
  const body = $("msgBody").value.trim();
  if (!body) return;
  const st = $("msgStatus"); st.className = "form-status"; st.textContent = "Sending…";
  try {
    await api("/api/social/messages/start", { method: "POST", body: JSON.stringify({ handle: HANDLE, body }) });
    st.className = "form-status ok"; st.textContent = "Sent! Replies land in your account → Messages.";
    $("msgBody").value = "";
  } catch (e) { st.className = "form-status error"; st.textContent = e.message; }
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!HANDLE) { document.body.innerHTML = "<p style='padding:40px'>No store specified.</p>"; return; }
  try { applyStore(await api(`/api/stores/${encodeURIComponent(HANDLE)}`)); }
  catch (e) { $("storeName").textContent = "Store not found"; toast(e.message); return; }
  loadListings();
  loadLive();
  loadSocial();
  loadFontOptions();
  $("followBtn").setAttribute("aria-pressed", "false");
  $("followBtn").addEventListener("click", toggleFollow);
  $("msgSend").addEventListener("click", sendStoreMessage);
  $("c-font").addEventListener("change", (e) => applyFont(e.target.value));

    $("customizeBtn").addEventListener("click", () => {
    const p = $("customizePanel"); p.hidden = !p.hidden;
    const saved = localStorage.getItem(TOKEN_KEY); if (saved) $("storeToken").value = saved;
    if (!p.hidden && !$("designFeed").children.length) {
      addDesignMsg("Hi! Describe the vibe you want and I'll design your store — colors, tagline, and bio. Try “dark and premium for vintage Pokémon” or “bright, fun, sports cards”.", "ai");
    }
  });

    const savedToken = localStorage.getItem(TOKEN_KEY);
    if (savedToken) {
      $("storeToken").value = savedToken;
      $("customizePanel").hidden = false;
      if (!$("designFeed").children.length) {
        addDesignMsg("Welcome back. Describe your next design change and I will draft it instantly.", "ai");
      }
    }
  $("saveStoreBtn").addEventListener("click", saveStore);
  $("designSend").addEventListener("click", runDesigner);
  $("designPrompt").addEventListener("keydown", (e) => { if (e.key === "Enter") runDesigner(); });
  $("designPresetRow").addEventListener("click", pickPreset);
});
