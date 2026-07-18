// RAGNAR — sign in / sign up.
"use strict";
const $ = (id) => document.getElementById(id);
let mode = "login";

async function api(p, o = {}) {
  const r = await fetch(p, { ...o, headers: { "Content-Type": "application/json", ...(o.headers || {}) } });
  let d = null; try { d = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error((d && (d.detail || d.error)) || `Request failed (${r.status})`);
  return d;
}

function setMode(m) {
  mode = m;
  document.querySelectorAll(".auth-tab").forEach((t) => t.classList.toggle("active", t.dataset.mode === m));
  $("nameField").hidden = m !== "signup";
  $("authForm").querySelector("button[type=submit]").textContent = m === "signup" ? "Create account" : "Log in";
}

async function submit(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = { email: fd.get("email"), password: fd.get("password") };
  if (mode === "signup") body.name = fd.get("name") || null;
  const st = $("authStatus"); st.className = "form-status"; st.textContent = "…";
  try {
    const u = await api(`/api/auth/${mode === "signup" ? "signup" : "login"}`, { method: "POST", body: JSON.stringify(body) });
    st.className = "form-status ok"; st.textContent = "Welcome!";
    location.href = u.is_staff ? "/admin" : "/account";
  } catch (err) { st.className = "form-status error"; st.textContent = err.message; }
}

document.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll(".auth-tab").forEach((t) => t.addEventListener("click", () => setMode(t.dataset.mode)));
  $("authForm").addEventListener("submit", submit);
  // If Google isn't configured, dim the button with a hint.
  try {
    const me = await api("/api/auth/me");
    if (me.user) { location.href = me.user.is_staff ? "/admin" : "/account"; return; }
    if (!me.google_enabled) {
      const g = $("googleBtn");
      g.addEventListener("click", (e) => { e.preventDefault(); $("authStatus").className = "form-status"; $("authStatus").textContent = "Google sign-in isn't configured yet — use email for now."; });
      g.style.opacity = ".6";
    }
  } catch (_) {}
});
