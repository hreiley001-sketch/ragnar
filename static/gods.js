// RAGNAR — Realm riches.
// Per-page Asgard color + found gem clusters — no statues, no gate cards.
// Gems sit in tight treasure caches, not a random float field.
"use strict";
(function () {
  const path = (location.pathname.replace(/\/+$/, "") || "/");
  const onHome = path === "/" || document.body.classList.contains("arena-home");

  const GODS = [
    { key: "freyr", god: "Freyr", title: "Lord of Plenty",        realm: "Marketplace",
      rc: "#c8901f", rcDeep: "#8a6210", rcSoft: "#e8c46a", jewel: "#f0d878", jewel2: "#7ec8a0", rune: "ᚠ",
      paths: ["/marketplace"] },
    { key: "thor",  god: "Thor",  title: "Thunder of the Break",  realm: "Live Rooms",
      rc: "#2f93c4", rcDeep: "#1a6288", rcSoft: "#7ec8e8", jewel: "#5eb8e0", jewel2: "#f0c040", rune: "ᚦ",
      paths: ["/live", "/rides", "/ride"] },
    { key: "tyr",   god: "Týr",   title: "Binder of Oaths",       realm: "Groups",
      rc: "#2f8f6b", rcDeep: "#1a5c45", rcSoft: "#6ec4a0", jewel: "#4db88a", jewel2: "#d4a84a", rune: "ᛏ",
      paths: ["/groups", "/group"] },
    { key: "loki",  god: "Loki",  title: "Teller of Tales",       realm: "The Feed",
      rc: "#7a5cc4", rcDeep: "#4e3488", rcSoft: "#b49ae8", jewel: "#c070e0", jewel2: "#e87850", rune: "ᛚ",
      paths: ["/feed"] },
    { key: "heimdall", god: "Heimdall", title: "Warden of the Halls", realm: "Stores & Halls",
      rc: "#1f8f9a", rcDeep: "#116068", rcSoft: "#6ec8d0", jewel: "#40d0c8", jewel2: "#e8a840", rune: "ᚺ",
      paths: ["/stores", "/store", "/mystore"] },
    { key: "odin",  god: "Odin",  title: "The All-Father",        realm: "Command Hub",
      rc: "#a67c1a", rcDeep: "#6d5010", rcSoft: "#d4b050", jewel: "#e8c050", jewel2: "#7088c0", rune: "ᛟ",
      paths: ["/admin", "/account", "/notifications", "/support", "/login", "/verify"] }
  ];
  const ODIN = GODS.find((g) => g.key === "odin");
  function patronFor(p) {
    for (const g of GODS) { if (g.paths.some((x) => p === x || p.startsWith(x + "/"))) return g; }
    return ODIN;
  }

  function applyRealmTheme(g) {
    const root = document.documentElement;
    const body = document.body;
    body.dataset.patron = g.key;
    root.style.setProperty("--rc", g.rc);
    root.style.setProperty("--rc-deep", g.rcDeep);
    root.style.setProperty("--rc-soft", g.rcSoft);
    root.style.setProperty("--jewel", g.jewel);
    root.style.setProperty("--jewel-2", g.jewel2);
    root.style.setProperty("--patron-rune", `"${g.rune}"`);
    root.style.setProperty("--color-accent-primary", g.rcDeep);
    root.style.setProperty("--color-accent-primary-strong", g.rc);
    root.style.setProperty("--color-accent-gold", g.rc);
    root.style.setProperty("--color-accent-gold-strong", g.rcSoft);
    root.style.setProperty("--color-crystal", g.rcDeep);
    root.style.setProperty("--color-border-gold", `color-mix(in srgb, ${g.rc} 55%, transparent)`);
    root.style.setProperty("--color-hover-surface", `color-mix(in srgb, ${g.rc} 14%, transparent)`);
    root.style.setProperty("--color-active-surface", `color-mix(in srgb, ${g.rc} 20%, transparent)`);
  }

  // Local offsets inside a found cluster (tight pile, not a scatter)
  const CLUSTER_LAYOUTS = [
    [
      { x: 0, y: 0, kind: "diamond", size: "lg" },
      { x: 18, y: -10, kind: "round", size: "" },
      { x: -16, y: 12, kind: "teardrop", size: "" },
      { x: 14, y: 16, kind: "ember", size: "sm" },
      { x: -20, y: -8, kind: "facet", size: "sm" },
      { x: 4, y: -20, kind: "ember", size: "sm" }
    ],
    [
      { x: 0, y: 2, kind: "round", size: "lg" },
      { x: -14, y: -12, kind: "diamond", size: "" },
      { x: 16, y: -8, kind: "facet", size: "" },
      { x: 12, y: 14, kind: "teardrop", size: "sm" },
      { x: -18, y: 10, kind: "ember", size: "sm" }
    ],
    [
      { x: 2, y: 0, kind: "facet", size: "lg" },
      { x: -12, y: 14, kind: "round", size: "" },
      { x: 18, y: 8, kind: "diamond", size: "" },
      { x: -16, y: -10, kind: "ember", size: "sm" },
      { x: 8, y: -16, kind: "teardrop", size: "sm" },
      { x: 22, y: -6, kind: "ember", size: "sm" }
    ],
    [
      { x: 0, y: -2, kind: "teardrop", size: "lg" },
      { x: 16, y: 10, kind: "round", size: "" },
      { x: -18, y: 6, kind: "diamond", size: "" },
      { x: 10, y: -14, kind: "facet", size: "sm" },
      { x: -8, y: 16, kind: "ember", size: "sm" }
    ]
  ];

  // Home: six found caches — one per patron palette, parked at hall edges
  const HOME_CACHES = [
    { left: "7%",  top: "18%", god: 0, layout: 0, delay: "0s" },
    { left: "88%", top: "16%", god: 1, layout: 1, delay: "-1.2s" },
    { left: "10%", top: "72%", god: 2, layout: 2, delay: "-2.4s" },
    { left: "86%", top: "68%", god: 3, layout: 3, delay: "-3.1s" },
    { left: "78%", top: "38%", god: 4, layout: 0, delay: "-4s" },
    { left: "18%", top: "42%", god: 5, layout: 1, delay: "-5s" }
  ];

  // Realm pages: three caches in the patron's palette
  const REALM_CACHES = [
    { left: "8%",  top: "22%", layout: 0, delay: "0s" },
    { left: "86%", top: "28%", layout: 2, delay: "-2s" },
    { left: "72%", top: "74%", layout: 1, delay: "-3.5s" },
    { left: "14%", top: "70%", layout: 3, delay: "-1.4s" }
  ];

  function gemSpan(g, spot, i) {
    const tone = i % 3 === 0 ? g.jewel : i % 3 === 1 ? g.jewel2 : g.rcSoft;
    const sizeClass = spot.size === "lg" ? "rj-lg" : spot.size === "sm" ? "rj-sm" : "";
    return `<span class="rj rj-${spot.kind} ${sizeClass}" style="--ox:${spot.x}px;--oy:${spot.y}px;--j:${tone};--rc:${g.rc};--jewel-2:${g.jewel2};--rc-deep:${g.rcDeep};--rc-soft:${g.rcSoft};--d:${i * 0.18}s"></span>`;
  }

  function buildCache(g, cache, idx) {
    const layout = CLUSTER_LAYOUTS[cache.layout % CLUSTER_LAYOUTS.length];
    const gems = layout.map((spot, i) => gemSpan(g, spot, i)).join("");
    return `<div class="gem-cache gem-cache-${idx}" style="left:${cache.left};top:${cache.top};--rc:${g.rc};--jewel:${g.jewel};--jewel-2:${g.jewel2};--rc-soft:${g.rcSoft};--cache-delay:${cache.delay}">
      <span class="gem-cache-glow"></span>
      <span class="gem-cache-base"></span>
      ${gems}
    </div>`;
  }

  function injectRealmRiches(g, multi) {
    if (document.querySelector(".realm-jewels")) return;
    const el = document.createElement("div");
    el.className = "realm-jewels" + (multi ? " realm-jewels--pantheon" : " realm-jewels--realm");
    el.setAttribute("aria-hidden", "true");

    const caches = multi
      ? HOME_CACHES.map((c, i) => buildCache(GODS[c.god], c, i)).join("")
      : REALM_CACHES.map((c, i) => buildCache(g, c, i)).join("");

    const runes = multi
      ? GODS.map((x, i) => `<span class="realm-rune-glow rr-${i}" style="--rc:${x.rc};--jewel:${x.jewel}">${x.rune}</span>`).join("")
      : [0, 1, 2].map((i) => `<span class="realm-rune-glow rr-${i}">${g.rune}</span>`).join("");

    const pools = multi
      ? GODS.slice(0, 4).map((x, i) => `<span class="realm-color-pool pool-${i}" style="--rc:${x.rc};--jewel:${x.jewel};--jewel-2:${x.jewel2}"></span>`).join("")
      : `<span class="realm-color-pool pool-0"></span>
         <span class="realm-color-pool pool-1" style="--rc:var(--jewel-2);--jewel:var(--rc-soft)"></span>`;

    el.innerHTML = `
      <div class="realm-color-fill"></div>
      <div class="realm-gold-vein vein-a"></div>
      <div class="realm-gold-vein vein-b"></div>
      <div class="realm-treasure-glow"></div>
      ${pools}
      <div class="realm-norse-ring ring-a"></div>
      <div class="realm-norse-ring ring-b"></div>
      ${caches}
      ${runes}`;

    const vaultEnv = multi && document.getElementById("vaultEnv");
    if (vaultEnv) {
      el.classList.add("realm-jewels--in-vault");
      vaultEnv.appendChild(el);
    } else {
      document.body.appendChild(el);
    }
  }

  if (onHome) {
    document.body.dataset.patron = "pantheon";
    const mount = () => injectRealmRiches(ODIN, true);
    if (document.getElementById("vaultEnv") || document.readyState !== "loading") mount();
    else document.addEventListener("DOMContentLoaded", mount);
  }

  if (!onHome) {
    const g = patronFor(path);
    applyRealmTheme(g);
    injectRealmRiches(g, false);
    if (!document.querySelector(".realm-bloom")) {
      const bloom = document.createElement("div");
      bloom.className = "realm-bloom";
      bloom.setAttribute("aria-hidden", "true");
      bloom.innerHTML = `<span class="rb-glow"></span><span class="rb-glow rb-glow-2"></span>`;
      document.body.appendChild(bloom);
    }
  }

  window.RagnarGods = { list: GODS, patronFor };
})();
