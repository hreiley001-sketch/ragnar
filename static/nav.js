// RAGNAR — shared hamburger navigation, site header, and chat-widget factory.
// Injected on every page for one consistent header/menu, plus the assistants
// (Concierge/Studio) that are built on the same shared chat component.
"use strict";
(function () {
  const path = (location.pathname.replace(/\/+$/, "") || "/");
  const onHome = path === "/" || document.body.classList.contains("arena-home");
  const onRoom = document.body.classList.contains("premium-room");

  // ---- Asgard realm: fonts + shell CSS + atmosphere on every hall page ----
  function ensureAsgardAssets() {
    if (!document.getElementById("ragnar-fonts")) {
      const pre1 = document.createElement("link");
      pre1.rel = "preconnect";
      pre1.href = "https://fonts.googleapis.com";
      const pre2 = document.createElement("link");
      pre2.rel = "preconnect";
      pre2.href = "https://fonts.gstatic.com";
      pre2.crossOrigin = "anonymous";
      const fonts = document.createElement("link");
      fonts.id = "ragnar-fonts";
      fonts.rel = "stylesheet";
      fonts.href = "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap";
      document.head.appendChild(pre1);
      document.head.appendChild(pre2);
      document.head.appendChild(fonts);
    }
    if (!document.getElementById("asgard-shell-css")) {
      const css = document.createElement("link");
      css.id = "asgard-shell-css";
      css.rel = "stylesheet";
      css.href = "/static/asgard-shell.css";
      document.head.appendChild(css);
    }
  }
  function mountAsgardRealm() {
    // Homepage owns the full vault-env; other pages enter the shared hall.
    document.body.classList.remove("theme-utility");
    if (!onHome) document.body.classList.add("asgard-realm");
    if (onHome) return;

    if (!document.getElementById("asgardAtmosphere")) {
      const atm = document.createElement("div");
      atm.id = "asgardAtmosphere";
      atm.className = "asgard-atmosphere";
      atm.setAttribute("aria-hidden", "true");
      atm.innerHTML = `
        <div class="asgard-atmosphere-rays"></div>
        <div class="asgard-atmosphere-frost"></div>
        <div class="asgard-atmosphere-grid"></div>
        <div class="asgard-atmosphere-runes">
          <span>\u16a6</span><span>\u16b1</span><span>\u16a8</span><span>\u16b7</span><span>\u16be</span>
        </div>`;
      document.body.insertBefore(atm, document.body.firstChild);
    }

    // Embedded ornaments — corners, crest seal, side rails, ice frame.
    if (!document.getElementById("asgardOrnaments") && !onRoom) {
      const orn = document.createElement("div");
      orn.id = "asgardOrnaments";
      orn.className = "asgard-ornaments";
      orn.setAttribute("aria-hidden", "true");
      orn.innerHTML = `
        <div class="asgard-frame"></div>
        <div class="asgard-corner asgard-corner-tl"></div>
        <div class="asgard-corner asgard-corner-tr"></div>
        <div class="asgard-corner asgard-corner-bl"></div>
        <div class="asgard-corner asgard-corner-br"></div>
        <div class="asgard-rail asgard-rail-l"><span>\u16b1</span><span>\u16a8</span><span>\u16b7</span><span>\u16be</span><span>\u16a8</span><span>\u16b1</span></div>
        <div class="asgard-rail asgard-rail-r"><span>\u16a6</span><span>\u16b1</span><span>\u16a8</span><span>\u16df</span><span>\u16b9</span><span>\u16a2</span></div>
        <div class="asgard-crest-seal">
          <img src="/static/logo.png" alt="" width="120" height="120" decoding="async" />
        </div>
        <div class="asgard-spark asgard-spark-a"></div>
        <div class="asgard-spark asgard-spark-b"></div>
        <div class="asgard-spark asgard-spark-c"></div>`;
      document.body.appendChild(orn);
    }
  }

  function embellishAsgardPage() {
    if (onHome || onRoom || !document.body.classList.contains("asgard-realm")) return;

    document.querySelectorAll(".mkt-hero, .platform-hero, .hero-strip, .auth-wrap .logo-c").forEach((hero) => {
      if (hero.querySelector(".asgard-hero-seal")) return;
      const seal = document.createElement("div");
      seal.className = "asgard-hero-seal";
      seal.setAttribute("aria-hidden", "true");
      seal.innerHTML = `<span class="asgard-hero-ring"></span><span class="asgard-hero-ring asgard-hero-ring-2"></span>`;
      hero.prepend(seal);
    });

    document.querySelectorAll(".section-title").forEach((el) => {
      if (el.querySelector(".asgard-section-rune")) return;
      const rune = document.createElement("span");
      rune.className = "asgard-section-rune";
      rune.setAttribute("aria-hidden", "true");
      rune.textContent = "\u16df";
      el.prepend(rune);
    });

    document.querySelectorAll(
      ".card, .listing, .live-card, .store-card, .rcard, .feed-card, .live-hub-card, .dash-card, .auth-wrap, .stat"
    ).forEach((card) => {
      if (card.querySelector(".asgard-foil")) return;
      const foil = document.createElement("span");
      foil.className = "asgard-foil";
      foil.setAttribute("aria-hidden", "true");
      card.classList.add("asgard-panel");
      card.appendChild(foil);
    });
  }

  ensureAsgardAssets();
  mountAsgardRealm();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", embellishAsgardPage);
  } else {
    embellishAsgardPage();
  }
  window.addEventListener("load", () => setTimeout(embellishAsgardPage, 400));

  const ITEMS = [
    { icon: "🛒", label: "Marketplace", href: "/marketplace" },
    { icon: "📡", label: "Live", href: "/live" },
    { icon: "📰", label: "Feed", href: "/feed" },
    { icon: "👥", label: "Groups", href: "/groups" },
    { icon: "🏪", label: "My Store", href: "/mystore" },
    { icon: "🔔", label: "Notifications", href: "/notifications" },
    { icon: "👤", label: "Profile", href: "/account" },
    { icon: "🏠", label: "Home", href: "/" },
    { icon: "⭐", label: "Become a Seller", href: "/#apply" },
  ];

  const mk = (tag, cls) => { const e = document.createElement(tag); if (cls) e.className = cls; return e; };
  function navLink(it) {
    const a = document.createElement("a");
    a.className = "nav-link" + (it.cls ? " " + it.cls : "");
    a.href = it.href;
    a.innerHTML = `<span class="ico">${it.icon}</span><span class="lbl">${it.label}</span>`;
    return a;
  }

  // ---- Shared site header, built into whatever page provides
  // <header id="siteHeader"></header>. Runs synchronously (not on
  // DOMContentLoaded) so page-owned scripts that look up header element IDs
  // (e.g. #logoutBtn, #viewers) on their own DOMContentLoaded still find them —
  // this script tag executes before that event fires. ----
  const acctLinks = [];   // kept in sync together: header link + drawer link
  let headerSellBtn = null;
  function headerExtrasHtml() {
    if (path === "/marketplace") {
      return `<span id="foundingCounter" class="founding-counter" title="Founding Seller slots">Founding —</span><span id="backendStatus" class="status-badge checking">connecting…</span>`;
    }
    if (path.startsWith("/ride/")) {
      return `<span id="viewers" class="status-badge">👁 0</span>`;
    }
    if (path === "/account") {
      return `<button id="logoutBtn" class="btn btn-ghost btn-sm" type="button">Log out</button>`;
    }
    return "";
  }
  function buildHeader() {
    const header = document.getElementById("siteHeader");
    if (!header) return;
    const headerTone = onHome
      ? "site-header site-header--arena site-header--asgard"
      : onRoom
        ? "site-header site-header--room site-header--asgard"
        : "site-header site-header--asgard";
    header.className = headerTone;
    const light = path === "/login" || path === "/verify";
    if (light) {
      header.innerHTML = `
        <div class="brand"><a href="/" class="logo-link"><img src="/static/logo.png" alt="RAGNAR" class="logo-img" /></a></div>
        <div class="header-actions"></div>`;
      return;
    }
    header.innerHTML = `
      <div class="brand"><a href="/" class="logo-link"><img src="/static/logo.png" alt="RAGNAR" class="logo-img" /></a></div>
      <div class="header-actions">
        <div class="header-extra" id="headerExtra">${headerExtrasHtml()}</div>
        <a class="btn btn-ghost btn-sm" href="/marketplace">Marketplace</a>
        <a class="btn btn-ghost btn-sm" href="/live">Live</a>
        <a class="btn btn-ghost btn-sm" href="/feed">Feed</a>
        <a class="btn btn-ghost btn-sm" href="/groups">Groups</a>
        <a class="btn btn-ghost btn-sm" href="/mystore">My Store</a>
        <a class="btn btn-ghost btn-sm" href="/cart" title="Cart">🛒</a>
        <a class="btn btn-ghost btn-sm" href="/notifications" title="Notifications">🔔</a>
        <button class="btn btn-primary btn-sm" type="button" data-open-sell>⚡ Sell</button>
        <a id="headerAcctLink" class="btn btn-ghost btn-sm" href="/login"><span class="lbl">Sign in</span></a>
      </div>`;
    acctLinks.push(header.querySelector("#headerAcctLink"));
    headerSellBtn = header.querySelector("[data-open-sell]");
    if (path.startsWith("/ride/")) {
      const link = document.createElement("a");
      link.className = "btn btn-ghost btn-sm"; link.href = "/rides"; link.textContent = "All rides";
      header.querySelector(".header-actions").insertBefore(link, header.querySelector(".header-extra").nextSibling);
    }
  }
  buildHeader();

  // Drawer
  const scrim = mk("div", "nav-scrim");
  const drawer = mk("div", "nav-drawer");
  drawer.innerHTML = `
    <div class="nav-head">
      <a href="/" style="display:inline-flex"><img src="/static/logo.png" alt="RAGNAR" /></a>
      <button class="nav-close" aria-label="Close menu">✕</button>
    </div>
    <nav class="nav-links" id="navLinks"></nav>
    <div class="nav-foot">RAGNAR · ᚱᚨᚷᚾᚨᚱ</div>`;
  const links = drawer.querySelector("#navLinks");
  ITEMS.forEach((it) => links.appendChild(navLink(it)));
  links.appendChild(mk("div", "nav-div"));
  const userLine = mk("div", "nav-user"); userLine.id = "navUser"; userLine.hidden = true; links.appendChild(userLine);
  const acct = navLink({ icon: "👤", label: "Sign in", href: "/login" }); links.appendChild(acct);
  acctLinks.push(acct);
  // Command Hub is staff-only — hidden until we confirm the user is staff.
  const hub = navLink({ icon: "⚙️", label: "Command Hub", href: "/admin", cls: "nav-hub" }); hub.hidden = true; links.appendChild(hub);

  document.body.appendChild(scrim);
  document.body.appendChild(drawer);

  // Burger button — into the header if present, else a floating button.
  const burger = mk("button", "nav-burger");
  burger.innerHTML = "☰";
  burger.setAttribute("aria-label", "Open menu");
  const actions = document.querySelector(".header-actions");
  if (actions) actions.appendChild(burger);
  else { Object.assign(burger.style, { position: "fixed", top: "14px", right: "14px", zIndex: "82" }); document.body.appendChild(burger); }

  const open = () => { scrim.classList.add("open"); drawer.classList.add("open"); };
  const close = () => { scrim.classList.remove("open"); drawer.classList.remove("open"); };
  burger.addEventListener("click", open);
  scrim.addEventListener("click", close);
  drawer.querySelector(".nav-close").addEventListener("click", close);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });

  // Highlight current page
  links.querySelectorAll("a.nav-link").forEach((a) => {
    const href = (a.getAttribute("href").split("#")[0].replace(/\/+$/, "") || "/");
    if (href === path) a.classList.add("active");
  });

  // ---- Site theme + content (staff-editable via RAGNAR Studio) ----
  function loadWebFont(family) {
    if (!family) return;
    const id = "gf-" + family.replace(/\W+/g, "-");
    if (document.getElementById(id)) return;
    const l = document.createElement("link");
    l.id = id; l.rel = "stylesheet";
    l.href = "https://fonts.googleapis.com/css2?family=" +
      encodeURIComponent(family).replace(/%20/g, "+") + ":wght@400;600;700&display=swap";
    document.head.appendChild(l);
  }
  function shade(hex, amt) {
    // Lightens dark colors and darkens light ones, so --bg-2 always has gentle
    // contrast against --bg whether the theme is light or dark.
    const m = /^#([0-9a-fA-F]{6})$/.exec(hex || ""); if (!m) return hex;
    const n = parseInt(m[1], 16);
    let r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    const d = (r + g + b) > 384 ? -amt : amt;
    r = Math.max(0, Math.min(255, r + d)); g = Math.max(0, Math.min(255, g + d)); b = Math.max(0, Math.min(255, b + d));
    return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
  }
  function applyTheme(c) {
    if (!c) return;
    const s = document.documentElement.style;
    if (c.theme_accent) { s.setProperty("--ice", c.theme_accent); s.setProperty("--ice-strong", c.theme_accent); }
    if (c.theme_gold) s.setProperty("--gold", c.theme_gold);
    if (c.theme_bg) { s.setProperty("--bg", c.theme_bg); s.setProperty("--bg-2", shade(c.theme_bg, 12)); }
    if (c.theme_text) s.setProperty("--text", c.theme_text);
    if (c.theme_font) { loadWebFont(c.theme_font); document.body.style.fontFamily = "'" + c.theme_font + "', system-ui, sans-serif"; }
  }
  function applyAnnouncement(c) {
    let bar = document.getElementById("navAnnounce");
    const msg = c && c.announcement;
    if (!msg) { if (bar) bar.remove(); return; }
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "navAnnounce";
      bar.style.cssText = "position:sticky;top:0;z-index:80;background:linear-gradient(90deg,#0f1620,#16202c);color:var(--ice,#6fd6ff);border-bottom:1px solid rgba(111,214,255,0.25);font-size:13px;font-weight:600;padding:8px 14px;text-align:center;";
      document.body.insertBefore(bar, document.body.firstChild);
    }
    bar.innerHTML = c.announcement_link
      ? `<a href="${c.announcement_link}" style="color:inherit;text-decoration:underline;">${msg}</a>`
      : msg;
  }
  function applyContent(c) {
    // Landing-page copy, if present on this page (skip vault homepage — it owns its hero HTML).
    const onVaultHome = document.body.classList.contains("arena-home");
    if (c.hero_headline && document.getElementById("heroHeadline") && !onVaultHome) {
      document.getElementById("heroHeadline").textContent = c.hero_headline;
    }
    if (c.hero_subtitle && document.getElementById("heroSubtitle") && !onVaultHome) {
      document.getElementById("heroSubtitle").textContent = c.hero_subtitle;
    }
  }
  window.__ragnarApplySite = (c) => { applyTheme(c); applyAnnouncement(c); applyContent(c); };

  // A visitor's personal, LOCAL-only look override (set by the shopper concierge).
  // Never touches the global site — it only restyles this one browser.
  function applyPersonalTheme() {
    try {
      const t = JSON.parse(localStorage.getItem("ragnar_personal_theme") || "null");
      if (t) applyTheme(t);
    } catch (_) { /* ignore */ }
  }
  applyPersonalTheme();

  fetch("/api/site-config").then((r) => r.json()).then((c) => {
    window.__ragnarSite = c;
    window.__ragnarApplySite(c);
    applyPersonalTheme();   // personal override wins over the global theme
  }).catch(() => {});

  // Reflect signed-in state + notifications bell
  fetch("/api/auth/me").then((r) => r.json()).then((d) => {
    if (d && d.user) {
      userLine.hidden = false;
      userLine.textContent = "Signed in · " + (d.user.name || d.user.email);
      acctLinks.forEach((a) => {
        const lbl = a.querySelector(".lbl");
        if (lbl) lbl.textContent = "My account"; else a.textContent = "My account";
        a.href = "/account";
      });
      if (d.user.is_staff) { hub.hidden = false; hub.querySelector(".lbl").textContent = "Command Hub (staff)"; initStudio(); }
      else initConcierge();

      // "Verify your email" banner for unverified accounts (site-wide reminder).
      if (d.user.email_verified === false && !sessionStorage.getItem("ragnar_hide_verify")) {
        const bar = document.createElement("div");
        bar.style.cssText = "position:sticky;top:0;z-index:79;background:linear-gradient(90deg,#8a6d1f,#b8901f);color:#0a0d12;font-size:13px;font-weight:600;padding:8px 14px;display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap;";
        bar.innerHTML = '📬 Verify your email to unlock full access. <a href="#" id="navResend" style="color:#0a0d12;text-decoration:underline;">Resend link</a> <span id="navVdismiss" style="cursor:pointer;opacity:.7;">✕</span>';
        document.body.insertBefore(bar, document.body.firstChild);
        bar.querySelector("#navResend").addEventListener("click", async (e) => {
          e.preventDefault();
          try { const r = await fetch("/api/auth/resend-verification", { method: "POST" }).then((x) => x.json()); e.target.textContent = r.sent ? "Sent ✓" : "Email not set up"; }
          catch (_) { e.target.textContent = "Try again later"; }
        });
        bar.querySelector("#navVdismiss").addEventListener("click", () => { sessionStorage.setItem("ragnar_hide_verify", "1"); bar.remove(); });
      }

      const bell = document.createElement("a");
      bell.className = "nav-bell";
      bell.href = "/account#notifications";
      bell.setAttribute("aria-label", "Notifications");
      bell.innerHTML = "🔔";
      if (actions) actions.insertBefore(bell, burger);
      const refreshBell = () =>
        fetch("/api/notifications/unread-count").then((r) => r.json()).then((c) => {
          const n = (c && c.unread) || 0;
          let b = bell.querySelector(".bump");
          if (n > 0) {
            if (!b) { b = document.createElement("span"); b.className = "bump"; bell.appendChild(b); }
            b.textContent = n > 99 ? "99+" : String(n);
          } else if (b) b.remove();
        }).catch(() => {});
      refreshBell();
      setInterval(refreshBell, 30000);
    } else {
      initConcierge();   // logged-out visitors get the shopper concierge too
    }
  }).catch(() => { initConcierge(); });

  // ---- Shared chat-widget factory: builds a FAB + slide-up panel with a
  // feed/chips/input, used by Concierge, Studio, and (via window.__ragnarChat)
  // the seller-facing Store Designer. One visual language, one place to tweak it. ----
  const escHtml = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function createChatWidget(opts) {
    const { key, icon, label, gold, publish, footNote } = opts;
    const fab = mk("button", "chat-fab" + (gold ? " chat-fab-gold" : ""));
    fab.innerHTML = `${icon} ${label}`;
    fab.id = "fab-" + key;

    const panel = mk("div", "chat-panel");
    panel.id = "panel-" + key;
    panel.innerHTML = `
      <div class="chat-head">
        <div class="chat-head-title">${icon} ${label}</div>
        <button class="chat-close" aria-label="Close">✕</button>
      </div>
      <div class="chat-feed"></div>
      <div class="chat-chips"></div>
      <div class="chat-input-row">
        <input placeholder="${footNote ? escHtml(footNote) : "Type a message…"}" />
        <button class="chat-send" type="button">➤</button>
      </div>
      ${publish ? `<div class="chat-foot">
        <div class="chat-publish-row">
          <button class="btn btn-ghost btn-sm chat-revert" type="button">Revert</button>
          <button class="btn btn-primary btn-sm chat-publish-btn" disabled type="button">Publish live</button>
        </div>
        <div class="chat-status"></div>
      </div>` : ""}`;

    document.body.appendChild(fab);
    document.body.appendChild(panel);

    const feed = panel.querySelector(".chat-feed");
    const chipsBox = panel.querySelector(".chat-chips");
    const input = panel.querySelector(".chat-input-row input");
    const sendBtn = panel.querySelector(".chat-send");

    const msg = (html, who) => {
      const el = mk("div", "chat-msg" + (who === "me" ? " me" : ""));
      el.innerHTML = html;
      feed.appendChild(el); feed.scrollTop = feed.scrollHeight;
      return el;
    };
    const chips = (arr) => {
      chipsBox.innerHTML = "";
      (arr || []).forEach((t) => {
        const c = mk("button", "chat-chip");
        c.textContent = t;
        c.addEventListener("click", () => { input.value = t; sendBtn.click(); });
        chipsBox.appendChild(c);
      });
    };

    let onOpenFirst = null;
    const toggle = () => {
      const isOpen = panel.classList.contains("open");
      panel.classList.toggle("open", !isOpen);
      if (!isOpen && !feed.children.length && onOpenFirst) onOpenFirst();
    };
    fab.addEventListener("click", toggle);
    panel.querySelector(".chat-close").addEventListener("click", () => panel.classList.remove("open"));
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") sendBtn.click(); });

    return {
      fab, panel, feed, input, sendBtn, msg, chips, escHtml,
      publishBtn: panel.querySelector(".chat-publish-btn"),
      revertBtn: panel.querySelector(".chat-revert"),
      statusEl: panel.querySelector(".chat-status"),
      onFirstOpen: (fn) => { onOpenFirst = fn; },
      onSend: (fn) => { sendBtn.addEventListener("click", fn); },
    };
  }
  window.__ragnarChat = createChatWidget;

  // ---- RAGNAR Concierge: a floating shopper assistant for EVERYONE. It finds
  // cards by vibe (plain language, not exact keywords) and can restyle the
  // visitor's OWN view — local-only, never the real site or anyone else. ----
  const VIBES = [
    [["gold", "lux", "premium", "elite", "luxury", "grail", "royal", "regal"], "#f0c674"],
    [["ice", "frost", "blue", "arctic", "cool", "cold", "steel"], "#6fd6ff"],
    [["fire", "red", "ember", "hot", "bold", "aggressive", "crimson", "blood"], "#ff6b5e"],
    [["green", "mint", "emerald", "money", "forest"], "#6fe3b0"],
    [["purple", "cosmic", "galaxy", "mystic", "magic", "violet"], "#b18cff"],
    [["pink", "cute", "pastel", "soft", "kawaii"], "#ff9ecb"],
    [["vintage", "retro", "classic", "warm", "cozy", "amber", "sepia"], "#e0a45e"],
  ];
  const PERSONAL_RE = /\b(my view|make it|make my|theme|background|colou?r|font|dark mode|light mode|high contrast|restyle|recolou?r|bigger text|darker|lighter|brighter)\b/i;

  let conciergeBuilt = false;
  function initConcierge() {
    if (conciergeBuilt) return;
    conciergeBuilt = true;
    const w = createChatWidget({ key: "concierge", icon: "💬", label: "Ask RAGNAR", footNote: "What are you hunting for?" });

    function personalize(text) {
      const low = text.toLowerCase();
      const theme = {};
      for (const [kws, hex] of VIBES) { if (kws.some((k) => low.includes(k))) { theme.theme_accent = hex; break; } }
      if (/\b(dark|darker|midnight|black|night)\b/.test(low)) theme.theme_bg = "#05070b";
      else if (/\b(light|lighter|bright|brighter|white|day)\b/.test(low)) theme.theme_bg = "#12161d";
      const fm = text.match(/font\s*(?:to|:|=)?\s*['"]?([A-Z][A-Za-z ]{2,30})['"]?/);
      if (fm) theme.theme_font = fm[1].trim();
      if (/reset|default|normal|undo/.test(low)) {
        localStorage.removeItem("ragnar_personal_theme");
        window.__ragnarApplySite(window.__ragnarSite || {});
        return "Reset — you're back to RAGNAR's normal look.";
      }
      if (!Object.keys(theme).length) return null;
      const merged = Object.assign(JSON.parse(localStorage.getItem("ragnar_personal_theme") || "{}"), theme);
      localStorage.setItem("ragnar_personal_theme", JSON.stringify(merged));
      applyTheme(merged);
      return "Done — I restyled your view (just for you). Say “reset my view” to undo.";
    }

    w.onSend(async () => {
      const text = w.input.value.trim();
      if (!text) return;
      w.input.value = "";
      w.msg(escHtml(text), "me");
      if (PERSONAL_RE.test(text)) {
        const r = personalize(text);
        if (r) { w.msg(r); return; }
      }
      const thinking = w.msg("Searching…");
      try {
        const r = await fetch(`/api/ai/search?q=${encodeURIComponent(text)}`).then((x) => x.json());
        thinking.remove();
        const f = r.filters || {};
        const p = new URLSearchParams();
        Object.entries(f).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") p.set(k, v); });
        const bits = [f.q, f.grading_company, f.category].filter(Boolean).join(" ");
        w.msg(`Hunting for ${escHtml(bits || text)} — taking you to the results…`);
        setTimeout(() => { location.href = "/marketplace?" + p.toString(); }, 700);
      } catch (e) { thinking.remove(); w.msg("Couldn't search just now — try again."); }
    });

    w.onFirstOpen(() => {
      w.msg("Hey! Tell me what you're after — a card, a player, a vibe — and I'll find it. I can also restyle your view just for you. 🐺");
      w.chips(["Vintage Charizard grails", "Cheap graded rookies under $50", "A gift for a Lakers fan", "Make my view dark & cozy"]);
    });
  }

  // ---- RAGNAR Studio: a floating AI assistant for staff to sculpt the whole
  // site (look + copy) in plain English. Preview live, publish in one tap. ----
  let studioBuilt = false;
  function initStudio() {
    if (studioBuilt) return;
    studioBuilt = true;
    const pending = {};   // accumulated updates not yet published
    const w = createChatWidget({ key: "studio", icon: "✨", label: "Studio", gold: true, publish: true, footNote: "Tell me how to sculpt the site…" });

    const setPublish = () => {
      const n = Object.keys(pending).length;
      w.publishBtn.disabled = n === 0;
      w.publishBtn.textContent = n === 0 ? "Publish live" : `Publish ${n} change${n === 1 ? "" : "s"}`;
    };

    w.onSend(async () => {
      const text = w.input.value.trim();
      if (!text) return;
      w.input.value = "";
      w.msg(escHtml(text), "me");
      const thinking = w.msg("…");
      try {
        const r = await fetch("/api/admin/studio", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: text }) }).then((x) => x.json());
        thinking.remove();
        w.msg(escHtml(r.reply || "Done."));
        const keys = Object.keys(r.updates || {});
        if (keys.length) {
          Object.assign(pending, r.updates);
          window.__ragnarApplySite(Object.assign({}, window.__ragnarSite, pending));
          w.msg(`<span class="chat-note">Previewing: ${keys.map(escHtml).join(", ")} — Publish to make it live.</span>`);
          setPublish();
        }
        w.chips(r.ideas);
      } catch (e) { thinking.remove(); w.msg("Something went wrong — try again."); }
    });

    w.publishBtn.addEventListener("click", async () => {
      if (!Object.keys(pending).length) return;
      w.statusEl.textContent = "Publishing…";
      try {
        const r = await fetch("/api/admin/site-config", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ updates: pending }) }).then((x) => x.json());
        window.__ragnarSite = r.config || window.__ragnarSite;
        for (const k in pending) delete pending[k];
        setPublish();
        w.statusEl.textContent = `Published live ✓ (by ${r.by || "you"})`;
        w.msg("Published — it's live on the site now. ✨");
      } catch (e) { w.statusEl.textContent = "Publish failed — check your access."; }
    });
    w.revertBtn.addEventListener("click", () => {
      for (const k in pending) delete pending[k];
      window.__ragnarApplySite(window.__ragnarSite);
      setPublish(); w.statusEl.textContent = "Reverted to the live version.";
    });

    w.onFirstOpen(() => {
      w.msg("Hey — I'm your Studio assistant. Tell me the vibe and I'll sculpt the whole site: colors, font, announcement, landing copy. Big swings welcome. 🐺");
      w.chips(["Midnight forge: black + ember gold", "Icy, premium, minimal", "Announce our Friday live drop", "Bolder headline about beating eBay fees"]);
    });
  }

  // Let any page open Studio directly (e.g. the Command Hub Site tab hint link).
  window.__ragnarOpenStudio = () => { initStudio(); document.getElementById("fab-studio")?.click(); };
})();
