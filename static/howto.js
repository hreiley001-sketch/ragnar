// RAGNAR — "How it works" onboarding band.
// Shown once on the home page only. Dismissible (remembered in localStorage).
// Ensures sell.js is loaded so the "List a card" CTA always opens the sell drawer.
"use strict";
(function () {
  const path = (location.pathname.replace(/\/+$/, "") || "/");

  // Strict home only — never on other pages (including ones that reuse arena-home).
  if (path !== "/") return;
  if (localStorage.getItem("ragnar_howto_dismissed") === "1") return;

  function ensureSell() {
    const has = Array.prototype.some.call(document.scripts, (s) => /\/static\/sell\.js/.test(s.src || ""));
    if (!has) {
      const s = document.createElement("script");
      s.src = "/static/sell.js";
      document.body.appendChild(s);
    }
  }

  function dismiss(band) {
    localStorage.setItem("ragnar_howto_dismissed", "1");
    if (band) band.remove();
  }

  function build() {
    if (document.getElementById("ragnarHowto")) return;
    const band = document.createElement("section");
    band.id = "ragnarHowto";
    band.className = "howto";
    band.setAttribute("aria-label", "How RAGNAR works");
    band.innerHTML = `
      <button class="howto-x" type="button" aria-label="Hide this">✕</button>
      <div class="howto-head">
        <span class="howto-kicker">New to RAGNAR?</span>
        <h2>How it works</h2>
        <p class="howto-sub">Buy in a few taps — or list a card in under a minute.</p>
      </div>
      <div class="howto-cols">
        <div class="howto-col">
          <h3>🛒 Buying</h3>
          <ol>
            <li><b>Search or ask.</b> Type a card, or tap <b>Ask RAGNAR</b> (bottom-right) and say what you're after.</li>
            <li><b>Buy Now or make an offer.</b> Instantly see comps from real sold prices on every listing.</li>
            <li><b>Secure checkout.</b> Per-seller checkout with buyer protection — all fees shown up front.</li>
          </ol>
        </div>
        <div class="howto-col">
          <h3>🏷️ Listing a card</h3>
          <ol>
            <li><b>Tap “List a card”</b> and add a photo of the card.</li>
            <li><b>AI fills it in</b> — set, grade, and a suggested price from real sold comps.</li>
            <li><b>Publish.</b> It goes live on your store and the marketplace. Flat 5% fee (4% Founding).</li>
          </ol>
        </div>
      </div>
      <div class="howto-cta">
        <button class="btn btn-primary" type="button" data-open-sell>⚡ List a card</button>
        <a class="btn btn-ghost" href="/marketplace">Browse marketplace</a>
        <a class="btn btn-ghost" href="/ai-tools">See how the AI works</a>
      </div>`;

    // Insert right after the home hero (or at the top of main / after header).
    const hero = document.querySelector(".home-hero");
    if (hero && hero.parentNode) {
      hero.parentNode.insertBefore(band, hero.nextSibling);
    } else {
      const main = document.querySelector("main");
      if (main) main.insertBefore(band, main.firstChild);
      else {
        const hdr = document.getElementById("siteHeader");
        if (hdr && hdr.parentNode) hdr.parentNode.insertBefore(band, hdr.nextSibling);
        else document.body.appendChild(band);
      }
    }

    band.querySelector(".howto-x").addEventListener("click", () => dismiss(band));

    // Seen once: remember after this visit so it does not return on later home loads.
    localStorage.setItem("ragnar_howto_dismissed", "1");
  }

  function init() { ensureSell(); build(); }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
