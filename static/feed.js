"use strict";
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) => n == null ? null : "$" + Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
  let followingOnly = false;

  const api = window.api;

  function postCard(p) {
    const seller = p.seller || {};
    const tags = (p.tags || []).map((t) => `<span>${esc(t)}</span>`).join("");
    const value = money(p.market_value);
    return `<article class="feed-card" id="post-${p.id}">
      <div class="feed-card-head">
        <strong>${esc(seller.display_name || "Seller")}</strong>
        <span class="muted">@${esc(seller.handle || "store")}</span>
        <span class="badge">${esc(p.kind || "post")}</span>
      </div>
      ${p.title ? `<h3>${esc(p.title)}</h3>` : ""}
      <p>${esc(p.body)}</p>
      ${value ? `<div class="fee-breakdown" style="margin-top:10px">Market snapshot: <b>${value}</b></div>` : ""}
      <div class="feed-tags">${tags}</div>
      <div class="feed-actions">
        <button class="btn btn-ghost btn-sm" data-like="${p.id}" type="button">♥ ${p.like_count || 0}</button>
        ${p.listing_id ? `<a class="btn btn-ghost btn-sm" href="/listing/${p.listing_id}">View listing</a>` : ""}
        ${seller.handle ? `<a class="btn btn-ghost btn-sm" href="/store/${encodeURIComponent(seller.handle)}">Storefront</a>` : ""}
        ${p.listing_id ? `<button class="btn btn-primary btn-sm" data-list="${p.listing_id}" type="button">List this card</button>` : ""}
      </div>
    </article>`;
  }

  function storyChip(p) {
    const seller = p.seller || {};
    const initial = (seller.display_name || "R").slice(0, 1).toUpperCase();
    return `<a class="story-chip" href="#post-${p.id}">
      <div class="av">${seller.avatar_url ? `<img src="${esc(seller.avatar_url)}" alt="" />` : esc(initial)}</div>
      <span>${esc(seller.handle || "story")}</span>
    </a>`;
  }

  async function load() {
    const [feed, stories] = await Promise.all([
      api(`/api/feed?following_only=${followingOnly}`),
      api("/api/feed?stories=true&limit=12"),
    ]);
    const items = feed.items || [];
    $("feedList").innerHTML = items.map(postCard).join("")
      || `<div class="empty-state">No posts yet. Follow sellers or <a href="/mystore">post from My Store</a>.</div>`;
    $("stories").innerHTML = (stories.items || []).map(storyChip).join("")
      || `<div class="muted" style="padding:8px 0">No stories right now.</div>`;
  }

  $("tabAll").addEventListener("click", () => {
    followingOnly = false;
    $("tabAll").classList.add("active");
    $("tabFollowing").classList.remove("active");
    load();
  });
  $("tabFollowing").addEventListener("click", () => {
    followingOnly = true;
    $("tabFollowing").classList.add("active");
    $("tabAll").classList.remove("active");
    load();
  });

  document.addEventListener("click", async (e) => {
    const like = e.target.closest("[data-like]");
    if (like) {
      try {
        const r = await api(`/api/feed/${like.dataset.like}/like`, { method: "POST" });
        like.textContent = `♥ ${r.like_count}`;
      } catch (_) { /* ignore */ }
    }
    const listBtn = e.target.closest("[data-list]");
    if (listBtn && window.openSell) window.openSell("ai");
  });

  load().catch(() => {
    $("feedList").innerHTML = `<div class="empty-state">Unable to load feed.</div>`;
  });
})();
