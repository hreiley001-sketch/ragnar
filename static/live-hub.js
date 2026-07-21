"use strict";
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });

  const api = window.api;

  function card(item, kind) {
    const href = item.href || "#";
    return `<a class="live-hub-card" href="${esc(href)}" data-cat="${esc(item.cat || "")}">
      <div style="display:flex;justify-content:space-between;gap:8px;margin-bottom:8px">
        <span class="badge">${kind === "live" ? '<i class="live-dot"></i> Live' : "Soon"}</span>
        <span class="muted" style="font-size:12px">${esc(item.meta || "")}</span>
      </div>
      <h3 style="margin:0 0 6px;font-size:16px">${esc(item.title)}</h3>
      <p style="margin:0;color:var(--color-text-secondary);font-size:13px">${esc(item.detail || "")}</p>
      <div class="card-actions"><span class="btn btn-ghost btn-sm">Enter →</span></div>
    </a>`;
  }

  function catOf(title) {
    const t = (title || "").toLowerCase();
    if (/pokemon|pokémon|charizard|pikachu/.test(t)) return "pokemon";
    if (/magic|mtg|lotus|lorcana/.test(t)) return "mtg";
    if (/yu-?gi|blue-eyes|yugioh/.test(t)) return "yugioh";
    if (/nba|nfl|mlb|football|basketball|baseball|sports|wembanyama/.test(t)) return "sports";
    return "all";
  }

  async function load() {
    const [streams, rides, stores] = await Promise.all([
      api("/api/streams").catch(() => []),
      api("/api/rides").catch(() => ({ items: [] })),
      api("/api/stores").catch(() => []),
    ]);

    const live = [];
    (streams || []).filter((s) => s.status === "live").forEach((s) => live.push({
      title: s.title, detail: s.seller_name || s.seller_handle, meta: `${s.viewer_count || 0} watching`,
      href: s.seller_handle ? `/store/${encodeURIComponent(s.seller_handle)}` : "/stores",
      cat: catOf(s.title),
    }));
    ((rides && rides.items) || []).filter((r) => !["idle", "archived"].includes(r.status)).forEach((r) => live.push({
      title: r.title, detail: r.seller_handle ? `@${r.seller_handle}` : "RAGNAR House",
      meta: r.current_phase || "live", href: `/ride/${r.id}`, cat: catOf(r.title),
    }));

    const soon = (streams || []).filter((s) => s.status !== "live").slice(0, 8).map((s) => ({
      title: s.title, detail: s.seller_name || s.seller_handle, meta: "Scheduled",
      href: s.seller_handle ? `/store/${encodeURIComponent(s.seller_handle)}` : "/stores",
      cat: catOf(s.title),
    }));

    const recs = (stores || []).slice(0, 6).map((s) => ({
      title: s.display_name, detail: s.tagline || `@${s.handle}`,
      meta: s.is_live ? "Live now" : (s.is_founding ? "Founding" : "Store"),
      href: `/store/${encodeURIComponent(s.handle)}`, cat: "all",
    }));

    function render(filter) {
      const match = (i) => filter === "all" || i.cat === filter || i.cat === "all";
      $("liveNow").innerHTML = live.filter(match).map((i) => card(i, "live")).join("")
        || `<div class="empty-state">No live rooms in this category. <a href="/rides">Browse rides</a></div>`;
      $("liveSoon").innerHTML = soon.filter(match).map((i) => card(i, "soon")).join("")
        || `<div class="empty-state">Nothing scheduled yet.</div>`;
      $("liveRecs").innerHTML = recs.map((i) => card(i, "soon")).join("")
        || `<div class="empty-state"><a href="/stores">Browse stores</a></div>`;
    }

    render("all");
    $("liveCats").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-cat]");
      if (!btn) return;
      $("liveCats").querySelectorAll(".btn").forEach((b) => b.classList.toggle("active", b === btn));
      render(btn.dataset.cat);
    });
  }

  load().catch(() => {
    $("liveNow").innerHTML = `<div class="empty-state">Unable to load live hub.</div>`;
  });
})();
