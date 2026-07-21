"use strict";
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) => "$" + Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });

  const api = window.api;

  function render(data) {
    if (!data.item_count) {
      $("cartRoot").innerHTML = `<div class="empty-state">Your cart is empty. <a href="/marketplace">Browse marketplace</a></div>`;
      return;
    }
    const blocks = Object.entries(data.by_seller || {}).map(([handle, lines]) => `
      <div class="cart-seller-block">
        <h3>Seller @${esc(handle)}</h3>
        <div class="cart-list">
          ${lines.map((l) => `
            <article class="feed-card">
              <h3 style="margin:0 0 6px">${esc(l.title)}</h3>
              <p>${money(l.price)} × ${l.quantity}</p>
              <div class="fee-breakdown">
                Platform (${(l.fees.platform_rate * 100).toFixed(1)}%): <b>${money(l.fees.platform_fee)}</b><br/>
                Card processing: <b>${money(l.fees.processing_fee)}</b> <span class="muted">(${esc(l.fees.processing_note)})</span><br/>
                Seller keeps: <b>${money(l.fees.seller_net)}</b>
              </div>
              <div class="feed-actions">
                <a class="btn btn-primary btn-sm" href="/listing/${l.listing_id}">Checkout this item</a>
                <button class="btn btn-ghost btn-sm" data-rm="${l.cart_item_id}" type="button">Remove</button>
              </div>
            </article>`).join("")}
        </div>
      </div>`).join("");

    $("cartRoot").innerHTML = `
      <div class="fee-breakdown" style="margin-bottom:16px">${esc(data.checkout_note || "")}</div>
      ${blocks}
      <div class="dash-card"><strong>Subtotal ${money(data.subtotal)}</strong> · ${data.item_count} item(s)</div>`;
  }

  async function load() {
    try {
      render(await api("/api/cart"));
    } catch (err) {
      $("cartRoot").innerHTML = err.status === 401
        ? `<div class="empty-state">Sign in to use your cart. <a href="/login">Sign in</a></div>`
        : `<div class="empty-state">Unable to load cart.</div>`;
    }
  }

  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-rm]");
    if (!btn) return;
    try {
      render(await api(`/api/cart/${btn.dataset.rm}`, { method: "DELETE" }));
    } catch (_) { /* ignore */ }
  });

  load();
})();
