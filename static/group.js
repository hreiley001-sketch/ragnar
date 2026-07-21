"use strict";
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const slug = decodeURIComponent((location.pathname.split("/").pop() || "").replace(/\/+$/, ""));

  const api = window.api;

  function threadCard(t) {
    return `<article class="thread-card">
      <div style="display:flex;justify-content:space-between;gap:8px;margin-bottom:6px">
        <span class="muted">${esc(t.author || "Collector")}</span>
        <button class="btn btn-ghost btn-sm" data-up="${t.id}" type="button">▲ ${t.upvotes || 0}</button>
      </div>
      <h3>${esc(t.title)}</h3>
      <p>${esc(t.body)}</p>
      ${t.ai_summary ? `<div class="fee-breakdown"><b>AI summary</b> — ${esc(t.ai_summary)}</div>` : ""}
      <div class="muted" style="margin-top:8px;font-size:12px">${t.comment_count || 0} comments</div>
    </article>`;
  }

  async function load() {
    const data = await api(`/api/groups/${encodeURIComponent(slug)}`);
    const g = data.group;
    $("groupName").textContent = g.name;
    $("groupDesc").textContent = g.description || "";
    $("memberCount").textContent = `${g.member_count || 0} members`;
    $("joinBtn").textContent = g.joined ? "Joined" : "Join group";
    $("joinBtn").disabled = !!g.joined;
    $("threadList").innerHTML = (data.threads || []).map(threadCard).join("")
      || `<div class="empty-state">No threads yet — start the conversation.</div>`;
    document.title = `RAGNAR — ${g.name}`;
  }

  $("joinBtn").addEventListener("click", async () => {
    try {
      await api(`/api/groups/${encodeURIComponent(slug)}/join`, { method: "POST", body: "{}" });
      load();
    } catch (err) {
      $("threadStatus").textContent = err.message || "Sign in to join";
    }
  });

  $("threadForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    try {
      await api(`/api/groups/${encodeURIComponent(slug)}/threads`, {
        method: "POST",
        body: JSON.stringify({ title: fd.get("title"), body: fd.get("body") }),
      });
      e.currentTarget.reset();
      $("threadStatus").textContent = "Posted.";
      load();
    } catch (err) {
      $("threadStatus").textContent = err.message || "Sign in to post";
    }
  });

  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-up]");
    if (!btn) return;
    try {
      const r = await api(`/api/groups/threads/${btn.dataset.up}/upvote`, { method: "POST", body: "{}" });
      btn.textContent = `▲ ${r.upvotes}`;
    } catch (_) { /* ignore */ }
  });

  load().catch(() => {
    $("groupName").textContent = "Group not found";
  });
})();
