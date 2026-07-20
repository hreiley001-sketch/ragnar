/**
 * Asgard scroll atmosphere engine (vanilla).
 * Turns the homepage into a Norse world as you scroll:
 *   Bifrost → Odin (Allfather + ravens)
 *   Midgard → Thor (storm + hammer pulse)
 *   Valhalla → champions' hall
 *   Forge → Loki (trickster shimmer + forge embers)
 * Mounts layered background, observes [data-asgard-realm] sections,
 * and drives --asgard-* CSS variables with rAF for smooth parallax.
 * Does not alter page content, typography, or vault hero structure.
 */
(function () {
  const REALMS = new Set(["bifrost", "midgard", "valhalla", "forge"]);
  const GOD_BY_REALM = {
    bifrost: "odin",
    midgard: "thor",
    valhalla: "valhalla",
    forge: "loki",
  };
  const GOD_LABEL = {
    odin: "ODIN",
    thor: "THOR",
    valhalla: "VALHALLA",
    loki: "LOKI",
  };
  const RUNE_BY_GOD = {
    odin: "ᚨ ᚾ ᛋ ᚢ ᛉ",
    thor: "ᚦ ᛟ ᚱ",
    valhalla: "ᚹ ᚨ ᛚ ᚺ ᚨ ᛚ ᛚ",
    loki: "ᛚ ᛟ ᚲ ᛁ",
  };

  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function mountLayers(root) {
    if (document.getElementById("asgardBg")) return document.getElementById("asgardBg");
    const bg = document.createElement("div");
    bg.id = "asgardBg";
    bg.className = "asgard-bg";
    bg.setAttribute("aria-hidden", "true");
    bg.innerHTML = [
      '<div class="asgard-layer asgard-sky"></div>',
      '<div class="asgard-layer asgard-yggdrasil"></div>',
      '<div class="asgard-layer asgard-bifrost"></div>',
      '<div class="asgard-layer asgard-mist"></div>',
      '<div class="asgard-layer asgard-storm"></div>',
      '<div class="asgard-layer asgard-runes"><span class="asgard-runes-text"></span></div>',
      '<div class="asgard-layer asgard-ravens">',
      '  <span class="asgard-raven asgard-raven-a"></span>',
      '  <span class="asgard-raven asgard-raven-b"></span>',
      "</div>",
      '<div class="asgard-layer asgard-aurora"></div>',
      '<div class="asgard-layer asgard-embers"></div>',
      '<div class="asgard-layer asgard-sigil"><span class="asgard-sigil-name"></span></div>',
      '<div class="asgard-layer asgard-horizon"></div>',
    ].join("");
    const canvas = document.getElementById("arenaCanvas");
    if (canvas && canvas.parentNode) {
      canvas.parentNode.insertBefore(bg, canvas);
    } else {
      root.insertBefore(bg, root.firstChild);
    }
    return bg;
  }

  function setRealm(name) {
    const realm = REALMS.has(name) ? name : "bifrost";
    const god = GOD_BY_REALM[realm] || "odin";
    const html = document.documentElement;
    if (html.getAttribute("data-asgard-realm") === realm) return;
    html.setAttribute("data-asgard-realm", realm);
    html.setAttribute("data-asgard-god", god);

    const nameEl = document.querySelector(".asgard-sigil-name");
    if (nameEl) nameEl.textContent = GOD_LABEL[god] || "";
    const runeEl = document.querySelector(".asgard-runes-text");
    if (runeEl) runeEl.textContent = RUNE_BY_GOD[god] || "ᚱ ᚨ ᚷ ᚾ ᚨ ᚱ";
  }

  function pickRealmFromSections(sections) {
    if (!sections.length) return "bifrost";

    const vh = window.innerHeight || 1;
    const mid = vh * 0.42;
    const maxScroll = Math.max(
      0,
      document.documentElement.scrollHeight - vh
    );
    const scrollY = window.scrollY || 0;

    // Near page bottom — lock onto the forge / Loki chapter
    if (maxScroll > 0 && scrollY / maxScroll > 0.88) {
      const forge = sections.find(
        (el) => el.getAttribute("data-asgard-realm") === "forge"
      );
      if (forge) return "forge";
    }

    // Near page top — stay with Bifrost / Odin
    if (scrollY < vh * 0.35) {
      return sections[0].getAttribute("data-asgard-realm") || "bifrost";
    }

    let best = sections[0];
    let bestDist = Infinity;
    sections.forEach((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.bottom < 0 || rect.top > vh) return;
      const center = rect.top + rect.height * 0.35;
      const dist = Math.abs(center - mid);
      if (dist < bestDist) {
        bestDist = dist;
        best = el;
      }
    });
    return best.getAttribute("data-asgard-realm") || "bifrost";
  }

  function initRealmObserver() {
    const sections = Array.from(document.querySelectorAll("[data-asgard-realm]"));
    if (!sections.length) {
      setRealm("bifrost");
      return;
    }

    setRealm(pickRealmFromSections(sections));

    let ticking = false;
    function update() {
      ticking = false;
      setRealm(pickRealmFromSections(sections));
    }
    function onScroll() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(update);
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
  }

  function initScrollVars() {
    const docEl = document.documentElement;
    let ticking = false;
    let lastY = window.scrollY || 0;
    let smoothVel = 0;
    let ravenPhase = 0;

    function apply() {
      ticking = false;
      const scrollY = window.scrollY || 0;
      const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
      const progress = Math.min(1, Math.max(0, scrollY / max));
      const rawVel = scrollY - lastY;
      smoothVel = smoothVel * 0.82 + rawVel * 0.18;
      lastY = scrollY;

      const parallaxY = -scrollY * 0.055 + smoothVel * 0.12;
      const parallaxX = Math.sin(progress * Math.PI * 2) * 12 + smoothVel * 0.04;
      ravenPhase += 0.004 + Math.min(0.02, Math.abs(smoothVel) * 0.002);

      docEl.style.setProperty("--asgard-scroll", progress.toFixed(4));
      docEl.style.setProperty("--asgard-parallax-y", `${parallaxY.toFixed(2)}px`);
      docEl.style.setProperty("--asgard-parallax-x", `${parallaxX.toFixed(2)}px`);
      docEl.style.setProperty("--asgard-velocity", Math.max(-1, Math.min(1, smoothVel / 40)).toFixed(3));
      docEl.style.setProperty("--asgard-raven-phase", ravenPhase.toFixed(3));

      const storm =
        docEl.getAttribute("data-asgard-god") === "thor"
          ? Math.min(1, 0.4 + Math.abs(smoothVel) / 50)
          : Math.max(0, 0.12 - Math.abs(smoothVel) / 120);
      docEl.style.setProperty("--asgard-storm", storm.toFixed(3));
    }

    function onScroll() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(apply);
    }

    if (prefersReducedMotion()) {
      docEl.style.setProperty("--asgard-scroll", "0");
      docEl.style.setProperty("--asgard-parallax-y", "0px");
      docEl.style.setProperty("--asgard-parallax-x", "0px");
      docEl.style.setProperty("--asgard-velocity", "0");
      docEl.style.setProperty("--asgard-storm", "0");
      docEl.style.setProperty("--asgard-raven-phase", "0");
      return;
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    apply();
  }

  function initThorPulse() {
    if (prefersReducedMotion()) return;
    const docEl = document.documentElement;
    let lastFlash = 0;

    function maybeFlash(now) {
      if (docEl.getAttribute("data-asgard-god") !== "thor") {
        requestAnimationFrame(maybeFlash);
        return;
      }
      if (now - lastFlash > 4200 + Math.random() * 3800) {
        lastFlash = now;
        docEl.classList.add("asgard-thunder");
        window.setTimeout(() => docEl.classList.remove("asgard-thunder"), 420);
      }
      requestAnimationFrame(maybeFlash);
    }
    requestAnimationFrame(maybeFlash);
  }

  function init() {
    if (!document.body.classList.contains("arena-home")) return;
    mountLayers(document.body);
    document.body.classList.add("asgard-active");
    setRealm("bifrost");
    initRealmObserver();
    initScrollVars();
    initThorPulse();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.__ragnarAsgard = { setRealm, init, GOD_BY_REALM };
})();
