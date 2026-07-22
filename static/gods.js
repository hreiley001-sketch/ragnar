// RAGNAR — Gods of the realms.
// Stylized patron statues + per-page runic glow, jewels, and realm color accents.
// Real art: drop a transparent-background PNG at /static/gods/<key>.png to override.
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

  /* ---------- Stylized carved statues (distinct silhouette + jewels) ---------- */
  const INK = "#0c1012";
  function gem(cx, cy, r, fill, hi) {
    return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${fill}"/><circle cx="${cx - r * 0.28}" cy="${cy - r * 0.28}" r="${r * 0.32}" fill="${hi || "#fff"}" opacity=".85"/>`;
  }
  function diamond(cx, cy, s, fill) {
    return `<path d="M${cx} ${cy - s} L${cx + s * 0.7} ${cy} L${cx} ${cy + s} L${cx - s * 0.7} ${cy} Z" fill="${fill}"/>`;
  }

  const FIG = {
    // FREYR — harvest lord: leaf circlet, amber jewels, boar Gullinbursti, grain sword
    freyr: (() => {
      const g = "#c8901f", soft = "#e8c46a", jade = "#7ec8a0";
      return `
        <defs>
          <radialGradient id="fg" cx="50%" cy="40%"><stop offset="0%" stop-color="${soft}" stop-opacity=".35"/><stop offset="100%" stop-color="${g}" stop-opacity="0"/></radialGradient>
        </defs>
        <ellipse cx="120" cy="200" rx="70" ry="90" fill="url(#fg)"/>
        <!-- cloak with harvest hem -->
        <path d="M120 98 C72 108 48 155 46 300 L194 300 C192 155 168 108 120 98 Z" fill="${INK}"/>
        <path d="M56 280 Q88 250 120 270 Q152 250 184 280" fill="none" stroke="${g}" stroke-width="3" opacity=".7"/>
        <!-- torso + arms -->
        <path d="M120 110 C92 114 82 142 84 178 L156 178 C158 142 148 114 120 110 Z" fill="${INK}"/>
        <!-- grain sword -->
        <rect x="42" y="118" width="9" height="155" rx="3" fill="${INK}"/>
        <path d="M46.5 118 L54 98 L46.5 84 L39 98 Z" fill="${INK}"/>
        ${gem(46.5, 108, 4.5, soft, "#fff8d0")}
        ${diamond(46.5, 155, 6, jade)}
        ${diamond(46.5, 190, 5, g)}
        <!-- head + leaf circlet -->
        <path d="M120 58 C103 58 91 72 91 90 C91 110 103 122 120 122 C137 122 149 110 149 90 C149 72 137 58 120 58 Z" fill="${INK}"/>
        <path d="M94 80 C108 68 132 68 146 80 L146 72 C132 62 108 62 94 72 Z" fill="${INK}"/>
        <path d="M100 70 L106 54 L112 70 M116 68 L120 50 L124 68 M128 70 L134 54 L140 70" fill="none" stroke="${g}" stroke-width="3.5" stroke-linecap="round"/>
        ${gem(120, 52, 5, soft, "#fff")}
        ${gem(106, 66, 3.2, jade)}
        ${gem(134, 66, 3.2, jade)}
        <!-- short beard -->
        <path d="M104 108 C108 148 132 148 136 108 C130 138 110 138 104 108 Z" fill="${INK}"/>
        <!-- glowing eyes -->
        <circle cx="111" cy="92" r="3.8" fill="${soft}"/><circle cx="129" cy="92" r="3.8" fill="${soft}"/>
        <circle cx="111" cy="92" r="1.6" fill="#fff"/><circle cx="129" cy="92" r="1.6" fill="#fff"/>
        <!-- boar Gullinbursti -->
        <path d="M148 300 C148 274 174 266 196 270 C212 274 222 286 222 300 L210 300 C208 308 200 308 198 300 L174 300 C172 308 164 308 162 300 Z" fill="${INK}"/>
        <path d="M222 292 C232 288 236 296 232 304 L222 300 Z" fill="${INK}"/>
        <path d="M168 278 Q188 270 206 282" fill="none" stroke="${soft}" stroke-width="2" opacity=".8"/>
        ${gem(205, 286, 3.2, soft)}
        ${gem(178, 288, 2.4, jade)}`;
    })(),

    // THOR — thunderer: horned helm, storm cloak, raised Mjölnir, lightning jewels
    thor: (() => {
      const g = "#2f93c4", soft = "#7ec8e8", bolt = "#f0c040";
      return `
        <defs>
          <radialGradient id="tg" cx="50%" cy="35%"><stop offset="0%" stop-color="${soft}" stop-opacity=".4"/><stop offset="100%" stop-color="${g}" stop-opacity="0"/></radialGradient>
        </defs>
        <ellipse cx="120" cy="190" rx="72" ry="95" fill="url(#tg)"/>
        <!-- storm cloak -->
        <path d="M120 96 C70 106 46 150 44 300 L196 300 C194 150 170 106 120 96 Z" fill="${INK}"/>
        <path d="M70 160 L88 200 L74 240 L96 280" fill="none" stroke="${g}" stroke-width="2.5" opacity=".55"/>
        <path d="M170 150 L152 195 L168 235 L148 275" fill="none" stroke="${soft}" stroke-width="2" opacity=".45"/>
        <!-- raised arm + Mjölnir -->
        <path d="M120 165 C152 165 174 150 186 132" fill="none" stroke="${INK}" stroke-width="18" stroke-linecap="round"/>
        <rect x="180" y="148" width="13" height="78" rx="4" fill="${INK}"/>
        <rect x="158" y="114" width="56" height="38" rx="6" fill="${INK}"/>
        <rect x="166" y="122" width="40" height="22" rx="3" fill="${g}" opacity=".35"/>
        ${gem(186, 133, 5, soft, "#e8f8ff")}
        ${diamond(186, 175, 5.5, bolt)}
        <!-- lightning bolt beside hammer -->
        <path d="M214 128 L204 148 L212 148 L200 172 L214 148 L206 148 Z" fill="${bolt}" opacity=".9"/>
        <!-- torso -->
        <path d="M120 108 C92 112 82 140 84 176 L156 176 C158 140 148 112 120 108 Z" fill="${INK}"/>
        ${gem(120, 140, 4.5, soft)}
        ${gem(105, 155, 3, bolt)}
        ${gem(135, 155, 3, bolt)}
        <!-- head + horned helm -->
        <path d="M120 56 C103 56 91 70 91 88 C91 108 103 120 120 120 C137 120 149 108 149 88 C149 70 137 56 120 56 Z" fill="${INK}"/>
        <path d="M90 80 C102 62 138 62 150 80 L150 72 C138 58 102 58 90 72 Z" fill="${INK}"/>
        <path d="M90 78 C70 64 60 40 66 22 C86 38 94 60 98 76 Z" fill="${INK}"/>
        <path d="M150 78 C170 64 180 40 174 22 C154 38 146 60 142 76 Z" fill="${INK}"/>
        ${gem(66, 32, 3.5, soft)}
        ${gem(174, 32, 3.5, soft)}
        <!-- braided beard -->
        <path d="M98 106 C102 178 138 178 142 106 C134 148 106 148 98 106 Z" fill="${INK}"/>
        <path d="M112 130 L112 165 M128 130 L128 165" stroke="${g}" stroke-width="2" opacity=".5"/>
        <circle cx="111" cy="90" r="4" fill="${soft}"/><circle cx="129" cy="90" r="4" fill="${soft}"/>
        <circle cx="111" cy="90" r="1.7" fill="#fff"/><circle cx="129" cy="90" r="1.7" fill="#fff"/>`;
    })(),

    // TÝR — oath-binder: noseguard helm, sword, Fenrir, jade/gold jewels, missing-hand sacrifice mark
    tyr: (() => {
      const g = "#2f8f6b", soft = "#6ec4a0", gold = "#d4a84a";
      return `
        <defs>
          <radialGradient id="yg" cx="50%" cy="40%"><stop offset="0%" stop-color="${soft}" stop-opacity=".38"/><stop offset="100%" stop-color="${g}" stop-opacity="0"/></radialGradient>
        </defs>
        <ellipse cx="120" cy="195" rx="68" ry="92" fill="url(#yg)"/>
        <path d="M120 98 C74 108 50 152 48 300 L192 300 C190 152 166 108 120 98 Z" fill="${INK}"/>
        <!-- oath band across cloak -->
        <path d="M62 220 H178" stroke="${g}" stroke-width="4" opacity=".55"/>
        ${diamond(120, 220, 7, gold)}
        <!-- torso -->
        <path d="M120 110 C94 114 84 140 86 176 L154 176 C156 140 146 114 120 110 Z" fill="${INK}"/>
        ${gem(120, 142, 4.2, soft)}
        <!-- sword (left) -->
        <rect x="42" y="116" width="9" height="152" rx="3" fill="${INK}"/>
        <rect x="34" y="148" width="26" height="9" rx="3" fill="${INK}"/>
        <path d="M46.5 116 L54 98 L46.5 86 L39 98 Z" fill="${INK}"/>
        ${gem(46.5, 106, 4, gold, "#fff4d0")}
        ${diamond(46.5, 170, 5, soft)}
        <!-- right arm stub — sacrifice mark with glowing ring -->
        <path d="M154 145 C168 148 176 158 178 172" fill="none" stroke="${INK}" stroke-width="14" stroke-linecap="round"/>
        <circle cx="182" cy="178" r="10" fill="none" stroke="${g}" stroke-width="3" opacity=".85"/>
        ${gem(182, 178, 4, soft)}
        <!-- head + noseguard helm -->
        <path d="M120 58 C103 58 91 72 91 90 C91 110 103 122 120 122 C137 122 149 110 149 90 C149 72 137 58 120 58 Z" fill="${INK}"/>
        <path d="M94 86 C94 68 108 58 120 58 C132 58 146 68 146 86 L146 78 C146 64 134 56 120 56 C106 56 94 64 94 78 Z" fill="${INK}"/>
        <rect x="116" y="76" width="8" height="32" rx="2" fill="${INK}"/>
        ${gem(120, 64, 4, soft)}
        ${gem(100, 78, 2.8, gold)}
        ${gem(140, 78, 2.8, gold)}
        <path d="M104 110 C108 148 132 148 136 110 C130 138 110 138 104 110 Z" fill="${INK}"/>
        <circle cx="111" cy="92" r="3.6" fill="${soft}"/><circle cx="129" cy="92" r="3.6" fill="${soft}"/>
        <circle cx="111" cy="92" r="1.5" fill="#fff"/><circle cx="129" cy="92" r="1.5" fill="#fff"/>
        <!-- Fenrir -->
        <path d="M148 300 L160 266 L170 282 L184 266 L194 282 L208 270 C212 288 204 300 194 300 Z" fill="${INK}"/>
        <path d="M208 270 L222 258 L218 280 Z" fill="${INK}"/>
        <circle cx="216" cy="270" r="3.5" fill="${soft}"/>
        ${gem(170, 288, 2.5, gold)}`;
    })(),

    // LOKI — trickster: swept horns, flame cloak, serpent, violet/ember jewels, asymmetrical grin
    loki: (() => {
      const g = "#7a5cc4", soft = "#b49ae8", ember = "#e87850", magenta = "#c070e0";
      return `
        <defs>
          <radialGradient id="lg" cx="45%" cy="35%"><stop offset="0%" stop-color="${magenta}" stop-opacity=".38"/><stop offset="100%" stop-color="${g}" stop-opacity="0"/></radialGradient>
        </defs>
        <ellipse cx="118" cy="190" rx="70" ry="94" fill="url(#lg)"/>
        <!-- flame-edged cloak -->
        <path d="M120 98 C80 108 62 152 64 300 L94 300 L102 282 L110 300 L128 300 L136 280 L144 300 L176 300 C178 152 160 108 120 98 Z" fill="${INK}"/>
        <path d="M70 250 L78 230 L86 255 L94 225 L102 260" fill="none" stroke="${ember}" stroke-width="2.5" opacity=".7"/>
        <path d="M150 245 L158 220 L166 250 L174 228 L180 258" fill="none" stroke="${magenta}" stroke-width="2.5" opacity=".65"/>
        <!-- torso -->
        <path d="M120 110 C94 114 86 140 88 174 L152 174 C154 140 146 114 120 110 Z" fill="${INK}"/>
        ${gem(112, 138, 4, magenta, "#f0d0ff")}
        ${gem(130, 148, 3.2, ember)}
        ${diamond(120, 162, 5, soft)}
        <!-- head + swept horns -->
        <path d="M120 58 C103 58 92 72 92 90 C92 110 104 122 120 122 C136 122 148 110 148 90 C148 72 137 58 120 58 Z" fill="${INK}"/>
        <path d="M98 68 C80 54 68 34 76 18 C90 36 98 54 106 68 Z" fill="${INK}"/>
        <path d="M142 68 C160 54 172 34 164 18 C150 36 142 54 134 68 Z" fill="${INK}"/>
        ${gem(76, 26, 3.5, magenta)}
        ${gem(164, 26, 3.5, ember)}
        <!-- mischievous eyes (slightly angled) -->
        <ellipse cx="110" cy="90" rx="4.2" ry="3.4" fill="${soft}" transform="rotate(-8 110 90)"/>
        <ellipse cx="130" cy="90" rx="4.2" ry="3.4" fill="${soft}" transform="rotate(8 130 90)"/>
        <circle cx="110" cy="90" r="1.5" fill="#fff"/><circle cx="130" cy="90" r="1.5" fill="#fff"/>
        <!-- serpentine companion -->
        <path d="M152 278 C120 256 170 232 140 210 C118 192 160 172 138 154" fill="none" stroke="${INK}" stroke-width="10" stroke-linecap="round"/>
        <path d="M138 154 L126 144 L144 140 Z" fill="${INK}"/>
        <path d="M152 278 C120 256 170 232 140 210 C118 192 160 172 138 154" fill="none" stroke="${g}" stroke-width="2.5" opacity=".55"/>
        ${gem(140, 210, 3.2, magenta)}
        ${gem(155, 250, 2.6, ember)}`;
    })(),

    // HEIMDALL — bifrost warden: winged helm, Gjallarhorn, teal/gold jewels, all-seeing gaze
    heimdall: (() => {
      const g = "#1f8f9a", soft = "#6ec8d0", gold = "#e8a840", bifrost = "#80a0e8";
      return `
        <defs>
          <radialGradient id="hg" cx="50%" cy="30%"><stop offset="0%" stop-color="${soft}" stop-opacity=".42"/><stop offset="100%" stop-color="${g}" stop-opacity="0"/></radialGradient>
          <linearGradient id="hb" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="#e87850"/><stop offset="35%" stop-color="${gold}"/>
            <stop offset="65%" stop-color="${g}"/><stop offset="100%" stop-color="${bifrost}"/>
          </linearGradient>
        </defs>
        <ellipse cx="120" cy="190" rx="70" ry="92" fill="url(#hg)"/>
        <path d="M120 98 C74 108 50 152 48 300 L192 300 C190 152 166 108 120 98 Z" fill="${INK}"/>
        <!-- bifrost sash -->
        <path d="M58 200 H182" stroke="url(#hb)" stroke-width="5" opacity=".75"/>
        <!-- torso -->
        <path d="M120 110 C94 114 84 140 86 176 L154 176 C156 140 146 114 120 110 Z" fill="${INK}"/>
        ${gem(120, 140, 4.5, soft, "#e0fffc")}
        ${gem(104, 155, 3, gold)}
        ${gem(136, 155, 3, bifrost)}
        <!-- head + winged helm -->
        <path d="M120 56 C103 56 91 70 91 88 C91 108 103 120 120 120 C137 120 149 108 149 88 C149 70 137 56 120 56 Z" fill="${INK}"/>
        <path d="M96 80 C104 64 136 64 144 80 L144 72 C136 60 104 60 96 72 Z" fill="${INK}"/>
        <path d="M96 76 C80 70 64 76 54 90 C72 86 88 82 100 78 Z" fill="${INK}"/>
        <path d="M144 76 C160 70 176 76 186 90 C168 86 152 82 140 78 Z" fill="${INK}"/>
        ${gem(58, 84, 3.2, soft)}
        ${gem(182, 84, 3.2, gold)}
        ${gem(120, 62, 4, soft)}
        <!-- all-seeing eyes (bright) -->
        <circle cx="110" cy="90" r="4.4" fill="${soft}"/><circle cx="130" cy="90" r="4.4" fill="${soft}"/>
        <circle cx="110" cy="90" r="2" fill="#fff"/><circle cx="130" cy="90" r="2" fill="#fff"/>
        <circle cx="120" cy="78" r="2.2" fill="${gold}" opacity=".9"/>
        <!-- Gjallarhorn raised -->
        <path d="M120 165 C138 174 150 186 152 192" fill="none" stroke="${INK}" stroke-width="16" stroke-linecap="round"/>
        <path d="M152 192 C180 170 190 128 152 112" fill="none" stroke="${INK}" stroke-width="13" stroke-linecap="round"/>
        <path d="M152 112 C138 106 128 106 124 112 L140 102 C152 102 154 108 152 112 Z" fill="${INK}"/>
        <path d="M152 192 C180 170 190 128 152 112" fill="none" stroke="${g}" stroke-width="2.5" opacity=".5"/>
        ${gem(170, 140, 4, gold, "#fff4d0")}
        ${diamond(158, 165, 5, soft)}`;
    })(),

    // ODIN — all-father: wide hat, Gungnir, ravens Huginn & Muninn, amber/steel jewels, one eye
    odin: (() => {
      const g = "#a67c1a", soft = "#d4b050", steel = "#7088c0", glow = "#f0d878";
      return `
        <defs>
          <radialGradient id="og" cx="50%" cy="35%"><stop offset="0%" stop-color="${soft}" stop-opacity=".4"/><stop offset="100%" stop-color="${g}" stop-opacity="0"/></radialGradient>
        </defs>
        <ellipse cx="120" cy="195" rx="72" ry="94" fill="url(#og)"/>
        <!-- Gungnir -->
        <rect x="198" y="42" width="8" height="255" rx="3" fill="${INK}"/>
        <path d="M202 28 L214 52 L202 68 L190 52 Z" fill="${INK}"/>
        ${gem(202, 48, 4.5, soft, "#fff8e0")}
        ${diamond(202, 100, 5, steel)}
        ${diamond(202, 160, 4.5, g)}
        <!-- cloak -->
        <path d="M120 98 C72 108 48 152 46 300 L194 300 C192 152 168 108 120 98 Z" fill="${INK}"/>
        <path d="M70 180 Q120 160 170 180" fill="none" stroke="${g}" stroke-width="2.5" opacity=".45"/>
        <!-- torso -->
        <path d="M120 110 C94 114 84 140 86 176 L154 176 C156 140 146 114 120 110 Z" fill="${INK}"/>
        ${gem(120, 138, 4.5, soft)}
        ${gem(108, 152, 2.8, steel)}
        ${gem(132, 152, 2.8, steel)}
        <!-- ravens on shoulders -->
        <path d="M44 148 C58 130 84 138 88 150 C76 150 66 156 60 168 C56 156 50 152 44 148 Z" fill="${INK}"/>
        <path d="M196 148 C182 130 156 138 152 150 C164 150 174 156 180 168 C184 156 190 152 196 148 Z" fill="${INK}"/>
        ${gem(62, 152, 2.8, steel, "#d0e0ff")}
        ${gem(178, 152, 2.8, soft)}
        <!-- head + wide-brim hat -->
        <path d="M120 58 C103 58 91 72 91 90 C91 110 103 122 120 122 C137 122 149 110 149 90 C149 72 137 58 120 58 Z" fill="${INK}"/>
        <path d="M74 82 C100 58 140 58 166 82 C142 98 98 98 74 82 Z" fill="${INK}"/>
        <path d="M96 82 C104 50 136 50 144 82 Z" fill="${INK}"/>
        ${gem(120, 56, 4, soft)}
        ${gem(86, 78, 2.6, steel)}
        ${gem(154, 78, 2.6, steel)}
        <!-- long beard -->
        <path d="M100 106 C104 172 136 172 140 106 C134 140 106 140 100 106 Z" fill="${INK}"/>
        <!-- one glowing eye (right closed) -->
        <circle cx="109" cy="92" r="4.2" fill="${glow}"/>
        <circle cx="109" cy="92" r="1.8" fill="#fff"/>
        <path d="M124 90 Q130 94 136 90" fill="none" stroke="${soft}" stroke-width="2.2" stroke-linecap="round" opacity=".7"/>`;
    })()
  };

  function fallbackSVG(g) {
    return `<svg viewBox="0 0 240 320" role="img" aria-label="Statue of ${g.god}">${FIG[g.key] || FIG.odin}</svg>`;
  }
  function figureHTML(g) {
    return `<span class="god-figure">${fallbackSVG(g)}<img src="/static/gods/${g.key}.png" alt="${g.god}, ${g.realm}"
      loading="lazy" decoding="async"
      onload="this.previousElementSibling.style.display='none'"
      onerror="this.remove()" /></span>`;
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
    // Soft-retarget brand accents for this realm (keeps ivory surfaces)
    root.style.setProperty("--color-accent-primary", g.rcDeep);
    root.style.setProperty("--color-accent-primary-strong", g.rc);
    root.style.setProperty("--color-accent-gold", g.rc);
    root.style.setProperty("--color-accent-gold-strong", g.rcSoft);
    root.style.setProperty("--color-crystal", g.rcDeep);
    root.style.setProperty("--color-border-gold", `color-mix(in srgb, ${g.rc} 55%, transparent)`);
    root.style.setProperty("--color-hover-surface", `color-mix(in srgb, ${g.rc} 12%, transparent)`);
    root.style.setProperty("--color-active-surface", `color-mix(in srgb, ${g.rc} 18%, transparent)`);
  }

  function jewelRow(g, i) {
    const tone = i % 3 === 0 ? g.jewel : i % 3 === 1 ? g.jewel2 : g.rcSoft;
    const kinds = ["rj-diamond", "rj-round", "rj-facet", "rj-ember"];
    return `<span class="rj ${kinds[i % kinds.length]} rj-${i}" style="--j:${tone};--rc:${g.rc}"></span>`;
  }

  function injectRealmMagic(g, multi) {
    if (document.querySelector(".realm-jewels")) return;
    const el = document.createElement("div");
    el.className = "realm-jewels" + (multi ? " realm-jewels--pantheon" : "");
    el.setAttribute("aria-hidden", "true");

    const gods = multi ? GODS : [g, g, g];
    const jewels = [];
    for (let i = 0; i < 18; i++) jewels.push(jewelRow(gods[i % gods.length], i));

    const runes = multi
      ? GODS.map((x, i) => `<span class="realm-rune-glow rr-${i}" style="--rc:${x.rc};--jewel:${x.jewel}">${x.rune}</span>`).join("")
      : [0, 1, 2, 3, 4].map((i) => `<span class="realm-rune-glow rr-${i}">${g.rune}</span>`).join("");

    const pools = multi
      ? GODS.map((x, i) => `<span class="realm-color-pool pool-${i}" style="--rc:${x.rc};--jewel:${x.jewel};--jewel-2:${x.jewel2}"></span>`).join("")
      : `<span class="realm-color-pool pool-0"></span>
         <span class="realm-color-pool pool-1" style="--rc:var(--jewel-2);--jewel:var(--rc-soft)"></span>
         <span class="realm-color-pool pool-2" style="--rc:var(--jewel);--jewel:var(--rc)"></span>
         <span class="realm-color-pool pool-3"></span>`;

    el.innerHTML = `
      <div class="realm-color-fill"></div>
      ${pools}
      <div class="realm-knot-band band-top"></div>
      <div class="realm-knot-band band-bot"></div>
      <div class="realm-norse-ring ring-a"></div>
      <div class="realm-norse-ring ring-b"></div>
      ${jewels.join("")}
      ${runes}
      <span class="realm-ember e1"></span><span class="realm-ember e2"></span>
      <span class="realm-ember e3"></span><span class="realm-ember e4"></span>`;
    document.body.appendChild(el);
  }

  // ---- Home: full pantheon magic (all god colors) ----
  if (onHome) {
    document.body.dataset.patron = "pantheon";
    injectRealmMagic(ODIN, true);
  }

  // ---- Background patron + realm theme (every page except home vault) ----
  if (!onHome) {
    const g = patronFor(path);
    applyRealmTheme(g);
    injectRealmMagic(g, false);
    if (!document.querySelector(".realm-patron")) {
      const el = document.createElement("div");
      el.className = "realm-patron";
      el.setAttribute("aria-hidden", "true");
      el.style.setProperty("--rc", g.rc);
      el.style.setProperty("--jewel", g.jewel);
      el.innerHTML = `
        <span class="rp-glow"></span>
        <span class="rp-glow rp-glow-2"></span>
        <span class="rp-fig">${figureHTML(g)}</span>`;
      document.body.appendChild(el);
    }
  }

  // ---- Pantheon wall (fills #pantheonWall if present) ----
  function buildPantheon(host) {
    if (!host) return;
    host.innerHTML = GODS.map((g) => `
      <a class="god-shrine god-shrine--${g.key}" style="--rc:${g.rc};--rc-deep:${g.rcDeep};--rc-soft:${g.rcSoft};--jewel:${g.jewel};--jewel-2:${g.jewel2}" href="${g.paths[0]}" aria-label="${g.god} — ${g.realm}">
        <div class="altar">
          <span class="halo"></span><span class="rays"></span>
          <span class="altar-mist"></span>
          <span class="jewel-tl"></span><span class="jewel-tr"></span>
          <span class="jewel-bl"></span><span class="jewel-br"></span>
          <span class="jewel-mid"></span>
          <span class="runemark">${g.rune}</span>
          ${figureHTML(g)}
          <span class="altar-base"></span>
        </div>
        <div class="plate">
          <div class="nm">${g.god}</div>
          <div class="ti">${g.title} · ${g.realm}</div>
        </div>
      </a>`).join("");
  }
  window.RagnarGods = { list: GODS, buildPantheon, patronFor };

  const host = document.getElementById("pantheonWall");
  if (host) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => buildPantheon(host));
    else buildPantheon(host);
  }
})();
