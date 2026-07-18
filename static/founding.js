// RAGNAR — Founding 250 application landing page.
"use strict";
const $ = (id) => document.getElementById(id);
let toastTimer;
function toast(m) { const e = $("toast"); e.textContent = m; e.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => e.classList.remove("show"), 2600); }

async function api(p, o = {}) {
  const r = await fetch(p, { ...o, headers: { "Content-Type": "application/json", ...(o.headers || {}) } });
  let d = null; try { d = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error((d && (d.detail || d.error)) || `Request failed (${r.status})`);
  return d;
}

async function loadStatus() {
  try {
    const s = await api("/api/founding/status");
    $("claimed").textContent = s.claimed;
    $("cap").textContent = s.cap;
    if (s.remaining <= 0) $("counter").innerHTML = "Founding roster full — join the waitlist";
  } catch (_) {}
}

async function submitApplication(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = {
    name: fd.get("name"),
    email: fd.get("email"),
    handle_wanted: fd.get("handle_wanted") || null,
    monthly_volume: fd.get("monthly_volume") || null,
    categories: fd.get("categories") || null,
    current_platforms: fd.get("current_platforms") || null,
    message: fd.get("message") || null,
  };
  const st = $("formStatus"); st.className = "form-status"; st.textContent = "Submitting…";
  try {
    await api("/api/founding/apply", { method: "POST", body: JSON.stringify(payload) });
    $("apply").hidden = true;
    $("successBox").hidden = false;
    $("successBox").scrollIntoView({ behavior: "smooth", block: "center" });
    toast("Application received!");
  } catch (err) {
    st.className = "form-status error"; st.textContent = err.message;
  }
}

async function reflectAccount() {
  try {
    const me = await api("/api/auth/me");
    const el = $("acctLink");
    if (el && me.user) { el.textContent = me.user.is_staff ? "Command Hub" : "My account"; el.href = me.user.is_staff ? "/admin" : "/account"; }
  } catch (_) {}
}

document.addEventListener("DOMContentLoaded", () => {
  loadStatus();
  reflectAccount();
  $("applyForm").addEventListener("submit", submitApplication);
});
