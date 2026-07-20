/**
 * Asgard scroll atmosphere engine (vanilla).
 * Mounts layered background, observes [data-asgard-realm] sections,
 * and drives --asgard-* CSS variables with rAF for smooth parallax.
 * Does not alter page content, typography, or vault hero structure.
 */
(function () {
  const REALMS = new Set(["bifrost", "midgard", "valhalla", "forge"]);

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
      '<div class="asgard-layer asgard-mist"></div>',
      '<div class="asgard-layer asgard-runes"></div>',
      '<div class="asgard-layer asgard-aurora"></div>',
      '<div class="asgard-layer asgard-horizon"></div>',
    ].join("");
    // Insert after skip link / before canvas so existing arena layers stay on top
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
    if (document.documentElement.getAttribute("data-asgard-realm") === realm) return;
    document.documentElement.setAttribute("data-asgard-realm", realm);
  }

  function initRealmObserver() {
    const sections = Array.from(document.querySelectorAll("[data-asgard-realm]"));
    if (!sections.length) {
      setRealm("bifrost");
      return;
    }

    // Pick the section closest to viewport center
    let active = sections[0].getAttribute("data-asgard-realm") || "bifrost";
    setRealm(active);

    if (!("IntersectionObserver" in window)) return;

    const ratios = new Map();
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          ratios.set(entry.target, entry.isIntersecting ? entry.intersectionRatio : 0);
        });
        let best = null;
        let bestScore = -1;
        sections.forEach((el) => {
          const score = ratios.get(el) || 0;
          if (score > bestScore) {
            bestScore = score;
            best = el;
          }
        });
        if (best) setRealm(best.getAttribute("data-asgard-realm") || "bifrost");
      },
      {
        root: null,
        // Bias toward the middle band of the viewport
        rootMargin: "-28% 0px -38% 0px",
        threshold: [0, 0.15, 0.35, 0.55, 0.75, 1],
      }
    );

    sections.forEach((el) => observer.observe(el));
  }

  function initScrollVars() {
    const docEl = document.documentElement;
    let ticking = false;
    let lastY = 0;

    function apply() {
      ticking = false;
      const scrollY = window.scrollY || 0;
      const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
      const progress = Math.min(1, Math.max(0, scrollY / max));
      // Subtle parallax — keep GPU-friendly, avoid layout thrash
      const parallax = (scrollY - lastY) * 0.08;
      lastY = scrollY * 0.15 + lastY * 0.85;
      docEl.style.setProperty("--asgard-scroll", progress.toFixed(4));
      docEl.style.setProperty("--asgard-parallax-y", `${(-scrollY * 0.04 + parallax).toFixed(2)}px`);
    }

    function onScroll() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(apply);
    }

    if (prefersReducedMotion()) {
      docEl.style.setProperty("--asgard-scroll", "0");
      docEl.style.setProperty("--asgard-parallax-y", "0px");
      return;
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    apply();
  }

  function init() {
    if (!document.body.classList.contains("arena-home")) return;
    mountLayers(document.body);
    document.body.classList.add("asgard-active");
    setRealm("bifrost");
    initRealmObserver();
    initScrollVars();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.__ragnarAsgard = { setRealm, init };
})();
