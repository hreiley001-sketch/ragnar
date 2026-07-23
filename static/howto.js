// RAGNAR — sitewide "How it works" onboarding band.
// Injected by nav.js. Makes listing + using the site obvious on every content
// page. Dismissible (remembered in localStorage). Ensures sell.js is loaded so
// the "List a card" CTA always opens the sell drawer.
"use strict";
(function () {
  const path = (location.pathname.replace(/\/+$/, "") || "/");

  // Pages that should NOT show the band.
  const SKIP = new Set(["/login", "/verify", "/admin", "/ai-tools"]);
  if (SKIP.has(path)) return;
  if (document.body.classList.contains("premium-room")) return;      // live room = focus mode
  if (localStorage.getItem("ragnar_howto_dismissed") === "1") return;

  // Which flow to emphasise on this page.
  const sellFocus = ["/", "/mystore", "/account"].includes(path);

  function ensureSell() {
    const has = Array.prototype.some.call(document.scripts, (s) => /\/static\/sell\.js/.test(s.src || ""));
    if (!has) {
      const s = document.createElement("script");
      s.src = "/static/sell.js";
      document.body.appendChild(s);
    }
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
        <div class="howto-col" data-focus="${sellFocus ? 0 : 1}">
          <h3>🛒 Buying</h3>
          <ol>
            <li><b>Search or ask.</b> Type a card, or tap <b>Ask RAGNAR</b> (bottom-right) to search in plain language.</li>
            <li><b>Buy Now or make an offer.</b> Every listing shows real sold-price history.</li>
            <li><b>Secure checkout.</b> Per-seller checkout with buyer protection — all fees shown up front.</li>
          </ol>
        </div>
        <div class="howto-col" data-focus="${sellFocus ? 1 : 0}">
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

    // Insert right after the page hero (or at the top of main / after header).
    const hero = document.querySelector(".mkt-hero, .platform-hero, .home-hero, .counsel-hero");
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

    band.querySelector(".howto-x").addEventListener("click", () => {
      localStorage.setItem("ragnar_howto_dismissed", "1");
      band.remove();
    });
  }

  function init() { ensureSell(); build(); }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
