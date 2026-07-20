// RAGNAR — shared hamburger navigation, site header, and chat-widget factory.
// Injected on every page for one consistent header/menu, plus the assistants
// (Concierge/Studio) that are built on the same shared chat component.
"use strict";
(function () {
  const path = (location.pathname.replace(/\/+$/, "") || "/");
  const pageMain = document.querySelector("main");
  if (pageMain && !document.querySelector(".arena-skip, .site-skip")) {
    if (!pageMain.id) pageMain.id = "main";
    const skip = document.createElement("a");
    skip.className = "site-skip";
    skip.href = `#${pageMain.id}`;
    skip.textContent = "Skip to content";
    document.body.insertBefore(skip, document.body.firstChild);
  }

  const ITEMS = [
    { icon: "01", label: "Home", href: "/" },
    { icon: "02", label: "Marketplace", href: "/marketplace" },
    { icon: "03", label: "Live Sellers", href: "/stores" },
    { icon: "04", label: "Live Rooms", href: "/rides" },
    { icon: "05", label: "Counsel", href: "/support" },
    { icon: "06", label: "Sell on RAGNAR", href: "/#apply" },
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
      return `<span id="viewers" class="status-badge">0 watching</span>`;
    }
    if (path === "/account") {
      return `<button id="logoutBtn" class="btn btn-ghost btn-sm" type="button">Log out</button>`;
    }
    return "";
  }
  function buildHeader() {
    const header = document.getElementById("siteHeader");
    if (!header) return;
    header.className = "site-header";
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
        <a class="btn btn-ghost btn-sm" href="/stores">Stores</a>
        <button class="btn btn-primary btn-sm" type="button" data-open-sell>Sell</button>
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
  drawer.id = "navDrawer";
  drawer.setAttribute("role", "dialog");
  drawer.setAttribute("aria-modal", "true");
  drawer.setAttribute("aria-label", "Site navigation");
  drawer.setAttribute("aria-hidden", "true");
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
  const acct = navLink({ icon: "ID", label: "Sign in", href: "/login" }); links.appendChild(acct);
  acctLinks.push(acct);
  // Command Hub is staff-only — hidden until we confirm the user is staff.
  const hub = navLink({ icon: "//", label: "Command Hub", href: "/admin", cls: "nav-hub" }); hub.hidden = true; links.appendChild(hub);

  document.body.appendChild(scrim);
  document.body.appendChild(drawer);

  // Burger button — into the header if present, else a floating button.
  const burger = mk("button", "nav-burger");
  burger.innerHTML = '<span aria-hidden="true">☰</span>';
  burger.setAttribute("aria-label", "Open menu");
  burger.setAttribute("aria-controls", "navDrawer");
  burger.setAttribute("aria-expanded", "false");
  const actions = document.querySelector(".header-actions");
  if (actions) actions.appendChild(burger);
  else { Object.assign(burger.style, { position: "fixed", top: "14px", right: "14px", zIndex: "82" }); document.body.appendChild(burger); }

  const open = () => {
    scrim.classList.add("open");
    drawer.classList.add("open");
    drawer.setAttribute("aria-hidden", "false");
    burger.setAttribute("aria-expanded", "true");
    drawer.querySelector(".nav-close").focus();
  };
  const close = () => {
    if (!drawer.classList.contains("open")) return;
    scrim.classList.remove("open");
    drawer.classList.remove("open");
    drawer.setAttribute("aria-hidden", "true");
    burger.setAttribute("aria-expanded", "false");
    burger.focus();
  };
  burger.addEventListener("click", open);
  scrim.addEventListener("click", close);
  drawer.querySelector(".nav-close").addEventListener("click", close);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
    if (e.key !== "Tab" || !drawer.classList.contains("open")) return;
    const focusable = [...drawer.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])')].filter((el) => !el.hidden);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

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
  loadWebFont("Inter Tight");
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
  function readableOn(hex) {
    const m = /^#([0-9a-fA-F]{6})$/.exec(hex || "");
    if (!m) return "#061016";
    const n = parseInt(m[1], 16);
    const channels = [n >> 16, (n >> 8) & 255, n & 255].map((v) => {
      const c = v / 255;
      return c <= .03928 ? c / 12.92 : Math.pow((c + .055) / 1.055, 2.4);
    });
    return (.2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2]) > .42
      ? "#061016"
      : "#f6f8fa";
  }
  function applyTheme(c) {
    if (!c) return;
    const s = document.documentElement.style;
    if (c.theme_accent) {
      const strong = shade(c.theme_accent, 22);
      s.setProperty("--color-accent-primary", c.theme_accent);
      s.setProperty("--color-accent-primary-strong", strong);
      s.setProperty("--color-on-accent", readableOn(c.theme_accent));
      s.setProperty("--ice", c.theme_accent);
      s.setProperty("--ice-strong", strong);
    }
    if (c.theme_gold) {
      s.setProperty("--color-accent-secondary", c.theme_gold);
      s.setProperty("--gold", c.theme_gold);
    }
    if (c.theme_bg) {
      const elevated = shade(c.theme_bg, 12);
      const panel = shade(c.theme_bg, 18);
      s.setProperty("--color-bg-base", c.theme_bg);
      s.setProperty("--color-bg-elevated", elevated);
      s.setProperty("--color-bg-panel", panel);
      s.setProperty("--bg", c.theme_bg);
      s.setProperty("--bg-2", elevated);
      s.setProperty("--panel-solid", panel);
    }
    if (c.theme_text) {
      s.setProperty("--color-text-primary", c.theme_text);
      s.setProperty("--color-text-secondary", shade(c.theme_text, 34));
      s.setProperty("--text", c.theme_text);
      s.setProperty("--text-soft", shade(c.theme_text, 34));
    }
    if (c.theme_font) { loadWebFont(c.theme_font); document.body.style.fontFamily = "'" + c.theme_font + "', system-ui, sans-serif"; }
  }
  function applyAnnouncement(c) {
    let bar = document.getElementById("navAnnounce");
    const msg = c && c.announcement;
    if (!msg) { if (bar) bar.remove(); return; }
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "navAnnounce";
      bar.className = "site-announce";
      document.body.insertBefore(bar, document.body.firstChild);
    }
    bar.innerHTML = c.announcement_link
      ? `<a href="${c.announcement_link}" class="site-announce-link">${msg}</a>`
      : msg;
  }
  function applyContent(c) {
    // Landing-page copy, if present on this page.
    if (c.hero_headline && document.getElementById("heroHeadline")) document.getElementById("heroHeadline").textContent = c.hero_headline;
    if (c.hero_subtitle && document.getElementById("heroSubtitle")) document.getElementById("heroSubtitle").textContent = c.hero_subtitle;
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
        bar.className = "verify-email-bar";
        bar.innerHTML = 'Verify your email to unlock full access. <a href="#" id="navResend">Resend link</a> <button id="navVdismiss" type="button" aria-label="Dismiss verification reminder">Close</button>';
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

  // Ensure Counsel design tokens load on every page (floating widget).
  (function loadCounselCss() {
    if (document.getElementById("counsel-css")) return;
    const l = document.createElement("link");
    l.id = "counsel-css";
    l.rel = "stylesheet";
    l.href = "/static/support.css";
    document.head.appendChild(l);
  })();

  // ---- Shared chat-widget factory: builds a FAB + slide-up panel with a
  // feed/chips/input, used by Concierge, Studio, and (via window.__ragnarChat)
  // the seller-facing Store Designer. One visual language, one place to tweak it. ----
  const escHtml = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function createChatWidget(opts) {
    const { key, icon, label, gold, publish, footNote, headSub, fabHtml, expandHref } = opts;
    const fab = mk("button", "chat-fab" + (gold ? " chat-fab-gold" : ""));
    fab.innerHTML = fabHtml || `${icon} ${label}`;
    fab.id = "fab-" + key;
    fab.setAttribute("aria-label", label);

    const panel = mk("div", "chat-panel");
    panel.id = "panel-" + key;
    panel.innerHTML = `
      <div class="chat-head">
        <div class="chat-head-title">${icon} ${label}${headSub ? `<span class="sub">${escHtml(headSub)}</span>` : ""}</div>
        <button class="chat-close" aria-label="Close">✕</button>
      </div>
      <div class="chat-feed"></div>
      <div class="chat-chips"></div>
      <div class="chat-input-row">
        <input placeholder="${footNote ? escHtml(footNote) : "Type a message…"}" />
        <button class="chat-send" type="button">➤</button>
      </div>
      ${expandHref ? `<a class="chat-expand" href="${escHtml(expandHref)}">Open full Counsel →</a>` : ""}
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
      open: () => { if (!panel.classList.contains("open")) toggle(); },
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
    const w = createChatWidget({ key: "concierge", icon: "R", label: "Ask RAGNAR", footNote: "What are you hunting for?" });

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
    const w = createChatWidget({ key: "studio", icon: "//", label: "Studio", gold: true, publish: true, footNote: "Tell me how to sculpt the site…" });

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

  // ---- RAGNAR Counsel: AI Support OS floating portal.
  // Full chamber lives at /support; this is the always-on entry. ----
  let supportBuilt = false;
  let supportConvId = localStorage.getItem("ragnar_support_id") || null;
  function supportReceipt(workflow) {
    if (!workflow) return "";
    const decision = workflow.decision || (workflow.policy && workflow.policy.decision);
    const order = workflow.order || {};
    const refund = workflow.refund || {};
    const bits = [];
    if (decision) bits.push(`<div class="cx-receipt-row"><span>Decision</span><strong>${escHtml(decision)}</strong></div>`);
    if (order.id) bits.push(`<div class="cx-receipt-row"><span>Order</span><strong>#${escHtml(order.id)}</strong></div>`);
    if (refund.amount != null) bits.push(`<div class="cx-receipt-row"><span>Refund</span><strong>$${Number(refund.amount).toFixed(2)}</strong></div>`);
    if (!bits.length) return "";
    return `<div class="cx-receipt"><div class="cx-receipt-label">Action record</div><div class="cx-receipt-rows">${bits.join("")}</div></div>`;
  }
  function initSupport() {
    if (supportBuilt) return;
    if ((location.pathname.replace(/\/+$/, "") || "/") === "/support") return; // full page owns UX
    supportBuilt = true;
    const w = createChatWidget({
      key: "support",
      icon: "R",
      label: "Counsel",
      headSub: "Guided resolution",
      footNote: "Order #, refund, return, tracking…",
      expandHref: "/support",
      fabHtml: `<span class="fab-crest">R</span><span class="fab-copy"><b>Counsel</b><small>Support</small></span>`,
    });
    w.fab.classList.add("chat-fab-support");
    w.panel.classList.add("chat-panel-support");

    async function ensureConv() {
      if (supportConvId) {
        try {
          const c = await fetch(`/api/support/conversations/${encodeURIComponent(supportConvId)}`)
            .then((r) => { if (!r.ok) throw new Error("gone"); return r.json(); });
          return c;
        } catch (_) { supportConvId = null; localStorage.removeItem("ragnar_support_id"); }
      }
      const c = await fetch("/api/support/conversations", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel: "web" }),
      }).then((r) => r.json());
      supportConvId = c.id;
      localStorage.setItem("ragnar_support_id", supportConvId);
      return c;
    }

    w.onFirstOpen(async () => {
      try {
        const c = await ensureConv();
        (c.messages || []).forEach((m) => {
          if (m.role === "user") w.msg(escHtml(m.body), "me");
          else w.msg(escHtml(m.body));
        });
        if (!(c.messages || []).length) {
          w.msg(escHtml(c.reply || "Counsel is ready — refunds, returns, tracking."));
        }
        w.chips(c.chips || ["Track my order", "I need a refund", "How do fees work?", "Talk to a human"]);
      } catch (_) {
        w.msg("Counsel is warming up — try again in a moment.");
      }
    });

    w.onSend(async () => {
      const text = w.input.value.trim();
      if (!text) return;
      w.input.value = "";
      w.msg(escHtml(text), "me");
      const thinking = w.msg('<span class="cx-typing" aria-label="Thinking"><span></span><span></span><span></span></span>');
      try {
        await ensureConv();
        const r = await fetch("/api/support/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, conversation_id: supportConvId }),
        }).then((x) => x.json());
        thinking.remove();
        if (r.id) {
          supportConvId = r.id;
          localStorage.setItem("ragnar_support_id", supportConvId);
        }
        w.msg(escHtml(r.reply || "Done.") + supportReceipt(r.workflow));
        if (r.chips) w.chips(r.chips);
        if (r.queue || r.decision === "escalate") {
          w.msg(`<span class="chat-note">Case ${escHtml(r.conversation_id || supportConvId)} — human review queue.</span>`);
        }
      } catch (e) {
        thinking.remove();
        w.msg("Something went wrong — try again, or open full Counsel.");
      }
    });

    window.__ragnarOpenCounsel = () => { w.open(); };
  }
  initSupport();
})();
