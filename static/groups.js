"use strict";
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  let kind = "";

  async function api(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error("failed");
    return r.json();
  }

  function card(g) {
    return `<a class="group-card" href="/groups/${encodeURIComponent(g.slug)}">
      <div class="group-card-head">
        <span class="badge">${esc(g.kind || "club")}</span>
        <span class="muted">${Number(g.member_count || 0).toLocaleString()} members</span>
      </div>
      <h3>${esc(g.name)}</h3>
      <p>${esc(g.description || "")}</p>
    </a>`;
  }

  async function load() {
    const q = ($("groupSearch").value || "").trim();
    const params = new URLSearchParams();
    if (kind) params.set("kind", kind);
    if (q) params.set("q", q);
    const data = await api("/api/groups?" + params.toString());
    $("groupGrid").innerHTML = (data.items || []).map(card).join("")
      || `<div class="empty-state">No groups match. Be the first to start one from a group page.</div>`;
  }

  $("groupKinds").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-kind]");
    if (!btn) return;
    kind = btn.dataset.kind || "";
    $("groupKinds").querySelectorAll(".btn").forEach((b) => b.classList.toggle("active", b === btn));
    load();
  });
  $("groupSearch").addEventListener("input", () => {
    clearTimeout($("groupSearch")._t);
    $("groupSearch")._t = setTimeout(load, 220);
  });

  load().catch(() => {
    $("groupGrid").innerHTML = `<div class="empty-state">Unable to load groups.</div>`;
  });
})();
