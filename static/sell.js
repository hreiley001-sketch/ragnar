// RAGNAR — the "Sell" drawer: one create-listing flow, reachable from the
// header's ⚡ Sell button (or any [data-open-sell] element) on every page.
// Opens on a choice screen — Scan with AI vs Enter manually — both leading
// into the same underlying form. Seller/payout setup is a separate step that
// collapses to a summary once the visitor has a seller profile.
"use strict";
(function () {
  const $ = (id) => document.getElementById(id);
  const escapeHtml = (s) =>
    String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) =>
    n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  async function api(path, options) {
    const headers = { "Content-Type": "application/json", ...(options?.headers || {}) };
    const res = await fetch(path, { headers, ...options });
    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) {
      const detail = data && (data.detail || data.error);
      throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
    }
    return data;
  }
  async function apiForm(path, formData) {
    const res = await fetch(path, { method: "POST", body: formData });
    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) {
      const detail = data && (data.detail || data.error);
      throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
    }
    return data;
  }

  let toastTimer = null;
  function toast(msg) {
    const el = $("toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 2800);
  }

  function fillSelect(el, values) {
    if (!el) return;
    const first = el.options.length ? el.options[0].outerHTML : "";
    el.innerHTML = first + (values || []).map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join("");
  }

  let META = null;
  function keepInfo(price, introActive) {
    const f = META.fees;
    const rate = introActive ? f.founding_rate : f.standard_rate;
    const keep = price - price * rate - (price * f.processing_rate + f.processing_flat);
    const ebayNet = price - (price * f.ebay_rate + f.ebay_flat);
    return { keep, savings: keep - ebayNet, rate };
  }

  const DRAWER_HTML = `
    <div class="drawer-scrim" id="sellDrawerScrim"></div>
    <div class="drawer-panel card">
      <div class="drawer-head">
        <h3>Sell a card</h3>
        <button id="sellCloseBtn" class="btn btn-ghost btn-sm" type="button">✕</button>
      </div>

      <div id="sellChoice" class="sell-choice">
        <button type="button" class="sell-choice-btn sell-choice-ai" id="sellChoiceAi">
          <span class="sc-badge">Scan Suite</span>
          <strong>Scan with AI</strong>
          <span class="muted">Upload a photo — we identify the card, pull sold-price history, and pre-fill the listing.</span>
        </button>
        <button type="button" class="sell-choice-btn" id="sellChoiceManual">
          <strong>Enter manually</strong>
          <span class="muted">Already know the details? Fill in the form yourself.</span>
        </button>
      </div>

      <button type="button" id="sellBackBtn" class="btn btn-ghost btn-sm back-to-choice" hidden>← Choose a different way</button>

      <div class="scan-zone" id="scanZone" hidden>
        <input id="scanInput" type="file" accept="image/*" hidden />
        <div class="scan-drop" id="scanDrop">
          <div class="scan-drop-inner">
            <div class="scan-icon" aria-hidden="true">◇</div>
            <p><strong>Upload your card photo</strong></p>
            <p class="muted">Identity → comps → pricing. Edit anything before publishing.</p>
          </div>
          <img id="scanPreview" class="scan-preview" alt="" hidden />
        </div>
        <div id="scanResult" class="scan-result" hidden></div>
      </div>

      <div id="historyPanel" class="history-panel" hidden></div>

      <form id="listForm" class="list-form" hidden>
        <div class="form-divider"><span>Card details</span></div>

        <label class="field"><span>Title *</span>
          <input name="title" required maxlength="140" placeholder="Charizard — Base Set Holo" />
        </label>
        <div class="field-row">
          <label class="field"><span>Category *</span><select name="category" id="form-category" required></select></label>
          <label class="field"><span>Year</span><input name="year" type="number" min="1900" max="2100" placeholder="1999" /></label>
        </div>
        <div class="field-row">
          <label class="field"><span>Set</span><input name="set_name" maxlength="120" placeholder="Base Set" /></label>
          <label class="field"><span>Card #</span><input name="card_number" maxlength="40" placeholder="4/102" /></label>
        </div>
        <label class="field"><span>Player / Character</span>
          <input name="player_or_character" maxlength="120" placeholder="Charizard" />
        </label>

        <label class="check-row"><input type="checkbox" name="is_graded" id="form-graded" /><span>This card is professionally graded</span></label>
        <div id="rawFields" class="field"><span>Condition *</span><select name="condition" id="form-condition"></select></div>
        <div id="gradedFields" class="field-row" hidden>
          <label class="field"><span>Grader *</span><select name="grading_company" id="form-grader"></select></label>
          <label class="field"><span>Grade *</span><input name="grade" type="number" min="1" max="10" step="0.5" placeholder="9" /></label>
        </div>

        <div class="field-row price-row">
          <label class="field"><span>Price ($) *</span><input name="price" id="form-price" type="number" min="0.01" step="0.01" required placeholder="42.00" /></label>
          <label class="field"><span>Quantity</span><input name="quantity" type="number" min="1" value="1" /></label>
        </div>
        <div class="inline-row-wrap">
          <button type="button" id="suggestPriceBtn" class="btn btn-ghost btn-sm">✨ Suggest a price</button>
          <button type="button" id="checkCompsBtn" class="btn btn-ghost btn-sm">↻ Check sold history for these details</button>
        </div>
        <div id="suggestOut" class="muted suggest-out"></div>

        <label class="field"><span>Image URL</span><input name="image_url" id="form-image" type="url" maxlength="500" placeholder="auto-filled from your scan" /></label>
        <label class="field"><span>Description</span><textarea name="description" rows="2" maxlength="2000" placeholder="Sharp corners, clean holo…"></textarea></label>

        <div class="form-divider"><span>Seller profile</span></div>
        <div id="sellerSummary" class="seller-summary" hidden>
          <span>✓ Selling as <strong id="sellerSummaryName"></strong></span>
          <button type="button" id="editSellerBtn" class="btn btn-ghost btn-sm">Change</button>
        </div>
        <div id="sellerSetup">
          <div class="field-row">
            <label class="field"><span>Seller handle</span><input name="seller_handle" id="form-handle" maxlength="40" placeholder="yggdrasil" /></label>
            <button type="button" id="applyFoundingBtn" class="btn btn-ghost btn-sm apply-btn">Apply as Founding Seller</button>
          </div>
          <label class="field"><span>Display name *</span><input name="seller_name" id="form-seller" minlength="2" maxlength="80" placeholder="Yggdrasil Cards" /></label>
          <button type="button" id="connectPayoutsBtn" class="btn btn-ghost btn-sm">💳 Set up payouts (Stripe)</button>
          <div id="sellerState" class="seller-state" hidden></div>
        </div>

        <div id="feePreview" class="fee-preview"></div>
        <div class="drawer-actions">
          <button type="submit" class="btn btn-primary">Publish listing</button>
          <span id="formStatus" class="form-status"></span>
        </div>
      </form>
    </div>`;

  // Build the drawer once, eagerly, so it's ready the instant it's opened.
  const drawer = document.createElement("div");
  drawer.id = "sellDrawer";
  drawer.className = "drawer";
  drawer.setAttribute("role", "dialog");
  drawer.setAttribute("aria-modal", "true");
  drawer.setAttribute("aria-label", "Sell a card");
  drawer.setAttribute("aria-hidden", "true");
  drawer.innerHTML = DRAWER_HTML;
  document.body.appendChild(drawer);

  const els = {
    scrim: $("sellDrawerScrim"), close: $("sellCloseBtn"), back: $("sellBackBtn"),
    choice: $("sellChoice"), choiceAi: $("sellChoiceAi"), choiceManual: $("sellChoiceManual"),
    scanZone: $("scanZone"), historyPanel: $("historyPanel"), form: $("listForm"),
    sellerSetup: $("sellerSetup"), sellerSummary: $("sellerSummary"), sellerSummaryName: $("sellerSummaryName"),
  };

  function showChoice() {
    els.choice.hidden = false; els.back.hidden = true;
    els.scanZone.hidden = true; els.historyPanel.hidden = true; els.form.hidden = true;
  }
  function showPath(mode) {
    els.choice.hidden = true; els.back.hidden = false;
    els.form.hidden = false;
    els.scanZone.hidden = mode !== "ai";
  }
  els.choiceAi.addEventListener("click", () => showPath("ai"));
  els.choiceManual.addEventListener("click", () => showPath("manual"));
  els.back.addEventListener("click", showChoice);

  function ensureMeta() {
    if (META) return Promise.resolve(META);
    return api("/api/meta").then((m) => {
      META = m;
      fillSelect($("form-category"), META.categories);
      fillSelect($("form-condition"), META.conditions);
      fillSelect($("form-grader"), META.grading_companies);
      return META;
    });
  }

  let sellerChecked = false;
  function ensureSellerState() {
    if (sellerChecked) return;
    sellerChecked = true;
    api("/api/auth/me").then((d) => {
      const handle = d && d.user && d.user.seller_handle;
      if (!handle) return;
      return api(`/api/sellers/${encodeURIComponent(handle)}`).then((s) => {
        $("form-handle").value = handle;
        $("form-seller").value = s.display_name || handle;
        showSellerState(s);
        updateFeePreview();
      });
    }).catch(() => {});
  }

  function showSellerState(s) {
    els.sellerSetup.hidden = true;
    els.sellerSummary.hidden = false;
    els.sellerSummaryName.textContent = s.display_name || $("form-handle").value;
    $("sellerState").hidden = false;
    const badge = s.is_founding ? `★ <strong>Founding Seller #${s.founding_number}</strong> · ` : "";
    if (s.intro_active) {
      $("sellerState").className = "seller-state founding";
      $("sellerState").innerHTML = `${badge}4% intro fee — ${money(s.intro_sales_remaining)} left before the standard 5% rate`;
    } else {
      $("sellerState").className = s.is_founding ? "seller-state founding" : "seller-state";
      $("sellerState").innerHTML = `${badge}${(s.effective_rate * 100).toFixed(0)}% standard fee`;
    }
    $("sellerState").dataset.founding = s.is_founding ? "1" : "0";
    $("sellerState").dataset.introActive = s.intro_active ? "1" : "0";
  }
  $("editSellerBtn").addEventListener("click", () => {
    els.sellerSetup.hidden = false;
    els.sellerSummary.hidden = true;
  });

  function sellerIntroActive() {
    // Only Founding 250 sellers get the 4% introductory rate; default to the
    // standard rate until we know this seller actually holds founding status.
    return $("sellerState").dataset.introActive === "1";
  }

  function updateFeePreview() {
    if (!META) return;
    const price = parseFloat($("form-price").value);
    const el = $("feePreview");
    if (!price || price <= 0) { el.innerHTML = "Enter a price to see what you keep on RAGNAR vs eBay."; return; }
    const introActive = sellerIntroActive();
    const { keep, savings, rate } = keepInfo(price, introActive);
    el.innerHTML = `On a ${money(price)} sale you keep <strong>${money(keep)}</strong> (${(rate * 100).toFixed(0)}% platform fee${introActive ? " — Founding 250 rate" : ""}). <span class="vs">≈ ${money(savings)} more than eBay.</span>`;
  }

  function syncGradedFields() {
    const graded = $("form-graded").checked;
    $("gradedFields").hidden = !graded;
    $("rawFields").hidden = graded;
    $("form-condition").required = !graded;
    $("form-grader").required = graded;
  }

  /* ---------------- scan-to-post ---------------- */
  function applyScanFields(f) {
    const set = (name, val) => { const el = document.querySelector(`#listForm [name="${name}"]`); if (el && val != null && val !== "") el.value = val; };
    set("title", f.title);
    if (f.category) $("form-category").value = f.category;
    set("set_name", f.set_name);
    set("card_number", f.card_number);
    set("player_or_character", f.player_or_character);
    set("year", f.year);
    $("form-graded").checked = !!f.is_graded;
    syncGradedFields();
    if (f.is_graded) {
      if (f.grading_company) $("form-grader").value = f.grading_company;
      set("grade", f.grade);
    } else if (f.condition) {
      $("form-condition").value = f.condition;
    }
  }

  function sparkline(series) {
    if (!series || series.length < 2) return "";
    const prices = series.map((p) => p.price);
    const min = Math.min(...prices), max = Math.max(...prices);
    const span = max - min || 1;
    const W = 240, H = 44, n = series.length;
    const pts = series.map((p, i) => {
      const x = (i / (n - 1)) * (W - 4) + 2;
      const y = H - 2 - ((p.price - min) / span) * (H - 6);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      <polyline points="${pts}" fill="none" stroke="var(--color-accent-primary)" stroke-width="2" /></svg>`;
  }

  function marketBlock(market) {
    if (!market || market.market == null) return "";
    const chg = market.change_7d;
    const chgHtml = chg == null ? "" : ` <span class="${chg >= 0 ? "delta-up" : "delta-down"}">${chg >= 0 ? "▲" : "▼"} ${Math.abs(chg)}% 7d</span>`;
    return `<div class="market-row">
      <span class="market-label">Live market${market.source ? ` · ${escapeHtml(market.source)}` : ""}</span>
      <span class="market-val">${money(market.market)}${chgHtml}</span>
    </div>`;
  }

  function renderHistory(h, label, market) {
    const panel = $("historyPanel");
    const mkt = marketBlock(market);
    if (!h || !h.count) {
      panel.hidden = false;
      panel.innerHTML = `<div class="history-head"><span>Sold history</span></div>${mkt}
        <p class="muted">No comparable sold data yet${label ? ` for ${escapeHtml(label)}` : ""}. As RAGNAR sales complete (or an external comps provider is configured), comps appear here.</p>`;
      return;
    }
    panel.hidden = false;
    const recent = h.recent.map((r) => {
      const tag = r.grading_company ? `${escapeHtml(r.grading_company)} ${r.grade}` : (r.condition ? escapeHtml(r.condition) : "raw");
      const date = new Date(r.sold_at).toLocaleDateString();
      return `<li><span>${date} · ${tag}</span><strong>${money(r.price)}</strong></li>`;
    }).join("");
    panel.innerHTML = `
      <div class="history-head"><span>Sold history</span><span class="history-count">${h.count} comps</span></div>
      ${mkt}
      <div class="history-stats">
        <div><span class="hs-num">${money(h.suggested_price)}</span><span class="hs-label">suggested</span></div>
        <div><span class="hs-num">${money(h.average)}</span><span class="hs-label">avg</span></div>
        <div><span class="hs-num">${money(h.low)}–${money(h.high)}</span><span class="hs-label">range</span></div>
        <div><span class="hs-num">${money(h.last_price)}</span><span class="hs-label">last sold</span></div>
      </div>
      ${sparkline(h.series)}
      <ul class="history-list">${recent}</ul>
      <button type="button" id="useSuggested" class="btn btn-ghost btn-sm">Use suggested price (${money(h.suggested_price)})</button>`;
    const btn = $("useSuggested");
    if (btn) btn.addEventListener("click", () => { $("form-price").value = h.suggested_price; updateFeePreview(); toast("Suggested price applied."); });
  }

  function historyQueryFromForm() {
    const p = new URLSearchParams();
    const cat = $("form-category").value; if (cat) p.set("category", cat);
    const setn = document.querySelector('#listForm [name="set_name"]').value.trim(); if (setn) p.set("set_name", setn);
    const num = document.querySelector('#listForm [name="card_number"]').value.trim(); if (num) p.set("card_number", num);
    const player = document.querySelector('#listForm [name="player_or_character"]').value.trim(); if (player) p.set("player_or_character", player);
    const graded = $("form-graded").checked; p.set("graded", graded ? "true" : "false");
    if (graded) {
      const gc = $("form-grader").value; if (gc) p.set("grading_company", gc);
      const g = document.querySelector('#listForm [name="grade"]').value; if (g) p.set("grade", g);
    }
    return p.toString();
  }

  async function fetchMarketForForm() {
    if (!META.integrations || !META.integrations.live_pricing) return null;
    const player = document.querySelector('#listForm [name="player_or_character"]').value.trim()
      || document.querySelector('#listForm [name="title"]').value.trim();
    const setn = document.querySelector('#listForm [name="set_name"]').value.trim();
    const cat = $("form-category").value;
    const q = [player, setn].filter(Boolean).join(" ");
    if (!q) return null;
    try {
      const p = new URLSearchParams({ q }); if (cat) p.set("category", cat);
      return await api(`/api/pricing/search?${p.toString()}`);
    } catch (_) { return null; }
  }

  async function checkComps() {
    try {
      const label = document.querySelector('#listForm [name="player_or_character"]').value.trim()
        || document.querySelector('#listForm [name="title"]').value.trim();
      const [h, market] = await Promise.all([
        api(`/api/sales/history?${historyQueryFromForm()}`),
        fetchMarketForForm(),
      ]);
      renderHistory(h, label, market);
    } catch (err) { toast("Could not load sold history: " + err.message); }
  }

  async function suggestPrice() {
    const out = $("suggestOut");
    const q = (n) => { const el = document.querySelector(`#listForm [name="${n}"]`); return el ? el.value.trim() : ""; };
    if (!q("player_or_character") && !q("title")) { out.textContent = "Add a card name/player first, then I can suggest a price."; return; }
    out.textContent = "Pricing…";
    const graded = $("form-graded").checked;
    const payload = {
      title: q("title"), player_or_character: q("player_or_character"),
      set_name: q("set_name"), card_number: q("card_number"),
      category: $("form-category").value || null, is_graded: graded,
      grading_company: graded ? ($("form-grader").value || null) : null,
      grade: graded ? (q("grade") || null) : null,
    };
    try {
      const r = await api("/api/pricing/suggest", { method: "POST", body: JSON.stringify(payload) });
      if (r.suggested_price != null) {
        $("form-price").value = r.suggested_price;
        updateFeePreview();
        const range = (r.low != null && r.high != null) ? ` · range $${r.low}–$${r.high}` : "";
        out.innerHTML = `✨ Suggested <strong>$${r.suggested_price}</strong>${range} — ${r.basis.join(" + ")}. Tweak freely.`;
        toast("Suggested price applied.");
      } else {
        out.textContent = r.note || "Not enough data to suggest a price yet.";
      }
    } catch (e) { out.textContent = "Couldn't suggest a price: " + e.message; }
  }

  async function handleScanFile(file) {
    if (!file) return;
    const preview = $("scanPreview");
    preview.src = URL.createObjectURL(file);
    preview.hidden = false;
    const result = $("scanResult");
    result.hidden = false;
    result.className = "scan-result loading";
    result.textContent = "Scanning card…";
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await apiForm("/api/scan", fd);
      applyScanFields(r.fields);
      if (r.image_url) $("form-image").value = r.image_url;
      const conf = Math.round(r.confidence * 100);
      const tone = conf >= 70 ? "ok" : "warn";
      result.className = `scan-result ${tone}`;
      result.innerHTML = `<strong>${conf}% match</strong> · ${escapeHtml(r.provider)}<br><span class="muted">${escapeHtml(r.notes)}</span>`;
      renderHistory(r.sales_history, r.fields.player_or_character || r.fields.title, r.market_price);
      updateFeePreview();
      toast("Card scanned — details pre-filled. Confirm and publish.");
    } catch (err) {
      result.className = "scan-result error";
      result.textContent = "Scan failed: " + err.message;
    }
  }

  /* ---------------- seller apply ---------------- */
  async function applyFounding() {
    const handle = $("form-handle").value.trim();
    const name = $("form-seller").value.trim();
    if (!handle || !name) { toast("Enter a seller handle and display name first."); return; }
    try {
      const s = await api("/api/sellers/apply", {
        method: "POST",
        body: JSON.stringify({ handle, display_name: name, apply_for_founding: true }),
      });
      showSellerState(s);
      updateFeePreview();
      toast(s.is_founding ? `You're Founding Seller #${s.founding_number}! You start at 4% on your first $250 in sales.` : "Seller created (Founding slots full — standard 5% rate).");
    } catch (err) {
      if (String(err.message).includes("already taken")) {
        try { const s = await api(`/api/sellers/${encodeURIComponent(handle)}`); showSellerState(s); updateFeePreview(); toast("Welcome back — seller loaded."); return; } catch (_) {}
      }
      toast(err.message);
    }
  }

  async function connectPayouts() {
    const handle = $("form-handle").value.trim();
    const name = $("form-seller").value.trim();
    if (!handle) { toast("Enter your seller handle first (and Apply if you're new)."); return; }
    try {
      try { await api("/api/sellers/apply", { method: "POST", body: JSON.stringify({ handle, display_name: name || handle, apply_for_founding: false }) }); } catch (_) {}
      const r = await api(`/api/payments/connect/${encodeURIComponent(handle)}`, { method: "POST" });
      if (r.onboarding_url) { toast("Opening Stripe onboarding…"); window.open(r.onboarding_url, "_blank", "noopener"); }
    } catch (err) { toast(err.message); }
  }

  async function submitListing(e) {
    e.preventDefault();
    const fd = new FormData(e.target);
    const graded = $("form-graded").checked;
    const payload = {
      title: fd.get("title"), category: fd.get("category"),
      set_name: fd.get("set_name") || null, card_number: fd.get("card_number") || null,
      player_or_character: fd.get("player_or_character") || null,
      year: fd.get("year") ? Number(fd.get("year")) : null,
      is_graded: graded,
      condition: graded ? null : fd.get("condition"),
      grading_company: graded ? fd.get("grading_company") : null,
      grade: graded && fd.get("grade") ? Number(fd.get("grade")) : null,
      price: Number(fd.get("price")), quantity: fd.get("quantity") ? Number(fd.get("quantity")) : 1,
      image_url: fd.get("image_url") || null, description: fd.get("description") || null,
      seller_name: fd.get("seller_name") || null,
      seller_handle: fd.get("seller_handle") || null,
    };
    const status = $("formStatus");
    status.className = "form-status"; status.textContent = "Publishing…";
    try {
      const created = await api("/api/listings", { method: "POST", body: JSON.stringify(payload) });
      status.className = "form-status ok"; status.textContent = "Published!";
      toast(`"${created.title}" is live in the vault.`);
      e.target.reset();
      $("scanPreview").hidden = true; $("scanResult").hidden = true; $("historyPanel").hidden = true;
      syncGradedFields(); updateFeePreview();
      close();
      if (window.RagnarMarketplace && window.RagnarMarketplace.reload) window.RagnarMarketplace.reload();
    } catch (err) {
      status.className = "form-status error"; status.textContent = err.message;
    }
  }

  let returnFocus = null;
  function open(mode) {
    returnFocus = document.activeElement;
    ensureMeta().then(() => { updateFeePreview(); ensureSellerState(); });
    drawer.classList.add("open");
    drawer.setAttribute("aria-hidden", "false");
    if (mode === "ai" || mode === "manual") showPath(mode); else showChoice();
    els.close.focus();
  }
  function close() {
    drawer.classList.remove("open");
    drawer.setAttribute("aria-hidden", "true");
    if (returnFocus && typeof returnFocus.focus === "function") returnFocus.focus();
  }
  window.RagnarSell = { open, close };

  drawer.addEventListener("keydown", (event) => {
    if (event.key !== "Tab") return;
    const focusable = [...drawer.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')]
      .filter((element) => !element.hidden && element.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });

  // Delegated so ANY page/button can open the drawer with data-open-sell
  // (optionally data-open-sell="ai" / "manual" to skip the choice screen).
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-open-sell]");
    if (btn) { e.preventDefault(); open(btn.getAttribute("data-open-sell") || undefined); }
  });

  els.close.addEventListener("click", close);
  els.scrim.addEventListener("click", close);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });

  $("scanDrop").addEventListener("click", () => $("scanInput").click());
  $("scanInput").addEventListener("change", (e) => handleScanFile(e.target.files[0]));
  $("scanDrop").addEventListener("dragover", (e) => { e.preventDefault(); $("scanDrop").classList.add("drag"); });
  $("scanDrop").addEventListener("dragleave", () => $("scanDrop").classList.remove("drag"));
  $("scanDrop").addEventListener("drop", (e) => { e.preventDefault(); $("scanDrop").classList.remove("drag"); handleScanFile(e.dataTransfer.files[0]); });

  $("form-graded").addEventListener("change", syncGradedFields);
  $("form-price").addEventListener("input", updateFeePreview);
  $("checkCompsBtn").addEventListener("click", checkComps);
  $("suggestPriceBtn").addEventListener("click", suggestPrice);
  $("applyFoundingBtn").addEventListener("click", applyFounding);
  $("connectPayoutsBtn").addEventListener("click", connectPayouts);
  $("listForm").addEventListener("submit", submitListing);
})();
