"use strict";
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) => "$" + Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });

  async function api(path, opts) {
    const r = await fetch(path, Object.assign({ credentials: "same-origin" }, opts || {}));
    const data = await r.json().catch(() => null);
    if (!r.ok) throw Object.assign(new Error((data && data.detail) || "fail"), { status: r.status, data });
    return data;
  }

  function toast(msg) {
    const el = $("toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 3200);
  }

  function statusIcon(st) {
    if (st === "done") return "✓";
    if (st === "pending") return "…";
    return "○";
  }

  function renderChecklist(data) {
    const box = $("onboardBox");
    const list = $("onboardList");
    const prog = $("onboardProgress");
    const title = $("onboardTitle");
    if (!box || !list || !data) return;

    if (data.complete) {
      title.textContent = "Setup complete";
      prog.textContent = "All required steps done";
      box.classList.add("onboard-complete");
    } else {
      title.textContent = "Get ready to sell";
      prog.textContent = `${data.progress.done_required}/${data.progress.total_required} required · ${data.progress.percent}%`;
      box.classList.remove("onboard-complete");
    }

    list.innerHTML = data.steps.map((step) => {
      const done = step.status === "done";
      const pending = step.status === "pending";
      let cta = "";
      if (!done) {
        if (step.cta_action === "connect_payouts") {
          cta = `<button type="button" class="btn btn-primary btn-sm" data-onboard-action="connect_payouts">Set up payouts</button>`;
        } else if (step.cta_action === "open_sell") {
          cta = `<button type="button" class="btn btn-primary btn-sm" data-open-sell>List with AI</button>`;
        } else if (step.cta_action === "request_verification") {
          if (pending) {
            cta = `<span class="onboard-pending-label">In review</span>`;
          } else {
            cta = `<button type="button" class="btn btn-ghost btn-sm" data-onboard-action="request_verification">Request verification</button>`;
          }
        } else if (step.cta_href) {
          cta = `<a class="btn btn-ghost btn-sm" href="${esc(step.cta_href)}">${esc(step.cta_label || "Open")}</a>`;
        }
      }
      return `<li class="onboard-step status-${esc(step.status)}" data-step="${esc(step.id)}">
        <span class="onboard-mark" aria-hidden="true">${statusIcon(step.status)}</span>
        <div class="onboard-copy">
          <strong>${esc(step.title)}${step.required ? "" : " <em>(optional)</em>"}</strong>
          <p>${esc(step.blurb)}</p>
        </div>
        <div class="onboard-cta">${cta}</div>
      </li>`;
    }).join("");

    box.hidden = false;
    list.querySelectorAll("[data-onboard-action]").forEach((btn) => {
      btn.addEventListener("click", () => handleOnboardAction(btn.getAttribute("data-onboard-action"), data.handle));
    });
  }

  async function handleOnboardAction(action, handle) {
    if (action === "connect_payouts") {
      try {
        const r = await api(`/api/payments/connect/${encodeURIComponent(handle)}`, { method: "POST" });
        if (r.onboarding_url) {
          window.location.href = r.onboarding_url;
          return;
        }
        toast("Payouts link unavailable — is Stripe configured?");
      } catch (e) {
        toast(e.message || "Could not start payouts setup");
      }
      return;
    }
    if (action === "request_verification") {
      try {
        const data = await api("/api/sellers/me/onboarding/request-verification", { method: "POST" });
        renderChecklist(data);
        toast("Verification requested — we'll review soon.");
      } catch (e) {
        toast(e.message || "Could not request verification");
      }
    }
  }

  async function refreshStripeIfNeeded(handle) {
    const params = new URLSearchParams(window.location.search);
    const stripe = params.get("stripe");
    if (!stripe || !handle) return;
    try {
      await api(`/api/payments/connect/${encodeURIComponent(handle)}/status`);
      toast(stripe === "return" ? "Payouts status updated." : "Finish payouts setup when ready.");
    } catch (_) {
      /* Stripe may be unconfigured in dev */
    }
    params.delete("stripe");
    const next = params.toString();
    window.history.replaceState({}, "", window.location.pathname + (next ? `?${next}` : ""));
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
      $("onboardBox").hidden = true;
      return;
    }

    const handle = me.user.seller_handle;
    $("storeLink").href = `/store/${encodeURIComponent(handle)}`;
    await refreshStripeIfNeeded(handle);

    const [store, listings, onboard] = await Promise.all([
      api(`/api/stores/${encodeURIComponent(handle)}`).catch(() => null),
      api(`/api/stores/${encodeURIComponent(handle)}/listings`).catch(() => []),
      api("/api/sellers/me/onboarding").catch(() => null),
    ]);

    if (onboard) renderChecklist(onboard);

    const items = Array.isArray(listings) ? listings : (listings.items || []);
    const active = items.filter((i) => i.status === "active" || !i.status);
    $("dashStats").innerHTML = `
      <div class="dash-card dash-stat"><strong>${active.length}</strong><span>Active listings</span></div>
      <div class="dash-card dash-stat"><strong>${store && store.follower_count != null ? store.follower_count : "—"}</strong><span>Followers</span></div>
      <div class="dash-card dash-stat"><strong>${store && store.is_founding ? "4%" : "5%"}</strong><span>Platform fee</span></div>
      <div class="dash-card dash-stat"><strong>${onboard && onboard.complete ? "Ready" : (onboard ? onboard.progress.percent + "%" : "AI")}</strong><span>${onboard && onboard.complete ? "Onboarding" : (onboard ? "Setup progress" : "Scan · price · tag")}</span></div>`;

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
