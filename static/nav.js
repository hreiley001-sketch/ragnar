// RAGNAR — shared hamburger navigation. Injected on every page for one
// consistent menu, including the behind-the-scenes Command Hub.
"use strict";
(function () {
  const path = (location.pathname.replace(/\/+$/, "") || "/");

  const ITEMS = [
    { icon: "🏠", label: "Home", href: "/" },
    { icon: "🛒", label: "Marketplace", href: "/marketplace" },
    { icon: "🏪", label: "Stores & Live", href: "/stores" },
    { icon: "🎢", label: "Live Rides", href: "/rides" },
    { icon: "🔎", label: "Want Lists", href: "/account#wants" },
    { icon: "⭐", label: "Become a Founding Seller", href: "/#apply" },
  ];

  const mk = (tag, cls) => { const e = document.createElement(tag); if (cls) e.className = cls; return e; };
  function navLink(it) {
    const a = document.createElement("a");
    a.className = "nav-link" + (it.cls ? " " + it.cls : "");
    a.href = it.href;
    a.innerHTML = `<span class="ico">${it.icon}</span><span class="lbl">${it.label}</span>`;
    return a;
  }

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
  const hub = navLink({ icon: "⚙️", label: "Command Hub", href: "/admin", cls: "nav-hub" }); links.appendChild(hub);

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
      acct.querySelector(".lbl").textContent = "My account";
      acct.href = "/account";
      if (d.user.is_staff) { hub.querySelector(".lbl").textContent = "Command Hub (staff)"; initStudio(); }
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
    const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

    const fab = mk("button", "concierge-fab");
    fab.innerHTML = "💬 Ask RAGNAR";
    fab.style.cssText = "position:fixed;right:18px;bottom:18px;z-index:90;border:1px solid var(--border-strong,#4a6);background:linear-gradient(135deg,#101826,#0a0f16);color:var(--ice,#6fd6ff);font-weight:700;font-size:13px;padding:11px 16px;border-radius:999px;cursor:pointer;box-shadow:0 10px 30px rgba(0,0,0,.5);";

    const panel = mk("div", "concierge-panel");
    panel.style.cssText = "position:fixed;right:18px;bottom:70px;z-index:91;width:min(370px,calc(100vw - 36px));height:min(540px,calc(100vh - 120px));display:none;flex-direction:column;background:var(--panel-solid,#121a26);border:1px solid var(--border-strong,#345);border-radius:16px;box-shadow:0 24px 70px rgba(0,0,0,.6);overflow:hidden;";
    panel.innerHTML = `
      <div style="padding:12px 14px;border-bottom:1px solid var(--border,#234);display:flex;align-items:center;justify-content:space-between;">
        <div style="font-weight:700;color:var(--ice,#6fd6ff);">💬 RAGNAR Concierge</div>
        <button id="cgClose" style="background:none;border:none;color:var(--muted,#89a);cursor:pointer;font-size:16px;">✕</button>
      </div>
      <div id="cgFeed" style="flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;font-size:13.5px;line-height:1.5;"></div>
      <div id="cgChips" style="padding:0 12px 8px;display:flex;flex-wrap:wrap;gap:6px;"></div>
      <div style="padding:10px 12px;border-top:1px solid var(--border,#234);display:flex;gap:8px;">
        <input id="cgInput" placeholder="What are you hunting for?" style="flex:1;background:var(--bg,#0a0f16);border:1px solid var(--border,#234);border-radius:10px;color:var(--text,#dfe8f2);padding:9px 11px;font-size:13px;" />
        <button id="cgSend" style="background:var(--ice,#6fd6ff);color:#04121c;border:none;border-radius:10px;font-weight:700;padding:0 14px;cursor:pointer;">➤</button>
      </div>`;

    document.body.appendChild(fab);
    document.body.appendChild(panel);
    const feed = panel.querySelector("#cgFeed");
    const chipsBox = panel.querySelector("#cgChips");
    const input = panel.querySelector("#cgInput");

    const msg = (html, who) => {
      const el = mk("div");
      el.style.cssText = who === "me"
        ? "align-self:flex-end;max-width:85%;background:var(--ice,#6fd6ff);color:#04121c;padding:8px 11px;border-radius:12px 12px 2px 12px;"
        : "align-self:flex-start;max-width:90%;background:var(--bg,#0a0f16);border:1px solid var(--border,#234);padding:8px 11px;border-radius:12px 12px 12px 2px;";
      el.innerHTML = html;
      feed.appendChild(el); feed.scrollTop = feed.scrollHeight;
      return el;
    };
    const chips = (arr) => {
      chipsBox.innerHTML = "";
      arr.forEach((t) => {
        const c = mk("button");
        c.textContent = t;
        c.style.cssText = "background:rgba(111,214,255,.1);border:1px solid var(--border,#234);color:var(--ice,#6fd6ff);border-radius:999px;padding:5px 10px;font-size:11.5px;cursor:pointer;";
        c.addEventListener("click", () => { input.value = t; send(); });
        chipsBox.appendChild(c);
      });
    };

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

    async function send() {
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      msg(esc(text), "me");
      // 1) Personal look/UX request -> local-only restyle.
      if (PERSONAL_RE.test(text)) {
        const r = personalize(text);
        if (r) { msg(r, "ai"); return; }
      }
      // 2) Otherwise: shop by vibe -> NL search -> marketplace with filters.
      const thinking = msg("Searching…", "ai");
      try {
        const r = await fetch(`/api/ai/search?q=${encodeURIComponent(text)}`).then((x) => x.json());
        thinking.remove();
        const f = r.filters || {};
        const p = new URLSearchParams();
        Object.entries(f).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") p.set(k, v); });
        const bits = [f.q, f.grading_company, f.category].filter(Boolean).join(" ");
        msg(`Hunting for ${esc(bits || text)} — taking you to the results…`, "ai");
        setTimeout(() => { location.href = "/marketplace?" + p.toString(); }, 700);
      } catch (e) { thinking.remove(); msg("Couldn't search just now — try again.", "ai"); }
    }

    fab.addEventListener("click", () => {
      const open = panel.style.display === "flex";
      panel.style.display = open ? "none" : "flex";
      if (!open && !feed.children.length) {
        msg("Hey! Tell me what you're after — a card, a player, a vibe — and I'll find it. I can also restyle your view just for you. 🐺", "ai");
        chips(["Vintage Charizard grails", "Cheap graded rookies under $50", "A gift for a Lakers fan", "Make my view dark & cozy"]);
      }
    });
    panel.querySelector("#cgClose").addEventListener("click", () => { panel.style.display = "none"; });
    panel.querySelector("#cgSend").addEventListener("click", send);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
  }

  // ---- RAGNAR Studio: a floating AI assistant for staff to sculpt the whole
  // site (look + copy) in plain English. Preview live, publish in one tap. ----
  let studioBuilt = false;
  function initStudio() {
    if (studioBuilt) return;
    studioBuilt = true;
    const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const pending = {};            // accumulated updates not yet published

    const launcher = mk("button", "studio-fab");
    launcher.innerHTML = "✨ Studio";
    launcher.style.cssText = "position:fixed;right:18px;bottom:18px;z-index:90;border:1px solid var(--border-strong,#4a6);background:linear-gradient(135deg,#101826,#0a0f16);color:var(--ice,#6fd6ff);font-weight:700;font-size:13px;padding:11px 16px;border-radius:999px;cursor:pointer;box-shadow:0 10px 30px rgba(0,0,0,.5);";

    const panel = mk("div", "studio-panel");
    panel.style.cssText = "position:fixed;right:18px;bottom:70px;z-index:91;width:min(380px,calc(100vw - 36px));height:min(560px,calc(100vh - 120px));display:none;flex-direction:column;background:var(--panel-solid,#121a26);border:1px solid var(--border-strong,#345);border-radius:16px;box-shadow:0 24px 70px rgba(0,0,0,.6);overflow:hidden;";
    panel.innerHTML = `
      <div style="padding:12px 14px;border-bottom:1px solid var(--border,#234);display:flex;align-items:center;justify-content:space-between;">
        <div style="font-weight:700;color:var(--ice,#6fd6ff);">✨ RAGNAR Studio</div>
        <button id="stClose" style="background:none;border:none;color:var(--muted,#89a);cursor:pointer;font-size:16px;">✕</button>
      </div>
      <div id="stFeed" style="flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;font-size:13.5px;line-height:1.5;"></div>
      <div id="stChips" style="padding:0 12px 8px;display:flex;flex-wrap:wrap;gap:6px;"></div>
      <div style="padding:10px 12px;border-top:1px solid var(--border,#234);">
        <div style="display:flex;gap:8px;">
          <input id="stInput" placeholder="Tell me how to sculpt the site…" style="flex:1;background:var(--bg,#0a0f16);border:1px solid var(--border,#234);border-radius:10px;color:var(--text,#dfe8f2);padding:9px 11px;font-size:13px;" />
          <button id="stSend" style="background:var(--ice,#6fd6ff);color:#04121c;border:none;border-radius:10px;font-weight:700;padding:0 14px;cursor:pointer;">➤</button>
        </div>
        <div style="display:flex;align-items:center;gap:10px;margin-top:8px;">
          <button id="stPublish" disabled style="flex:1;background:var(--gold,#f0c674);color:#0a0d12;border:none;border-radius:10px;font-weight:700;padding:9px;cursor:pointer;opacity:.5;">Publish live</button>
          <button id="stReset" style="background:none;border:1px solid var(--border,#234);color:var(--muted,#89a);border-radius:10px;padding:9px 12px;cursor:pointer;font-size:12px;">Revert</button>
        </div>
        <div id="stStatus" style="font-size:11.5px;color:var(--muted,#89a);margin-top:6px;min-height:14px;"></div>
      </div>`;

    document.body.appendChild(launcher);
    document.body.appendChild(panel);
    const feed = panel.querySelector("#stFeed");
    const chipsBox = panel.querySelector("#stChips");
    const input = panel.querySelector("#stInput");
    const publishBtn = panel.querySelector("#stPublish");
    const statusEl = panel.querySelector("#stStatus");

    const msg = (html, who) => {
      const el = mk("div");
      el.style.cssText = who === "me"
        ? "align-self:flex-end;max-width:85%;background:var(--ice,#6fd6ff);color:#04121c;padding:8px 11px;border-radius:12px 12px 2px 12px;"
        : "align-self:flex-start;max-width:90%;background:var(--bg,#0a0f16);border:1px solid var(--border,#234);padding:8px 11px;border-radius:12px 12px 12px 2px;";
      el.innerHTML = html;
      feed.appendChild(el); feed.scrollTop = feed.scrollHeight;
      return el;
    };
    const renderChips = (ideas) => {
      chipsBox.innerHTML = "";
      (ideas || []).forEach((idea) => {
        const c = mk("button");
        c.textContent = idea;
        c.style.cssText = "background:rgba(111,214,255,.1);border:1px solid var(--border,#234);color:var(--ice,#6fd6ff);border-radius:999px;padding:5px 10px;font-size:11.5px;cursor:pointer;";
        c.addEventListener("click", () => { input.value = idea; send(); });
        chipsBox.appendChild(c);
      });
    };
    const setPublish = () => {
      const n = Object.keys(pending).length;
      publishBtn.disabled = n === 0;
      publishBtn.style.opacity = n === 0 ? ".5" : "1";
      publishBtn.textContent = n === 0 ? "Publish live" : `Publish ${n} change${n === 1 ? "" : "s"}`;
    };

    async function send() {
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      msg(esc(text), "me");
      const thinking = msg("…", "ai");
      try {
        const r = await fetch("/api/admin/studio", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: text }) }).then((x) => x.json());
        thinking.remove();
        msg(esc(r.reply || "Done."), "ai");
        const keys = Object.keys(r.updates || {});
        if (keys.length) {
          Object.assign(pending, r.updates);
          // Live preview across the whole site.
          window.__ragnarApplySite(Object.assign({}, window.__ragnarSite, pending));
          msg(`<span style="color:var(--muted,#89a);font-size:12px;">Previewing: ${keys.map(esc).join(", ")} — Publish to make it live.</span>`, "ai");
          setPublish();
        }
        renderChips(r.ideas);
      } catch (e) { thinking.remove(); msg("Something went wrong — try again.", "ai"); }
    }

    async function publish() {
      if (!Object.keys(pending).length) return;
      statusEl.textContent = "Publishing…";
      try {
        const r = await fetch("/api/admin/site-config", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ updates: pending }) }).then((x) => x.json());
        window.__ragnarSite = r.config || window.__ragnarSite;
        for (const k in pending) delete pending[k];
        setPublish();
        statusEl.textContent = `Published live ✓ (by ${r.by || "you"})`;
        msg("Published — it's live on the site now. ✨", "ai");
      } catch (e) { statusEl.textContent = "Publish failed — check your access."; }
    }

    launcher.addEventListener("click", () => {
      const open = panel.style.display === "flex";
      panel.style.display = open ? "none" : "flex";
      if (!open && !feed.children.length) {
        msg("Hey — I'm your Studio assistant. Tell me the vibe and I'll sculpt the whole site: colors, font, announcement, landing copy. Big swings welcome. 🐺", "ai");
        renderChips(["Midnight forge: black + ember gold", "Icy, premium, minimal", "Announce our Friday live drop", "Bolder headline about beating eBay fees"]);
      }
    });
    panel.querySelector("#stClose").addEventListener("click", () => { panel.style.display = "none"; });
    panel.querySelector("#stSend").addEventListener("click", send);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
    publishBtn.addEventListener("click", publish);
    panel.querySelector("#stReset").addEventListener("click", () => {
      for (const k in pending) delete pending[k];
      window.__ragnarApplySite(window.__ragnarSite);   // restore last-published
      setPublish(); statusEl.textContent = "Reverted to the live version.";
    });
  }
})();
