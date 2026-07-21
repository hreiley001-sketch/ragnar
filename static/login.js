// RAGNAR — sign in / sign up with email verification + password reset.
"use strict";
const $ = window.Ragnar.$;
let mode = "login";
let resetToken = "";

function hideChromeForSpecial() {
  const tabs = document.querySelector(".auth-tabs");
  const divider = document.querySelector(".divider");
  const google = $("googleBtn");
  const note = document.querySelector(".staff-note");
  if (tabs) tabs.hidden = true;
  if (divider) divider.hidden = true;
  if (google) google.hidden = true;
  if (note) note.hidden = true;
}

function showLoginChrome() {
  const tabs = document.querySelector(".auth-tabs");
  const divider = document.querySelector(".divider");
  const google = $("googleBtn");
  const note = document.querySelector(".staff-note");
  if (tabs) tabs.hidden = false;
  if (divider) divider.hidden = false;
  if (google) google.hidden = false;
  if (note) note.hidden = false;
  $("authForm").hidden = false;
  $("forgotForm").hidden = true;
  $("resetForm").hidden = true;
  $("verifySent").hidden = true;
  setMode("login");
}

function showForgot() {
  hideChromeForSpecial();
  $("authForm").hidden = true;
  $("forgotForm").hidden = false;
  $("resetForm").hidden = true;
  $("forgotStatus").className = "form-status";
  $("forgotStatus").textContent = "";
}

function showReset(token) {
  resetToken = token;
  hideChromeForSpecial();
  $("authForm").hidden = true;
  $("forgotForm").hidden = true;
  $("resetForm").hidden = false;
  $("resetStatus").className = "form-status";
  $("resetStatus").textContent = "";
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
  $("forgotWrap").hidden = signup;
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

async function submitForgot(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const st = $("forgotStatus");
  st.className = "form-status";
  st.textContent = "Sending…";
  try {
    const r = await api("/api/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email: fd.get("email") }),
    });
    st.className = "form-status ok";
    st.textContent = r.message || "If an account exists for that email, a reset link has been sent.";
  } catch (err) {
    st.className = "form-status error";
    st.textContent = err.message;
  }
}

async function submitReset(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const st = $("resetStatus");
  st.className = "form-status";
  const password = fd.get("password") || "";
  const confirm = fd.get("confirm") || "";
  if (password !== confirm) {
    st.className = "form-status error";
    st.textContent = "Passwords don't match.";
    return;
  }
  st.textContent = "Updating password…";
  try {
    const r = await api("/api/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token: resetToken, password }),
    });
    st.className = "form-status ok";
    st.textContent = "Password updated. Redirecting…";
    setTimeout(() => {
      location.href = (r.user && r.user.is_staff) ? "/admin" : "/account";
    }, 600);
  } catch (err) {
    st.className = "form-status error";
    st.textContent = err.message;
  }
}

async function resend() {
  const b = $("resendBtn"); b.disabled = true; b.textContent = "Sending…";
  try { const r = await api("/api/auth/resend-verification", { method: "POST" }); b.textContent = r.sent ? "Sent again ✓" : "Email not configured"; }
  catch (e) { b.textContent = e.message; b.disabled = false; }
}

document.addEventListener("DOMContentLoaded", async () => {
  const params = new URLSearchParams(location.search);
  const token = (params.get("reset") || "").trim();

  setMode("login");
  document.querySelectorAll(".auth-tab").forEach((t) => t.addEventListener("click", () => setMode(t.dataset.mode)));
  $("authForm").addEventListener("submit", submit);
  $("forgotForm").addEventListener("submit", submitForgot);
  $("resetForm").addEventListener("submit", submitReset);
  $("forgotLink").addEventListener("click", showForgot);
  $("forgotBack").addEventListener("click", showLoginChrome);
  $("pw").addEventListener("input", paintMeter);
  $("resendBtn").addEventListener("click", resend);

  if (token) {
    showReset(token);
    history.replaceState({}, "", "/login");
  }

  try {
    const me = await api("/api/auth/me");
    if (me.user && !token) { location.href = me.user.is_staff ? "/admin" : "/account"; return; }
    if (!me.google_enabled) {
      const g = $("googleBtn");
      g.addEventListener("click", (e) => { e.preventDefault(); $("authStatus").className = "form-status"; $("authStatus").textContent = "Google sign-in isn't configured yet — use email for now."; });
      g.style.opacity = ".6";
    }
  } catch (_) {}
});
