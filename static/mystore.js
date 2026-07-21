"use strict";
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) => "$" + Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });

  async function api(path) {
    const r = await fetch(path);
    const data = await r.json().catch(() => null);
    if (!r.ok) throw Object.assign(new Error("fail"), { status: r.status, data });
    return data;
  }

  async function load() {
    let me;
    try { me = await api("/api/auth/me"); } catch (_) { me = { user: null }; }
    if (!me.user) {
      $("guestGate").hidden = false;
      $("sellerDash").hidden = true;
      return;
    }
    $("guestGate").hidden = true;
    $("sellerDash").hidden = false;

    const fees = await api("/api/fees/quote?price=100").catch(() => null);
    if (fees) {
      $("feeBox").innerHTML = `
        On a $100 sale (standard): platform <b>${(fees.platform_rate * 100).toFixed(1)}%</b> =
        <b>${money(fees.platform_fee)}</b>, processing <b>${money(fees.processing_fee)}</b> (2.9% + $0.30),
        you keep <b>${money(fees.seller_net)}</b>. Founding 250 lock in 4% forever.`;
    }

    if (!me.user.seller_handle) {
      $("dashStats").innerHTML = `<div class="dash-card dash-stat"><strong>—</strong><span>No store yet</span></div>`;
      $("invList").innerHTML = `<div class="empty-state">Apply to sell or claim your storefront. <a href="/#apply">Become a seller</a></div>`;
      $("storeLink").href = "/stores";
      return;
    }

    const handle = me.user.seller_handle;
    $("storeLink").href = `/store/${encodeURIComponent(handle)}`;
    const [store, listings] = await Promise.all([
      api(`/api/stores/${encodeURIComponent(handle)}`).catch(() => null),
      api(`/api/stores/${encodeURIComponent(handle)}/listings`).catch(() => []),
    ]);

    const items = Array.isArray(listings) ? listings : (listings.items || []);
    const active = items.filter((i) => i.status === "active" || !i.status);
    $("dashStats").innerHTML = `
      <div class="dash-card dash-stat"><strong>${active.length}</strong><span>Active listings</span></div>
      <div class="dash-card dash-stat"><strong>${store && store.follower_count != null ? store.follower_count : "—"}</strong><span>Followers</span></div>
      <div class="dash-card dash-stat"><strong>${store && store.is_founding ? "4%" : "5%"}</strong><span>Platform fee</span></div>
      <div class="dash-card dash-stat"><strong>AI</strong><span>Scan · price · tag</span></div>`;

    $("invList").innerHTML = active.slice(0, 20).map((l) => `
      <article class="feed-card">
        <h3 style="margin:0 0 6px">${esc(l.title)}</h3>
        <p>${money(l.price)} · ${esc(l.category || "Card")}</p>
        <div class="feed-actions">
          <a class="btn btn-ghost btn-sm" href="/listing/${l.id}">Open</a>
          <button class="btn btn-ghost btn-sm" data-open-sell="ai" type="button">AI reprice</button>
        </div>
      </article>`).join("") || `<div class="empty-state">No inventory yet. <button class="btn btn-primary btn-sm" data-open-sell type="button">List a card</button></div>`;
  }

  $("openSell").addEventListener("click", (e) => {
    e.preventDefault();
    const btn = document.querySelector("[data-open-sell]");
    if (btn) btn.click();
  });

  load().catch(() => {
    $("guestGate").hidden = false;
  });
})();
