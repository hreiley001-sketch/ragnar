// RAGNAR — Realm riches.
// Per-page Asgard color, gems, and runic glow — no statues, no gate cards.
// Gems are the pops of color in the Asgard atmosphere.
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

  function gemHTML(g, i) {
    const tone = i % 3 === 0 ? g.jewel : i % 3 === 1 ? g.jewel2 : g.rcSoft;
    const kinds = ["rj-diamond", "rj-round", "rj-facet", "rj-ember", "rj-teardrop", "rj-cluster"];
    const size = i % 7 === 0 ? "rj-lg" : i % 5 === 0 ? "rj-sm" : "";
    return `<span class="rj ${kinds[i % kinds.length]} ${size} rj-${i}" style="--j:${tone};--rc:${g.rc};--jewel-2:${g.jewel2};--rc-deep:${g.rcDeep};--rc-soft:${g.rcSoft}"></span>`;
  }

  function injectRealmRiches(g, multi) {
    if (document.querySelector(".realm-jewels")) return;
    const el = document.createElement("div");
    el.className = "realm-jewels" + (multi ? " realm-jewels--pantheon" : " realm-jewels--realm");
    el.setAttribute("aria-hidden", "true");

    const gods = multi ? GODS : [g, g, g, g];
    const count = multi ? 36 : 24;
    const gems = [];
    for (let i = 0; i < count; i++) gems.push(gemHTML(gods[i % gods.length], i));

    const runes = multi
      ? GODS.map((x, i) => `<span class="realm-rune-glow rr-${i}" style="--rc:${x.rc};--jewel:${x.jewel}">${x.rune}</span>`).join("")
      : [0, 1, 2, 3, 4, 5].map((i) => `<span class="realm-rune-glow rr-${i}">${g.rune}</span>`).join("");

    // Soft ambient pools only — gems carry the color pops
    const pools = multi
      ? GODS.map((x, i) => `<span class="realm-color-pool pool-${i}" style="--rc:${x.rc};--jewel:${x.jewel};--jewel-2:${x.jewel2}"></span>`).join("")
      : `<span class="realm-color-pool pool-0"></span>
         <span class="realm-color-pool pool-1" style="--rc:var(--jewel-2);--jewel:var(--rc-soft)"></span>
         <span class="realm-color-pool pool-3"></span>`;

    el.innerHTML = `
      <div class="realm-color-fill"></div>
      <div class="realm-gold-vein vein-a"></div>
      <div class="realm-gold-vein vein-b"></div>
      <div class="realm-treasure-glow"></div>
      ${pools}
      <div class="realm-norse-ring ring-a"></div>
      <div class="realm-norse-ring ring-b"></div>
      ${gems.join("")}
      ${runes}
      <span class="realm-ember e1"></span><span class="realm-ember e2"></span>
      <span class="realm-ember e3"></span><span class="realm-ember e4"></span>
      <span class="realm-ember e5"></span><span class="realm-ember e6"></span>`;

    // Home: nest in vault-env (above haze) so gems read as clear color pops
    const vaultEnv = multi && document.getElementById("vaultEnv");
    if (vaultEnv) {
      el.classList.add("realm-jewels--in-vault");
      vaultEnv.appendChild(el);
    } else {
      document.body.appendChild(el);
    }
  }

  // Home: all-realm treasure wash — gems are the color language
  if (onHome) {
    document.body.dataset.patron = "pantheon";
    const mount = () => injectRealmRiches(ODIN, true);
    if (document.getElementById("vaultEnv") || document.readyState !== "loading") mount();
    else document.addEventListener("DOMContentLoaded", mount);
  }

  // Realm pages: patron color + riches (no statues, no gate cards)
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
