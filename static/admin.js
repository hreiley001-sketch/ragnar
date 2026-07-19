// RAGNAR Command Hub — admin dashboard.
"use strict";

const $ = (id) => document.getElementById(id);
const money = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtDate = (s) => s ? new Date(s).toLocaleDateString() : "—";
let TOKEN = localStorage.getItem("ragnar_admin_token") || "";
let SITE_ACCESS = { allowed: false, role: null };

let toastTimer = null;
function toast(m) { const e = $("toast"); e.textContent = m; e.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => e.classList.remove("show"), 2600); }

async function api(path, options = {}) {
  const res = await fetch(path, { ...options, headers: { "Content-Type": "application/json", "X-Admin-Token": TOKEN, ...(options.headers || {}) } });
  let data = null; try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const d = data && (data.detail || data.error);
    const msg = typeof d === "string" ? d : (res.status === 401 ? "Not signed in — enter your admin token, or sign in at /login with a staff account." : `Request failed (${res.status})`);
    const err = new Error(msg); err.status = res.status; throw err;
  }
  return data;
}

/* ---------- status pills ---------- */
const PILL_CLASS = {
  pending: "warn", open: "warn", awaiting_shipment: "warn", processing: "warn",
  approved: "ok", paid: "ok", shipped: "ok", delivered: "ok", completed: "ok", resolved_refund: "ok", live: "ok", active: "ok",
  rejected: "bad", cancelled: "bad", canceled: "bad", failed: "bad", resolved_denied: "bad",
  scheduled: "info", pre_show: "info", lobby: "info",
  sold: "sold", ended: "sold",
};
const pill = (s) => `<span class="pill ${PILL_CLASS[s] || ""}">${esc(String(s || "—").replace(/_/g, " "))}</span>`;

/* ---------- auth ---------- */
async function tryLogin(token) {
  TOKEN = token;
  await api("/api/admin/check");           // throws if bad
  if (token) localStorage.setItem("ragnar_admin_token", token);
  $("loginGate").hidden = true;
  $("hub").hidden = false;
  $("logoutBtn").hidden = false;
  loadDashboard();
}

function logout() {
  localStorage.removeItem("ragnar_admin_token");
  TOKEN = "";
  $("hub").hidden = true; $("logoutBtn").hidden = true; $("loginGate").hidden = false;
}

/* ---------- dashboard ---------- */
async function loadDashboard() {
  try {
    const s = await api("/api/admin/stats");
    const f = s.founding;
    $("kpiGrid").innerHTML = `
      ${kpi(money(s.gmv), "GMV", "completed sales", "hot")}
      ${kpi(money(s.estimated_platform_revenue), "Est. revenue", "platform fees")}
      ${kpi(s.orders, "Orders", "completed")}
      ${kpi(s.listings.active, "Active listings", money(s.active_inventory_value) + " value")}
      ${kpi(s.listings.sold, "Sold", `${s.listings.total} total`)}
      ${kpi(s.sellers.total, "Sellers", "registered")}
      ${kpi(`${f.claimed}/${f.cap}`, "Founding 250", `${f.remaining} left`, "gold")}
    `;
    renderIntegrations(s.integrations);
  } catch (e) { toast(e.message); if (e.status === 401 || String(e.message).includes("token")) logout(); }
}
function kpi(num, label, sub, cls = "") { return `<div class="kpi"><div class="k-num ${cls}">${esc(num)}</div><div class="k-label">${esc(label)}</div><div class="k-sub">${esc(sub)}</div></div>`; }

function renderIntegrations(i) {
  const dot = (on) => `<span class="int-dot ${on ? "on" : "off"}"></span>`;
  const pay = i.payments || {};
  const known = [
    ["Card recognition", i.recognition !== "heuristic", i.recognition],
    ["Live pricing", i.live_pricing, i.live_pricing ? "on" : "off"],
    ["External comps", i.external_comps, i.external_comps ? "on" : "off"],
    ["AI (LLM)", i.ai, i.ai ? "on" : "off"],
    ["Card catalog", i.catalog, "Scryfall + Pokémon TCG"],
    ["Payments", pay.configured, pay.configured ? pay.mode : "off"],
    ["PSA data", i.psa, i.psa ? "on" : "off"],
  ];
  // Render any additional integration keys (email/discord/shipping/livekit/seo, …) generically.
  const knownKeys = new Set(["recognition", "live_pricing", "external_comps", "ai", "catalog", "payments", "psa"]);
  const extras = Object.entries(i || {}).filter(([k]) => !knownKeys.has(k)).map(([k, v]) => {
    let on, note;
    if (v && typeof v === "object") { on = !!(v.configured || v.enabled || v.on); note = typeof v.mode === "string" ? v.mode : (on ? "on" : "off"); }
    else if (typeof v === "string") { on = v !== "" && v !== "off"; note = v; }
    else { on = !!v; note = on ? "on" : "off"; }
    const label = k.charAt(0).toUpperCase() + k.slice(1).replace(/_/g, " ");
    return [label, on, note];
  });
  $("intList").innerHTML = [...known, ...extras].map(([label, on, note]) => `<span class="int-item">${dot(on)}${esc(label)} <span class="muted">(${esc(note)})</span></span>`).join("");
}

/* ---------- listings ---------- */
const FEATURED = Object.create(null);   // optimistic is_featured state by listing id

async function loadListings() {
  try {
    const p = new URLSearchParams();
    const q = $("listSearch").value.trim(); if (q) p.set("q", q);
    const st = $("listStatus").value; if (st) p.set("status", st);
    const d = await api(`/api/admin/listings?${p.toString()}`);
    $("listBody").innerHTML = d.items.map((l) => {
      const gc = l.is_graded && l.grading_company ? `${l.grading_company} ${l.grade}` : (l.condition || "—");
      if (l.is_featured !== undefined && l.is_featured !== null) FEATURED[l.id] = !!l.is_featured;
      const feat = !!FEATURED[l.id];
      return `<tr>
        <td>${l.id}</td><td>${feat ? '<span class="pill gold" title="Featured">★</span> ' : ""}${esc(l.title)}</td><td>${esc(l.category)}</td><td>${esc(gc)}</td>
        <td>${money(l.price)}</td><td>${esc(l.seller_name)}${l.is_founding_seller ? ' <span class="pill gold">★</span>' : ""}</td>
        <td><span class="pill ${l.status}">${esc(l.status)}</span></td>
        <td class="row-actions">
          <button class="btn btn-sm" data-feat="${l.id}">${feat ? "★ Unfeature" : "☆ Feature"}</button>
          <button class="btn btn-sm" data-edit="${l.id}" data-price="${l.price}">Price</button>
          ${l.status === "active" ? `<button class="btn btn-sm" data-sold="${l.id}">Sold</button>` : ""}
          ${l.image_url ? `<button class="btn btn-sm" data-enhance="${l.id}" title="AI upscale / clean up photo">✨ Enhance</button>` : ""}
          <button class="btn btn-sm btn-danger" data-del="${l.id}">Del</button>
        </td></tr>`;
    }).join("") || `<tr><td colspan="8" class="muted" style="padding:20px;text-align:center;">No listings</td></tr>`;
  } catch (e) { toast(e.message); }
}

async function listingsAction(e) {
  const t = e.target.closest("button"); if (!t) return;
  const edit = t.getAttribute("data-edit");
  const sold = t.getAttribute("data-sold");
  const del = t.getAttribute("data-del");
  const feat = t.getAttribute("data-feat");
  const enhance = t.getAttribute("data-enhance");
  try {
    if (enhance) {
      if (!confirm("AI-enhance this listing photo (upscale / clean up)?")) return;
      const removeBg = confirm("Also remove the background? (OK = yes, Cancel = keep it)");
      await api(`/api/media/enhance/${enhance}`, { method: "POST", body: JSON.stringify({ upscale: true, remove_bg: removeBg }) });
      toast("Enhancing… the photo will update shortly.");
      setTimeout(loadListings, 6000);
      return;
    }
    if (edit) {
      const cur = t.getAttribute("data-price");
      const np = prompt("New price ($):", cur);
      if (np == null) return;
      await api(`/api/admin/listings/${edit}`, { method: "PATCH", body: JSON.stringify({ price: Number(np) }) });
      toast("Price updated"); loadListings();
    } else if (sold) {
      if (!confirm("Mark this listing sold?")) return;
      await api(`/api/admin/listings/${sold}/mark-sold`, { method: "POST", body: JSON.stringify({}) });
      toast("Marked sold"); loadListings(); loadDashboard();
    } else if (del) {
      if (!confirm("Delete this listing permanently?")) return;
      await api(`/api/admin/listings/${del}`, { method: "DELETE" });
      toast("Deleted"); loadListings(); loadDashboard();
    } else if (feat) {
      const next = !FEATURED[feat];
      await api(`/api/admin/listings/${feat}`, { method: "PATCH", body: JSON.stringify({ is_featured: next }) });
      FEATURED[feat] = next;
      toast(next ? "Listing featured ★" : "Listing unfeatured");
      loadListings();
    }
  } catch (err) { toast(err.message); }
}

/* ---------- sellers / sales ---------- */
async function loadSellers() {
  try {
    const d = await api("/api/admin/sellers");
    $("sellerBody").innerHTML = d.items.map((s) => `<tr>
      <td>${esc(s.handle)}</td><td>${esc(s.display_name)}</td>
      <td>${s.is_founding ? `<span class="pill gold">#${s.founding_number}</span>` : "—"}</td>
      <td>${money(s.founding_intro_sales)}</td>
      <td>${s.stripe_connected ? (s.stripe_charges_enabled ? "✓ ready" : "onboarding") : "—"}</td>
    </tr>`).join("") || `<tr><td colspan="5" class="muted" style="padding:20px;text-align:center;">No sellers</td></tr>`;
  } catch (e) { toast(e.message); }
}
async function loadSales() {
  try {
    const d = await api("/api/admin/sales");
    $("salesBody").innerHTML = d.items.map((s) => `<tr>
      <td>${new Date(s.sold_at).toLocaleDateString()}</td>
      <td>${esc(s.player_or_character || "—")} <span class="muted">${esc(s.set_name || "")}</span></td>
      <td>${esc(s.category)}</td>
      <td>${s.grading_company ? esc(s.grading_company + " " + s.grade) : "—"}</td>
      <td>${money(s.price)}</td><td><span class="pill">${esc(s.source)}</span></td>
    </tr>`).join("") || `<tr><td colspan="6" class="muted" style="padding:20px;text-align:center;">No sales yet</td></tr>`;
  } catch (e) { toast(e.message); }
}

/* ---------- founding applications ---------- */
async function loadApps() {
  try {
    const d = await api("/api/admin/founding-applications");
    $("appsBody").innerHTML = (d.items || []).map((a) => {
      const cats = Array.isArray(a.categories) ? a.categories.join(", ") : (a.categories || "—");
      return `<tr>
        <td>${a.id}</td>
        <td>${esc(a.name)}</td>
        <td><a href="mailto:${esc(a.email)}">${esc(a.email)}</a></td>
        <td>${esc(a.handle_wanted || "—")}</td>
        <td class="wrap-cell">${esc(cats)}</td>
        <td class="wrap-cell">${esc(a.current_platforms || "—")}</td>
        <td>${esc(a.monthly_volume || "—")}</td>
        <td class="wrap-cell">${esc(a.message || "—")}</td>
        <td>${pill(a.status)}</td>
        <td>${fmtDate(a.created_at)}</td>
        <td class="row-actions">${a.status === "pending"
          ? `<button class="btn btn-sm btn-primary" data-approve="${a.id}">Approve</button><button class="btn btn-sm" data-reject="${a.id}">Reject</button>`
          : ""}</td>
      </tr>`;
    }).join("") || `<tr><td colspan="11" class="muted" style="padding:20px;text-align:center;">No applications</td></tr>`;
  } catch (e) { toast(e.message); }
}

async function appsAction(e) {
  const t = e.target.closest("button"); if (!t) return;
  const ap = t.getAttribute("data-approve");
  const rj = t.getAttribute("data-reject");
  try {
    if (ap) {
      if (!confirm("Approve this founding application? This creates their seller store.")) return;
      const r = await api(`/api/admin/founding-applications/${ap}`, { method: "PATCH", body: JSON.stringify({ status: "approved" }) });
      toast("Application approved ⚔");
      if (r && (r.seller_handle || r.store_edit_token)) {
        alert(`Approved — send these to the seller:\n\nSeller handle: ${r.seller_handle || "?"}\nStore edit token: ${r.store_edit_token || "?"}\n\nThey use the token to customize their store at /store/${r.seller_handle || ""}`);
      }
      loadApps(); loadDashboard();
    } else if (rj) {
      if (!confirm("Reject this application?")) return;
      await api(`/api/admin/founding-applications/${rj}`, { method: "PATCH", body: JSON.stringify({ status: "rejected" }) });
      toast("Application rejected"); loadApps();
    }
  } catch (err) { toast(err.message); }
}

/* ---------- orders ---------- */
async function loadOrders() {
  try {
    const d = await api("/api/admin/orders");
    $("ordersBody").innerHTML = (d.items || []).map((o) => {
      const trackTxt = [o.carrier, o.tracking_number].filter(Boolean).join(" ");
      const track = o.tracking_url
        ? `<a href="${esc(o.tracking_url)}" target="_blank" rel="noopener">${esc(trackTxt || "Track")}</a>`
        : (trackTxt ? esc(trackTxt) : "—");
      return `<tr>
        <td>${o.id}</td>
        <td class="wrap-cell">${esc(o.title)}</td>
        <td>${money(o.price)}</td>
        <td>${money(o.shipping)}</td>
        <td><strong>${money(o.total)}</strong></td>
        <td>${pill(o.status)}</td>
        <td>${esc(o.buyer_name || "—")}<br><span class="muted">${esc(o.buyer_email || "")}</span></td>
        <td>${o.seller_handle ? `<a href="/store/${esc(o.seller_handle)}" target="_blank" rel="noopener">${esc(o.seller_handle)}</a>` : "—"}</td>
        <td>${track}</td>
        <td>${fmtDate(o.created_at)}</td>
      </tr>`;
    }).join("") || `<tr><td colspan="10" class="muted" style="padding:20px;text-align:center;">No orders yet</td></tr>`;
  } catch (e) { toast(e.message); }
}

/* ---------- disputes ---------- */
async function loadDisputes() {
  try {
    const d = await api("/api/admin/disputes");
    $("disputesBody").innerHTML = (d.items || []).map((x) => `<tr>
      <td>${x.id}</td>
      <td class="wrap-cell">#${x.order_id} — ${esc(x.order_title || "")}</td>
      <td class="wrap-cell">${esc(x.reason || "—")}</td>
      <td>${pill(x.status)}</td>
      <td class="wrap-cell">${esc(x.resolution || "—")}</td>
      <td>${fmtDate(x.created_at)}</td>
      <td class="row-actions">${x.status === "open"
        ? `<button class="btn btn-sm btn-primary" data-refund="${x.id}">Refund buyer</button><button class="btn btn-sm" data-deny="${x.id}">Deny</button>`
        : ""}</td>
    </tr>`).join("") || `<tr><td colspan="7" class="muted" style="padding:20px;text-align:center;">No disputes — the realm is at peace</td></tr>`;
  } catch (e) { toast(e.message); }
}

async function disputesAction(e) {
  const t = e.target.closest("button"); if (!t) return;
  const rf = t.getAttribute("data-refund");
  const dn = t.getAttribute("data-deny");
  const id = rf || dn; if (!id) return;
  const status = rf ? "resolved_refund" : "resolved_denied";
  const resolution = prompt(rf ? "Resolution note (buyer will be refunded):" : "Resolution note (dispute will be denied):", rf ? "Refunded buyer in full." : "Reviewed — no refund warranted.");
  if (resolution == null) return;
  try {
    await api(`/api/admin/disputes/${id}/resolve`, { method: "POST", body: JSON.stringify({ status, resolution }) });
    toast(rf ? "Dispute resolved — buyer refunded" : "Dispute denied");
    loadDisputes();
  } catch (err) { toast(err.message); }
}

/* ---------- rides ---------- */
async function loadRides() {
  try {
    const d = await api("/api/rides");
    const items = Array.isArray(d) ? d : ((d && (d.items || d.rides)) || []);
    $("ridesBody").innerHTML = items.map((r) => `<tr>
      <td>${r.id}</td>
      <td>${esc(r.title)}</td>
      <td>${pill(r.status)}</td>
      <td>${money(r.current_bid)}</td>
      <td>${r.viewer_count == null ? "—" : r.viewer_count}</td>
      <td class="row-actions">
        <a class="btn btn-sm" href="/ride/${r.id}" target="_blank" rel="noopener">View</a>
        ${r.status !== "live" && r.status !== "ended" ? `<button class="btn btn-sm btn-primary" data-start="${r.id}">Start</button>` : ""}
        <button class="btn btn-sm" data-advance="${r.id}">Advance phase</button>
        <button class="btn btn-sm" data-gwstart="${r.id}">Start giveaway</button>
        <button class="btn btn-sm" data-gwdraw="${r.id}">Draw winner</button>
      </td>
    </tr>`).join("") || `<tr><td colspan="6" class="muted" style="padding:20px;text-align:center;">No rides — launch one above</td></tr>`;
  } catch (e) { toast(e.message); }
}

async function launchRide() {
  const title = $("rideTitle").value.trim();
  if (!title) { toast("Give the ride a title."); return; }
  const body = { title };
  const lid = $("rideListingId").value.trim();
  if (lid) body.listing_id = Number(lid);
  const sb = $("rideStartBid").value.trim();
  if (sb !== "") body.starting_bid = Number(sb);
  const rv = $("rideReserve").value.trim();
  if (rv !== "") body.reserve = Number(rv);
  try {
    const r = await api("/api/hub/ride", { method: "POST", body: JSON.stringify(body) });
    const id = r && (r.id || (r.ride && r.ride.id));
    toast(id ? `Ride #${id} created — hit Start when ready` : "Ride created");
    $("rideTitle").value = ""; $("rideListingId").value = ""; $("rideStartBid").value = ""; $("rideReserve").value = "";
    loadRides();
  } catch (e) { toast(e.message); }
}

async function ridesAction(e) {
  const t = e.target.closest("button"); if (!t) return;
  const start = t.getAttribute("data-start");
  const adv = t.getAttribute("data-advance");
  const gws = t.getAttribute("data-gwstart");
  const gwd = t.getAttribute("data-gwdraw");
  try {
    if (start) {
      await api(`/api/hub/ride/${start}/start`, { method: "POST", body: JSON.stringify({}) });
      toast("Ride started — Valhalla awaits"); loadRides();
    } else if (adv) {
      const r = await api(`/api/hub/ride/${adv}/advance`, { method: "POST", body: JSON.stringify({}) });
      toast("Phase advanced" + (r && (r.phase || r.status) ? ` → ${r.phase || r.status}` : ""));
      loadRides();
    } else if (gws) {
      const title = prompt("Giveaway title:");
      if (!title || !title.trim()) return;
      await api(`/api/rides/${gws}/giveaway/start`, { method: "POST", body: JSON.stringify({ title: title.trim() }) });
      toast("Giveaway started 🎁");
    } else if (gwd) {
      const r = await api(`/api/rides/${gwd}/giveaway/draw`, { method: "POST", body: JSON.stringify({}) });
      const w = r && (r.winner_name || r.winner_handle ||
        (typeof r.winner === "string" ? r.winner : (r.winner && (r.winner.name || r.winner.handle || r.winner.email))));
      toast(w ? `Winner: ${w} 🏆` : "Winner drawn");
    }
  } catch (err) { toast(err.message); }
}

/* ---------- AI tools ---------- */
async function nlSearch() {
  const q = $("nlQuery").value.trim(); if (!q) return;
  $("nlOut").textContent = "Parsing…";
  try {
    const r = await api(`/api/ai/search?q=${encodeURIComponent(q)}`);
    $("nlOut").textContent = `source: ${r.source}\nfilters: ${JSON.stringify(r.filters, null, 2)}\n\nOpen on storefront:`;
    const p = new URLSearchParams(); Object.entries(r.filters).forEach(([k, v]) => p.set(k, v));
    const a = document.createElement("a"); a.href = `/?${p.toString()}`; a.target = "_blank"; a.textContent = ` /?${p.toString()}`; a.style.color = "var(--ice)";
    $("nlOut").appendChild(a);
  } catch (e) { $("nlOut").textContent = e.message; }
}
async function genDesc() {
  const title = $("descTitle").value.trim(); if (!title) return;
  $("descOut").textContent = "Generating…";
  try {
    const r = await api("/api/ai/describe", { method: "POST", body: JSON.stringify({ title, set_name: $("descExtra").value.trim() || null }) });
    $("descOut").textContent = `(${r.source})\n\n${r.description}`;
  } catch (e) { $("descOut").textContent = e.message; }
}

/* ---------- team / staff ---------- */
async function loadTeam() {
  try {
    const p = new URLSearchParams();
    const q = $("userSearch").value.trim(); if (q) p.set("q", q);
    const d = await api(`/api/admin/users?${p.toString()}`);
    $("usersBody").innerHTML = d.items.map((u) => `<tr>
      <td>${esc(u.email)}</td><td>${esc(u.name || "—")}</td>
      <td>${u.is_staff ? '<span class="pill gold">★ staff</span>' : "member"}</td>
      <td>${u.email_verified ? '<span class="pill ok">verified</span>' : '<span class="pill warn">unverified</span>'}</td>
      <td>${u.seller_handle ? esc(u.seller_handle) : "—"}</td>
      <td>${fmtDate(u.created_at)}</td>
      <td class="row-actions">
        ${u.is_staff
          ? `<button class="btn btn-sm" data-revoke="${esc(u.email)}">Revoke staff</button>`
          : `<button class="btn btn-sm" data-grant="${esc(u.email)}">Make staff</button>`}
        <button class="btn btn-sm btn-danger" data-del="${u.id}" data-del-email="${esc(u.email)}" data-del-store="${esc(u.seller_handle || "")}">Remove</button>
      </td></tr>`).join("") || `<tr><td colspan="7" class="muted" style="padding:20px;text-align:center;">No users yet</td></tr>`;
  } catch (e) { toast(e.message); }
}

async function setStaff(email, makeStaff) {
  try {
    await api("/api/admin/staff", { method: "POST", body: JSON.stringify({ email, make_staff: makeStaff }) });
    toast(makeStaff ? `Granted staff to ${email}` : `Revoked staff from ${email}`);
    loadTeam();
  } catch (e) { toast(e.message); }
}

async function grantStaffFromInput() {
  const email = $("staffEmail").value.trim();
  const st = $("staffStatus"); st.className = "form-status";
  if (!email) { st.className = "form-status error"; st.textContent = "Enter an email."; return; }
  try {
    const r = await api("/api/admin/staff", { method: "POST", body: JSON.stringify({ email, make_staff: true }) });
    st.className = "form-status ok"; st.textContent = `${r.email} is now staff.`;
    $("staffEmail").value = ""; loadTeam();
  } catch (e) { st.className = "form-status error"; st.textContent = e.message; }
}

async function deleteUser(id, email, store) {
  let force = false;
  if (store) {
    if (!confirm(`${email} operates store "${store}". Deleting their account will detach it. Delete anyway?`)) return;
    force = true;
  } else if (!confirm(`Permanently remove ${email}? This cannot be undone.`)) return;
  try {
    await api(`/api/admin/users/${id}${force ? "?force=true" : ""}`, { method: "DELETE" });
    toast(`Removed ${email}`);
    loadTeam();
  } catch (e) { toast(e.message); }
}

function teamAction(e) {
  const t = e.target.closest("button"); if (!t) return;
  const grant = t.getAttribute("data-grant");
  const revoke = t.getAttribute("data-revoke");
  const del = t.getAttribute("data-del");
  if (grant) setStaff(grant, true);
  else if (revoke) { if (confirm(`Revoke staff access from ${revoke}?`)) setStaff(revoke, false); }
  else if (del) deleteUser(del, t.getAttribute("data-del-email"), t.getAttribute("data-del-store"));
}

/* ---------- site editor ---------- */
async function loadSite() {
  const box = $("siteFields");
  const access = await loadSiteAccess();
  if (!access.allowed) {
    box.innerHTML = `<p class="form-status error">Site Builder access denied. Use a verified @ragnarips.com staff account with partner role.</p>`;
    setSiteBuilderDisabled(true);
    return;
  }
  setSiteBuilderDisabled(false);
  try {
    const d = await api("/api/admin/site-config");
    const groups = {};
    (d.fields || []).forEach((f) => { (groups[f.group] = groups[f.group] || []).push(f); });
    box.innerHTML = Object.entries(groups).map(([group, fields]) => `
      <div class="card" style="padding:14px;margin-bottom:12px;">
        <div style="font-weight:600;margin-bottom:10px;color:var(--gold);">${esc(group)}</div>
        ${fields.map((f) => {
          const meta = f.updated_by ? `<span class="muted" style="font-size:11px;"> · last edited by ${esc(f.updated_by)}</span>` : "";
          const input = f.type === "textarea"
            ? `<textarea data-key="${esc(f.key)}" rows="3" style="width:100%;">${esc(f.value)}</textarea>`
            : f.type === "color"
            ? `<input data-key="${esc(f.key)}" type="color" value="${esc(f.value || "#6fd6ff")}" style="width:64px;height:34px;padding:2px;" />`
            : `<input data-key="${esc(f.key)}" type="${f.type === "url" ? "url" : "text"}" value="${esc(f.value)}" style="width:100%;" />`;
          return `<label class="field" style="display:block;margin-bottom:12px;">
            <span>${esc(f.label)}${meta}</span>
            ${input}
            ${f.help ? `<span class="muted" style="font-size:12px;">${esc(f.help)}</span>` : ""}
          </label>`;
        }).join("")}
      </div>`).join("");
  } catch (e) { box.innerHTML = `<p class="form-status error">${esc(e.message)}</p>`; }
  await loadCollaborators();
}

function setSiteBuilderDisabled(disabled) {
  ["siteSaveBtn", "studioSendBtn", "studioPrompt", "sendEmailTestBtn", "emailTestTo", "emailTestSubject", "emailTestBody", "addCollabBtn", "collabEmail", "collabRole"].forEach((id) => {
    const el = $(id);
    if (el) el.disabled = !!disabled;
  });
}

async function loadSiteAccess() {
  try {
    SITE_ACCESS = await api("/api/admin/site-builder/access");
  } catch (_) {
    SITE_ACCESS = { allowed: false, role: null };
  }
  const note = $("siteRoleNote");
  if (note) {
    if (SITE_ACCESS.allowed) {
      note.className = "form-status ok";
      note.textContent = `Site Builder role: ${SITE_ACCESS.role}`;
    } else {
      note.className = "form-status error";
      note.textContent = "No Site Builder partner role for this account.";
    }
  }
  return SITE_ACCESS;
}

async function loadCollaborators() {
  const body = $("collabBody");
  if (!body) return;
  if (!SITE_ACCESS.allowed) {
    body.innerHTML = `<tr><td colspan="5" class="muted">Sign in with an eligible staff account.</td></tr>`;
    return;
  }
  try {
    const d = await api("/api/admin/site-collaborators");
    body.innerHTML = (d.items || []).map((r) => `<tr>
      <td>${esc(r.email)}</td>
      <td>${esc(r.role)}</td>
      <td>${esc(r.added_by || "—")}</td>
      <td>${fmtDate(r.updated_at)}</td>
      <td>${SITE_ACCESS.role === "owner" ? `<button class="btn btn-sm" data-del-collab="${esc(r.email)}">Remove</button>` : "—"}</td>
    </tr>`).join("") || `<tr><td colspan="5" class="muted">No partners configured.</td></tr>`;
  } catch (e) {
    body.innerHTML = `<tr><td colspan="5" class="form-status error">${esc(e.message)}</td></tr>`;
  }
}

async function saveCollaborator() {
  const st = $("collabStatus");
  st.className = "form-status";
  if (SITE_ACCESS.role !== "owner") {
    st.className = "form-status error";
    st.textContent = "Only owners can manage partner roles.";
    return;
  }
  const email = $("collabEmail").value.trim().toLowerCase();
  const role = $("collabRole").value;
  if (!email) {
    st.className = "form-status error";
    st.textContent = "Enter a partner email.";
    return;
  }
  try {
    await api("/api/admin/site-collaborators", { method: "POST", body: JSON.stringify({ email, role }) });
    st.className = "form-status ok";
    st.textContent = "Partner role saved.";
    $("collabEmail").value = "";
    loadCollaborators();
  } catch (e) {
    st.className = "form-status error";
    st.textContent = e.message;
  }
}

function collaboratorsAction(e) {
  const btn = e.target.closest("[data-del-collab]");
  if (!btn || SITE_ACCESS.role !== "owner") return;
  const email = btn.getAttribute("data-del-collab");
  if (!confirm(`Remove ${email} from Site Builder roles?`)) return;
  api(`/api/admin/site-collaborators/${encodeURIComponent(email)}`, { method: "DELETE" })
    .then(() => loadCollaborators())
    .catch((err) => toast(err.message));
}

function studioMsg(text, mine = false) {
  const feed = $("studioFeed");
  if (!feed) return null;
  const node = document.createElement("div");
  node.className = "studio-msg" + (mine ? " me" : "");
  node.textContent = text;
  feed.appendChild(node);
  feed.scrollTop = feed.scrollHeight;
  return node;
}

function injectSiteUpdates(updates) {
  Object.entries(updates || {}).forEach(([k, v]) => {
    const el = document.querySelector(`#siteFields [data-key="${CSS.escape(k)}"]`);
    if (el) el.value = v;
  });
}

async function studioSuggest(seed) {
  if (!SITE_ACCESS.allowed) { toast("Site Builder role required."); return; }
  const input = $("studioPrompt");
  const prompt = (seed || (input ? input.value : "") || "").trim();
  if (!prompt) return;
  studioMsg(prompt, true);
  if (input) input.value = "";
  const wait = studioMsg("Designing updates…");
  try {
    const r = await api("/api/admin/studio", { method: "POST", body: JSON.stringify({ message: prompt }) });
    if (wait) wait.remove();
    injectSiteUpdates(r.updates || {});
    studioMsg(r.reply || "Applied suggestions into the editor fields.");
    const ideas = $("studioIdeas");
    if (ideas) {
      ideas.innerHTML = (r.ideas || []).map((i) => `<button class="btn btn-ghost btn-sm" type="button" data-idea="${esc(i)}">${esc(i)}</button>`).join("");
      ideas.querySelectorAll("[data-idea]").forEach((b) => b.addEventListener("click", () => studioSuggest(b.getAttribute("data-idea"))));
    }
  } catch (e) {
    if (wait) wait.remove();
    studioMsg("Studio failed: " + e.message);
  }
}

async function sendEmailTest() {
  const st = $("emailTestStatus");
  st.className = "form-status";
  st.textContent = "Sending…";
  const payload = {
    to: $("emailTestTo").value.trim(),
    subject: $("emailTestSubject").value.trim(),
    message: $("emailTestBody").value.trim(),
  };
  try {
    const r = await api("/api/admin/email/test", { method: "POST", body: JSON.stringify(payload) });
    st.className = r.sent ? "form-status ok" : "form-status error";
    st.textContent = r.sent
      ? `Sent to ${r.to} from ${r.from}`
      : (r.detail || "Send failed");
  } catch (e) {
    st.className = "form-status error";
    st.textContent = e.message;
  }
}

async function saveSite() {
  if (!SITE_ACCESS.allowed) { toast("Site Builder role required."); return; }
  const st = $("siteStatus"); st.className = "form-status"; st.textContent = "Publishing…";
  const updates = {};
  document.querySelectorAll("#siteFields [data-key]").forEach((el) => { updates[el.getAttribute("data-key")] = el.value; });
  try {
    const r = await api("/api/admin/site-config", { method: "PUT", body: JSON.stringify({ updates }) });
    st.className = "form-status ok"; st.textContent = `Published live ✓ (by ${r.by})`;
    toast("Site updated — live on ragnarips.com");
    loadSite();
  } catch (e) { st.className = "form-status error"; st.textContent = e.message; }
}

/* ---------- tabs ---------- */
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => {
    const active = t.dataset.tab === name;
    t.classList.toggle("active", active);
    t.setAttribute("aria-selected", active ? "true" : "false");
    t.setAttribute("tabindex", active ? "0" : "-1");
  });
  document.querySelectorAll(".tab-panel").forEach((p) => (p.hidden = p.id !== `tab-${name}`));
  if (name === "listings") loadListings();
  if (name === "sellers") loadSellers();
  if (name === "sales") loadSales();
  if (name === "dashboard") loadDashboard();
  if (name === "apps") loadApps();
  if (name === "orders") loadOrders();
  if (name === "disputes") loadDisputes();
  if (name === "rides") loadRides();
  if (name === "team") loadTeam();
  if (name === "site") loadSite();
}

/* ---------- init ---------- */
document.addEventListener("DOMContentLoaded", () => {
  $("loginBtn").addEventListener("click", () => tryLogin($("tokenInput").value.trim()).catch((e) => { $("loginErr").textContent = e.message; }));
  $("tokenInput").addEventListener("keydown", (e) => { if (e.key === "Enter") $("loginBtn").click(); });
  $("logoutBtn").addEventListener("click", logout);
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));
  $("listBody").addEventListener("click", listingsAction);
  $("listSearch").addEventListener("input", () => { clearTimeout(window._ls); window._ls = setTimeout(loadListings, 300); });
  $("listStatus").addEventListener("change", loadListings);
  $("appsBody").addEventListener("click", appsAction);
  $("appsRefresh").addEventListener("click", loadApps);
  $("ordersRefresh").addEventListener("click", loadOrders);
  $("disputesBody").addEventListener("click", disputesAction);
  $("disputesRefresh").addEventListener("click", loadDisputes);
  $("ridesBody").addEventListener("click", ridesAction);
  $("ridesRefresh").addEventListener("click", loadRides);
  $("siteSaveBtn").addEventListener("click", saveSite);
  $("siteRefresh").addEventListener("click", loadSite);
  $("studioSendBtn").addEventListener("click", () => studioSuggest());
  $("studioPrompt").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); studioSuggest(); } });
  $("sendEmailTestBtn").addEventListener("click", sendEmailTest);
  $("addCollabBtn").addEventListener("click", saveCollaborator);
  $("collabBody").addEventListener("click", collaboratorsAction);
  $("rideLaunchBtn").addEventListener("click", launchRide);
  $("nlBtn").addEventListener("click", nlSearch);
  $("descBtn").addEventListener("click", genDesc);
  $("grantStaffBtn").addEventListener("click", grantStaffFromInput);
  $("teamRefresh").addEventListener("click", loadTeam);
  $("usersBody").addEventListener("click", teamAction);
  $("userSearch").addEventListener("input", () => { clearTimeout(window._us); window._us = setTimeout(loadTeam, 300); });

  // Token login if stored; with no token this still lets a staff session (cookie) through.
  tryLogin(TOKEN).catch(() => { /* stale token or not signed in; show gate */ });
});
