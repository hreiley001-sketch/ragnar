// RAGNAR — Gods of the realms.
// Injects a faint background patron statue per page and builds the Pantheon wall.
// Real art: drop a transparent-background PNG at /static/gods/<key>.png
// (odin/thor/freyr/tyr/loki/heimdall). Until then a carved silhouette stands in.
"use strict";
(function () {
  const path = (location.pathname.replace(/\/+$/, "") || "/");
  const onHome = path === "/" || document.body.classList.contains("arena-home");

  const GODS = [
    { key: "freyr", god: "Freyr", title: "Lord of Plenty",        realm: "Marketplace",     rc: "#c8901f", rune: "ᚠ", paths: ["/marketplace"] },
    { key: "thor",  god: "Thor",  title: "Thunder of the Break",  realm: "Live Rooms",      rc: "#2f93c4", rune: "ᚦ", paths: ["/live", "/rides", "/ride"] },
    { key: "tyr",   god: "Týr",   title: "Binder of Oaths",       realm: "Groups",          rc: "#2f8f6b", rune: "ᛏ", paths: ["/groups", "/group"] },
    { key: "loki",  god: "Loki",  title: "Teller of Tales",       realm: "The Feed",        rc: "#7a5cc4", rune: "ᛚ", paths: ["/feed"] },
    { key: "heimdall", god: "Heimdall", title: "Warden of the Halls", realm: "Stores & Halls", rc: "#1f8f9a", rune: "ᛗ", paths: ["/stores", "/store", "/mystore"] },
    { key: "odin",  god: "Odin",  title: "The All-Father",        realm: "Command Hub",     rc: "#a67c1a", rune: "ᛟ", paths: ["/admin", "/account", "/notifications", "/support", "/login", "/verify"] }
  ];
  const ODIN = GODS.find((g) => g.key === "odin");
  function patronFor(p) {
    for (const g of GODS) { if (g.paths.some((x) => p === x || p.startsWith(x + "/"))) return g; }
    return ODIN;
  }

  // Carved-silhouette fallback (shown until real art is added). Bold near-black
  // figure; the realm glow is applied by CSS drop-shadow.
  const INK = "#0a0d0c";
  function fallbackSVG(g) {
    return `<svg viewBox="0 0 240 320" role="img" aria-label="Statue of ${g.god}">
      <g fill="${INK}">
        <line x1="196" y1="46" x2="196" y2="292" stroke="${INK}" stroke-width="7" stroke-linecap="round"/>
        <path d="M196 30 L206 52 L196 66 L186 52 Z"/>
        <path d="M120 96 C74 104 50 150 46 300 L194 300 C190 150 166 104 120 96 Z"/>
        <path d="M120 108 C92 112 82 138 84 176 L156 176 C158 138 148 112 120 108 Z"/>
        <path d="M120 58 C104 58 92 70 92 88 C92 108 104 120 120 120 C136 120 148 108 148 88 C148 70 136 58 120 58 Z"/>
        <path d="M82 84 C102 66 138 66 158 84 C140 96 100 96 82 84 Z"/>
        <path d="M97 84 C105 58 135 58 143 84 Z"/>
        <path d="M100 104 C104 168 136 168 140 104 C134 138 106 138 100 104 Z"/>
      </g>
      <circle cx="108" cy="92" r="4" fill="#fff"/>
    </svg>`;
  }
  // <img> that reveals the silhouette if the PNG isn't there yet.
  function figureHTML(g) {
    return `<span class="god-figure">${fallbackSVG(g)}<img src="/static/gods/${g.key}.png" alt="${g.god}, ${g.realm}"
      loading="lazy" decoding="async"
      onload="this.previousElementSibling.style.display='none'"
      onerror="this.remove()" /></span>`;
  }

  // ---- Background patron (every page except the home vault) ----
  if (!onHome && !document.querySelector(".realm-patron")) {
    const g = patronFor(path);
    const el = document.createElement("div");
    el.className = "realm-patron"; el.setAttribute("aria-hidden", "true");
    el.style.setProperty("--rc", g.rc);
    el.innerHTML = `<span class="rp-glow"></span><span class="rp-fig">${figureHTML(g)}</span>`;
    document.body.appendChild(el);
  }

  // ---- Pantheon wall (fills #pantheonWall if present) ----
  function buildPantheon(host) {
    if (!host) return;
    host.innerHTML = GODS.map((g) => `
      <a class="god-shrine" style="--rc:${g.rc}" href="${g.paths[0]}" aria-label="${g.god} — ${g.realm}">
        <div class="altar"><span class="halo"></span><span class="rays"></span>
          <span class="runemark">${g.rune}</span>${figureHTML(g)}</div>
        <div class="plate"><div class="nm">${g.god}</div><div class="ti">${g.title} · ${g.realm}</div></div>
      </a>`).join("");
  }
  window.RagnarGods = { list: GODS, buildPantheon };

  const host = document.getElementById("pantheonWall");
  if (host) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => buildPantheon(host));
    else buildPantheon(host);
  }
})();
