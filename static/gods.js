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

  // Carved statue per god — a distinct near-black figure identified by helm,
  // weapon and companion. The realm glow is applied by CSS drop-shadow. Any real
  // PNG at /static/gods/<key>.png still auto-overrides these.
  const INK = "#0a0d0c";
  const CLOAK = `<path d="M120 100 C74 108 50 152 48 300 L192 300 C190 152 166 108 120 100 Z"/>`;
  const TORSO = `<path d="M120 112 C94 116 84 140 86 178 L154 178 C156 140 146 116 120 112 Z"/>`;
  const HEAD  = `<path d="M120 60 C104 60 92 72 92 90 C92 110 104 122 120 122 C136 122 148 110 148 90 C148 72 136 60 120 60 Z"/>`;
  const EYES  = `<circle cx="111" cy="92" r="3.4" fill="#fff"/><circle cx="129" cy="92" r="3.4" fill="#fff"/>`;
  const FIG = {
    // Odin — wide-brim hat, long beard, spear Gungnir, a raven on each shoulder, one eye
    odin: `<g fill="${INK}"><rect x="196" y="46" width="7" height="250" rx="3"/><path d="M199.5 30 L209 52 L199.5 66 L190 52 Z"/>${CLOAK}${TORSO}<path d="M46 150 C60 134 84 140 88 152 C76 152 66 158 60 168 C58 158 52 154 46 150 Z"/><path d="M194 150 C180 134 156 140 152 152 C164 152 174 158 180 168 C182 158 188 154 194 150 Z"/>${HEAD}<path d="M78 84 C102 62 138 62 162 84 C140 98 100 98 78 84 Z"/><path d="M96 84 C104 54 136 54 144 84 Z"/><path d="M100 106 C104 174 136 174 140 106 C134 140 106 140 100 106 Z"/></g><circle cx="109" cy="93" r="3.6" fill="#fff"/>`,
    // Thor — horned helm, braided beard, raised hammer Mjölnir
    thor: `<g fill="${INK}">${CLOAK}<path d="M120 168 C150 168 172 154 182 138" fill="none" stroke="${INK}" stroke-width="16" stroke-linecap="round"/><rect x="176" y="150" width="12" height="74" rx="4"/><rect x="156" y="118" width="52" height="36" rx="5"/>${TORSO}${HEAD}<path d="M92 84 C104 66 136 66 148 84 L148 76 C136 64 104 64 92 76 Z"/><path d="M92 80 C74 68 66 46 70 30 C88 44 94 64 98 78 Z"/><path d="M148 80 C166 68 174 46 170 30 C152 44 146 64 142 78 Z"/><path d="M98 108 C102 180 138 180 142 108 C134 150 106 150 98 108 Z"/></g>${EYES}`,
    // Freyr — circlet crown, short beard, sword, the boar Gullinbursti at his feet
    freyr: `<g fill="${INK}">${CLOAK}<rect x="46" y="120" width="8" height="150" rx="3"/><rect x="36" y="150" width="28" height="8" rx="3"/><path d="M50 120 L58 104 L50 92 L42 104 Z"/>${TORSO}${HEAD}<path d="M96 84 C108 74 132 74 144 84 L144 76 C132 70 108 70 96 76 Z"/><path d="M104 74 L108 62 L112 74 M116 74 L120 60 L124 74 M128 74 L132 62 L136 74 Z"/><path d="M104 108 C108 152 132 152 136 108 C130 140 110 140 104 108 Z"/><path d="M150 300 C150 276 176 268 196 272 C210 275 220 286 220 300 L210 300 C208 308 200 308 198 300 L176 300 C174 308 166 308 164 300 Z"/><path d="M220 292 C230 290 234 296 230 302 L220 300 Z"/></g>${EYES}<circle cx="205" cy="288" r="2.2" fill="#fff"/>`,
    // Týr — domed helm with noseguard, sword, the wolf Fenrir at his feet
    tyr: `<g fill="${INK}">${CLOAK}<rect x="46" y="118" width="8" height="150" rx="3"/><rect x="36" y="150" width="28" height="8" rx="3"/><path d="M50 118 L58 102 L50 90 L42 102 Z"/>${TORSO}${HEAD}<path d="M94 88 C94 70 108 60 120 60 C132 60 146 70 146 88 L146 80 C146 66 134 58 120 58 C106 58 94 66 94 80 Z"/><rect x="116" y="78" width="8" height="30" rx="2"/><path d="M104 110 C108 150 132 150 136 110 C130 140 110 140 104 110 Z"/><path d="M150 300 L162 268 L172 284 L186 268 L196 284 L210 272 C214 288 206 300 196 300 Z"/><path d="M210 272 L224 262 L220 282 Z"/></g>${EYES}<circle cx="216" cy="272" r="2" fill="#fff"/>`,
    // Loki — back-swept horns, no beard, a coiling serpent, flame-edged cloak
    loki: `<g fill="${INK}"><path d="M120 100 C82 108 64 152 66 300 L96 300 L104 284 L112 300 L128 300 L136 282 L144 300 L174 300 C176 152 158 108 120 100 Z"/>${TORSO}${HEAD}<path d="M100 70 C84 58 74 40 80 26 C92 42 98 58 106 70 Z"/><path d="M140 70 C156 58 166 40 160 26 C148 42 142 58 134 70 Z"/><path d="M150 280 C120 260 168 236 140 214 C118 196 158 176 138 158" fill="none" stroke="${INK}" stroke-width="9" stroke-linecap="round"/><path d="M138 158 L128 150 L142 146 Z"/></g>${EYES}`,
    // Heimdall — winged helm, raising the Gjallarhorn to his lips
    heimdall: `<g fill="${INK}">${CLOAK}${TORSO}${HEAD}<path d="M96 82 C104 66 136 66 144 82 L144 74 C136 62 104 62 96 74 Z"/><path d="M96 78 C82 74 70 78 62 88 C76 86 88 84 98 80 Z"/><path d="M144 78 C158 74 170 78 178 88 C164 86 152 84 142 80 Z"/><path d="M120 168 C136 176 148 186 150 190" fill="none" stroke="${INK}" stroke-width="15" stroke-linecap="round"/><path d="M150 190 C176 170 186 130 150 116" fill="none" stroke="${INK}" stroke-width="12" stroke-linecap="round"/><path d="M150 116 C138 112 130 112 126 116 L140 108 C150 108 152 112 150 116 Z"/></g>${EYES}`
  };
  function fallbackSVG(g) {
    return `<svg viewBox="0 0 240 320" role="img" aria-label="Statue of ${g.god}">${FIG[g.key] || FIG.odin}</svg>`;
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
