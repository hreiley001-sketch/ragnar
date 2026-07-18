// RAGNAR Command Hub — admin dashboard.
"use strict";

const $ = (id) => document.getElementById(id);
const money = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let TOKEN = localStorage.getItem("ragnar_admin_token") || "";

let toastTimer = null;
function toast(m) { const e = $("toast"); e.textContent = m; e.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => e.classList.remove("show"), 2600); }

async function api(path, options = {}) {
  const res = await fetch(path, { ...options, headers: { "Content-Type": "application/json", "X-Admin-Token": TOKEN, ...(options.headers || {}) } });
  let data = null; try { data = await res.json(); } catch (_) {}
  if (!res.ok) { const d = data && (data.detail || data.error); throw new Error(typeof d === "string" ? d : `Request failed (${res.status})`); }
  return data;
}

/* ---------- auth ---------- */
async function tryLogin(token) {
  TOKEN = token;
  await api("/api/admin/check");           // throws if bad
  localStorage.setItem("ragnar_admin_token", token);
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
  } catch (e) { toast(e.message); if (String(e.message).includes("token")) logout(); }
}
function kpi(num, label, sub, cls = "") { return `<div class="kpi"><div class="k-num ${cls}">${esc(num)}</div><div class="k-label">${esc(label)}</div><div class="k-sub">${esc(sub)}</div></div>`; }

function renderIntegrations(i) {
  const dot = (on) => `<span class="int-dot ${on ? "on" : "off"}"></span>`;
  const pay = i.payments || {};
  $("intList").innerHTML = [
    ["Card recognition", i.recognition !== "heuristic", i.recognition],
    ["Live pricing", i.live_pricing, i.live_pricing ? "on" : "off"],
    ["External comps", i.external_comps, i.external_comps ? "on" : "off"],
    ["AI (LLM)", i.ai, i.ai ? "on" : "off"],
    ["Card catalog", i.catalog, "Scryfall + Pokémon TCG"],
    ["Payments", pay.configured, pay.configured ? pay.mode : "off"],
    ["PSA data", i.psa, i.psa ? "on" : "off"],
  ].map(([label, on, note]) => `<span class="int-item">${dot(on)}${esc(label)} <span class="muted">(${esc(note)})</span></span>`).join("");
}

/* ---------- listings ---------- */
async function loadListings() {
  try {
    const p = new URLSearchParams();
    const q = $("listSearch").value.trim(); if (q) p.set("q", q);
    const st = $("listStatus").value; if (st) p.set("status", st);
    const d = await api(`/api/admin/listings?${p.toString()}`);
    $("listBody").innerHTML = d.items.map((l) => {
      const gc = l.is_graded && l.grading_company ? `${l.grading_company} ${l.grade}` : (l.condition || "—");
      return `<tr>
        <td>${l.id}</td><td>${esc(l.title)}</td><td>${esc(l.category)}</td><td>${esc(gc)}</td>
        <td>${money(l.price)}</td><td>${esc(l.seller_name)}${l.is_founding_seller ? ' <span class="pill gold">★</span>' : ""}</td>
        <td><span class="pill ${l.status}">${esc(l.status)}</span></td>
        <td class="row-actions">
          <button class="btn btn-sm" data-edit="${l.id}" data-price="${l.price}">Price</button>
          ${l.status === "active" ? `<button class="btn btn-sm" data-sold="${l.id}">Sold</button>` : ""}
          <button class="btn btn-sm" data-del="${l.id}">Del</button>
        </td></tr>`;
    }).join("") || `<tr><td colspan="8" class="muted" style="padding:20px;text-align:center;">No listings</td></tr>`;
  } catch (e) { toast(e.message); }
}

async function listingsAction(e) {
  const t = e.target;
  const edit = t.getAttribute("data-edit");
  const sold = t.getAttribute("data-sold");
  const del = t.getAttribute("data-del");
  try {
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

/* ---------- tabs ---------- */
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => (p.hidden = p.id !== `tab-${name}`));
  if (name === "listings") loadListings();
  if (name === "sellers") loadSellers();
  if (name === "sales") loadSales();
  if (name === "dashboard") loadDashboard();
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
  $("nlBtn").addEventListener("click", nlSearch);
  $("descBtn").addEventListener("click", genDesc);

  if (TOKEN) tryLogin(TOKEN).catch(() => { /* stale token; show gate */ });
});
