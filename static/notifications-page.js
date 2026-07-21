"use strict";
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const api = window.api;

  async function load() {
    try {
      const data = await api("/api/notifications");
      const items = data.items || data || [];
      $("notifList").innerHTML = items.map((n) => `
        <a class="notif-card" href="${esc(n.link || "/account")}" style="text-decoration:none;color:inherit;display:block;opacity:${n.read ? 0.7 : 1}">
          <div style="display:flex;justify-content:space-between;gap:8px">
            <strong>${esc(n.title)}</strong>
            <span class="badge">${esc(n.type || "update")}</span>
          </div>
          <p style="margin:6px 0 0">${esc(n.body || "")}</p>
        </a>`).join("") || `<div class="empty-state">You're all caught up.</div>`;
    } catch (_) {
      $("notifList").innerHTML = `<div class="empty-state">Sign in to see notifications. <a href="/login">Sign in</a></div>`;
    }
  }

  $("markAll").addEventListener("click", async () => {
    try {
      await api("/api/notifications/read-all", { method: "POST" });
      load();
    } catch (_) { /* ignore */ }
  });

  load();
})();
