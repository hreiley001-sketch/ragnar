// RAGNAR — shared fetch helpers used by every storefront page.
// Load before page scripts: <script src="/static/api.js"></script>
"use strict";

(function (global) {
  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function money(n) {
    return n == null
      ? "—"
      : "$" + Number(n).toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
  }

  // Shared placeholder crest used on listing/store cards when no photo exists.
  const CREST =
    `<svg class="placeholder-crest" viewBox="0 0 120 80" xmlns="http://www.w3.org/2000/svg"><g fill="var(--crest-primary)"><path d="M60 30 L18 20 L30 27 L14 26 L28 33 L16 34 L30 40 L60 40 Z"/><path d="M60 30 L102 20 L90 27 L106 26 L92 33 L104 34 L90 40 L60 40 Z"/><path d="M60 24 L48 30 L44 44 L52 42 L48 54 L60 66 L72 54 L68 42 L76 44 L72 30 Z"/></g><g fill="var(--crest-accent)"><circle cx="55" cy="42" r="1.8"/><circle cx="65" cy="42" r="1.8"/></g></svg>`;

  function accentGrad(color) {
    const c = color || "var(--color-accent-fallback)";
    return `linear-gradient(135deg, color-mix(in srgb, ${c} 24%, transparent), var(--color-bg-base)), radial-gradient(circle at 30% 20%, color-mix(in srgb, ${c} 38%, transparent), transparent 60%)`;
  }

  function errorDetail(data, status) {
    const detail = data && (data.detail || data.error);
    if (typeof detail === "string" && detail) return detail;
    return `Request failed (${status})`;
  }

  async function api(path, options = {}) {
    const opts = { ...options };
    const headers = { ...(opts.headers || {}) };
    const body = opts.body;
    const isForm =
      typeof FormData !== "undefined" && body instanceof FormData;
    if (!isForm && body != null && !headers["Content-Type"] && !headers["content-type"]) {
      headers["Content-Type"] = "application/json";
    }
    opts.headers = headers;

    const res = await fetch(path, opts);
    let data = null;
    try {
      data = await res.json();
    } catch (_) {}
    if (!res.ok) {
      const err = new Error(errorDetail(data, res.status));
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function apiForm(path, formData, options = {}) {
    return api(path, { method: "POST", ...options, body: formData });
  }

  const Ragnar = {
    api,
    apiForm,
    $,
    money,
    escapeHtml,
    esc: escapeHtml,
    CREST,
    accentGrad,
  };
  global.Ragnar = Ragnar;
  // Convenience globals — page scripts may alias or use these directly.
  global.api = api;
  global.apiForm = apiForm;
})(typeof window !== "undefined" ? window : globalThis);
