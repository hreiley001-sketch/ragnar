// RAGNAR — sign in / sign up with email verification.
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
  const signup = m === "signup";
  document.querySelectorAll(".auth-tab").forEach((t) => t.classList.toggle("active", t.dataset.mode === m));
  $("nameField").hidden = !signup;
  $("confirmField").hidden = !signup;
  $("termsRow").hidden = !signup;
  $("mktRow").hidden = !signup;
  $("pwMeter").hidden = !signup;
  $("authForm").querySelector("button[type=submit]").textContent = signup ? "Create account" : "Log in";
  $("authStatus").textContent = "";
}

function scorePw(pw) {
  let s = 0;
  if (pw.length >= 8) s++;
  if (pw.length >= 12) s++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) s++;
  if (/\d/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  return Math.min(s, 4);
}
function paintMeter() {
  if (mode !== "signup") return;
  const s = scorePw($("pw").value);
  const bar = $("pwBar");
  bar.className = `pw-bar pw-strength-${s}`;
}

async function submit(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const st = $("authStatus"); st.className = "form-status";
  if (mode === "login") {
    st.textContent = "Signing in…";
    try {
      const u = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ email: fd.get("email"), password: fd.get("password") }) });
      location.href = u.is_staff ? "/admin" : "/account";
    } catch (err) { st.className = "form-status error"; st.textContent = err.message; }
    return;
  }
  // signup
  const password = fd.get("password") || "";
  if (password !== ($("confirmField").querySelector("input").value || "")) {
    st.className = "form-status error"; st.textContent = "Passwords don't match."; return;
  }
  if (!$("terms").checked) { st.className = "form-status error"; st.textContent = "Please accept the Terms."; return; }
  st.textContent = "Creating your account…";
  try {
    const u = await api("/api/auth/signup", { method: "POST", body: JSON.stringify({
      name: fd.get("name"), email: fd.get("email"), password,
      accept_terms: true, marketing_opt_in: $("mkt").checked,
    }) });
    // Show verify-email panel
    $("authForm").hidden = true;
    document.querySelector(".auth-tabs").hidden = true;
    document.querySelector(".divider").hidden = true;
    $("googleBtn").hidden = true;
    $("verifySent").hidden = false;
    const staffLine = u.staff_domain ? " Verifying your @ragnarips.com email also unlocks the Command Hub." : "";
    $("verifyMsg").innerHTML = u.verification_email_sent
      ? `We sent a verification link to <strong>${u.email}</strong>.${staffLine}`
      : `Your account is created.${staffLine} <span style="color:var(--gold)">Email delivery isn't set up yet — an admin can verify you, or use Google sign-in.</span>`;
    if (!u.verification_email_sent) $("resendBtn").hidden = true;
  } catch (err) { st.className = "form-status error"; st.textContent = err.message; }
}

async function resend() {
  const b = $("resendBtn"); b.disabled = true; b.textContent = "Sending…";
  try { const r = await api("/api/auth/resend-verification", { method: "POST" }); b.textContent = r.sent ? "Sent again ✓" : "Email not configured"; }
  catch (e) { b.textContent = e.message; b.disabled = false; }
}

document.addEventListener("DOMContentLoaded", async () => {
  setMode("login");
  document.querySelectorAll(".auth-tab").forEach((t) => t.addEventListener("click", () => setMode(t.dataset.mode)));
  $("authForm").addEventListener("submit", submit);
  $("pw").addEventListener("input", paintMeter);
  $("resendBtn").addEventListener("click", resend);
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
