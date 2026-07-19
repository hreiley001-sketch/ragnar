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

  // Reflect signed-in state + notifications bell
  fetch("/api/auth/me").then((r) => r.json()).then((d) => {
    if (d && d.user) {
      userLine.hidden = false;
      userLine.textContent = "Signed in · " + (d.user.name || d.user.email);
      acct.querySelector(".lbl").textContent = "My account";
      acct.href = "/account";
      if (d.user.is_staff) hub.querySelector(".lbl").textContent = "Command Hub (staff)";

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
    }
  }).catch(() => {});
})();
