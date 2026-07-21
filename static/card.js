// RAGNAR Card — shared foil surface, shimmer idle, pointer tilt.
"use strict";

(function (global) {
  const REDUCE = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const COARSE = () => matchMedia("(pointer: coarse)").matches;

  function shimmerMarkup(slow) {
    return `<span class="ragnar-card__shimmer${slow ? " ragnar-card__shimmer--slow" : ""}" aria-hidden="true"></span>`;
  }

  function ensureShimmer(card, slow) {
    if (!card || card.querySelector(".ragnar-card__shimmer")) return;
    card.insertAdjacentHTML("afterbegin", shimmerMarkup(slow));
  }

  function mountTilt(card) {
    if (!card || card.dataset.tiltBound || REDUCE() || COARSE()) return;
    card.dataset.tiltBound = "1";

    card.addEventListener("pointermove", (event) => {
      const bounds = card.getBoundingClientRect();
      const px = (event.clientX - bounds.left) / bounds.width - 0.5;
      const py = (event.clientY - bounds.top) / bounds.height - 0.5;
      card.style.setProperty("--card-rx", `${(-py * 5).toFixed(2)}deg`);
      card.style.setProperty("--card-ry", `${(px * 6).toFixed(2)}deg`);
      card.classList.add("is-hovered");
    });

    card.addEventListener("pointerleave", () => {
      card.style.setProperty("--card-rx", "0deg");
      card.style.setProperty("--card-ry", "0deg");
      card.classList.remove("is-hovered");
    });
  }

  function enhanceCards(root, options = {}) {
    const scope = root || document;
    const selector = options.selector || ".ragnar-card";
    scope.querySelectorAll(selector).forEach((card) => {
      ensureShimmer(card, options.slowShimmer || card.classList.contains("ragnar-card--archive"));
      if (!options.noTilt) mountTilt(card);
    });
  }

  function blankCardHTML({ title, subtitle, ctaHref, ctaLabel, variant = "blank" } = {}) {
    const cta = ctaHref
      ? `<div style="margin-top:22px"><a class="arena-btn small" href="${ctaHref}">${ctaLabel || "Explore"} <span class="arrow">→</span></a></div>`
      : "";
    return `
      <div class="ragnar-card ragnar-card--${variant} ragnar-card--blank arena-empty">
        <div class="ragnar-card__shimmer" aria-hidden="true"></div>
        <div class="ragnar-card__pulse" aria-hidden="true"></div>
        <div>
          ${title ? `<strong>${title}</strong>` : ""}
          ${subtitle ? `<span>${subtitle}</span>` : ""}
          ${cta}
        </div>
      </div>`;
  }

  global.RagnarCard = { enhanceCards, blankCardHTML, ensureShimmer, mountTilt };
})(window);
