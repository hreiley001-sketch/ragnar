// RAGNAR — live rides list.
"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

async function api(path) {
  const r = await fetch(path);
  let d = null;
  try { d = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error((d && (d.detail || d.error)) || `Request failed (${r.status})`);
  return d;
}

function bindCardNavigation(nodes, onOpen) {
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

async function load() {
  try {
    const d = await api("/api/rides");
    const grid = $("rgrid");
    if (!d.items.length) { grid.innerHTML = `<p class="muted">No live rides right now. Check back soon — or hosts can launch one from the Command Hub.</p>`; return; }
    grid.innerHTML = d.items.map((r) => {
      const live = r.status === "bidding";
      const bid = r.current_bid != null ? money(r.current_bid) : money(r.starting_bid) + " start";
      return `<div class="rcard" data-id="${r.id}" role="link" tabindex="0" aria-label="Open ride ${esc(r.title)}">
        <div class="rcard-head">
          <span class="rphase ${esc(r.status)}">${live ? '<span class="live-d"></span> ' : ""}${esc(r.status)}</span>
          <span class="rcard-viewers">${r.viewer_count} watching</span>
        </div>
        <div class="rcard-title">${esc(r.title)}</div>
        <div class="rcard-sub">${r.listing ? esc(r.listing.title) : esc(r.type)}${r.seller_handle ? " · @" + esc(r.seller_handle) : ""}</div>
        <div class="rcard-bid-row">
          <div><div class="rcard-bid-label">Current bid</div><div class="rcard-bid-value">${bid}</div></div>
          <span class="btn btn-primary btn-sm">Enter ride →</span>
        </div>
      </div>`;
    }).join("");
    bindCardNavigation(grid.querySelectorAll("[data-id]"), function () {
      location.href = `/ride/${this.getAttribute("data-id")}`;
    });
  } catch (err) {
    $("rgrid").innerHTML = `<p class="muted">Could not load rides: ${esc(err.message || "Unknown error")}.</p>`;
  }
}
document.addEventListener("DOMContentLoaded", () => { load(); setInterval(load, 5000); });
