/**
 * RAGNAR client (Birdman spine) — shared fetch + v1 marketplace surface.
 * Product = RAGNAR. Organism nickname = Birdman. Loaded before page scripts.
 */
"use strict";

(function (global) {
  const API_ROOT = "";

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body && !headers["Content-Type"] && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }
    const res = await fetch(API_ROOT + path, {
      credentials: "same-origin",
      ...options,
      headers,
    });
    let data = null;
    try {
      data = await res.json();
    } catch (_) {}
    if (!res.ok) {
      const detail = data && (data.detail || data.error);
      throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
    }
    return data;
  }

  async function browseListings(params = {}) {
    const p = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== "" && v != null && v !== false) p.set(k, String(v));
    });
    const qs = p.toString();
    try {
      return await api(`/api/v1/marketplace/browse${qs ? `?${qs}` : ""}`);
    } catch (_) {
      return api(`/api/listings${qs ? `?${qs}` : ""}`);
    }
  }

  async function me() {
    try {
      return await api("/api/v1/users/me");
    } catch (_) {
      return api("/api/auth/me");
    }
  }

  async function pulse() {
    try {
      return await api("/api/v1/marketplace/pulse");
    } catch (_) {
      try {
        return await api("/api/v1/realtime/pulse");
      } catch (__) {
        return api("/api/platform/status");
      }
    }
  }

  async function siteContent() {
    try {
      const item = await api("/api/v1/content/site");
      return item && item.data ? item.data : item;
    } catch (_) {
      return api("/api/site-config");
    }
  }

  global.Birdman = {
    api,
    browseListings,
    me,
    pulse,
    siteContent,
    product: "ragnar",
    organism: "birdman",
    version: 2,
  };
  global.Ragnar = global.Birdman;
})(typeof window !== "undefined" ? window : globalThis);
