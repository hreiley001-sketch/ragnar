// RAGNAR — legal acceptance + AI identity verification.
"use strict";
const $ = (id) => document.getElementById(id);

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { ...(opts.headers || {}) } });
  let d = null;
  try { d = await r.json(); } catch (_) {}
  if (!r.ok) {
    const detail = d && (d.detail || d.error);
    throw new Error(typeof detail === "string" ? detail : `Request failed (${r.status})`);
  }
  return d;
}

function pill(status) {
  const map = {
    approved: ["ok", "Verified"],
    pending: ["warn", "Pending review"],
    rejected: ["bad", "Rejected — try again"],
    banned: ["bad", "Banned"],
    none: ["", "Not started"],
  };
  const [cls, label] = map[status] || ["", status || "unknown"];
  return `<span class="id-status-pill ${cls}">${label}</span>`;
}

function preview(input, img) {
  input.addEventListener("change", () => {
    const f = input.files && input.files[0];
    if (!f) { img.style.display = "none"; img.removeAttribute("src"); return; }
    img.src = URL.createObjectURL(f);
    img.style.display = "block";
  });
}

function show(el, on) { el.hidden = !on; }

async function boot() {
  let data;
  try {
    data = await api("/api/auth/identity");
  } catch (e) {
    location.href = "/login?next=/identity";
    return;
  }
  const u = data.user;
  $("statusLine").innerHTML = `Signed in as <strong>${u.email}</strong> · ${pill(u.identity_status)}`;

  if (u.banned) {
    show($("legalStep"), false);
    show($("idStep"), false);
    show($("doneStep"), true);
    $("doneMsg").textContent = "This account is banned and cannot complete verification.";
    return;
  }

  if (u.needs_legal) {
    show($("legalStep"), true);
    show($("idStep"), false);
    show($("doneStep"), false);
  } else if (u.identity_status === "approved") {
    show($("legalStep"), false);
    show($("idStep"), false);
    show($("doneStep"), true);
    $("doneMsg").textContent = "Identity verified. You can sell and use high-trust features.";
  } else if (u.identity_status === "pending") {
    show($("legalStep"), false);
    show($("idStep"), false);
    show($("doneStep"), true);
    $("doneMsg").textContent = "Your ID is under staff review. You can browse meanwhile — selling unlocks when approved.";
  } else {
    show($("legalStep"), false);
    show($("idStep"), true);
    show($("doneStep"), false);
    if (u.identity_status === "rejected" && u.identity_reject_reason) {
      $("idStatus").className = "form-status error";
      $("idStatus").textContent = u.identity_reject_reason;
    }
  }

  $("acceptLegalBtn").addEventListener("click", async () => {
    const st = $("legalStatus");
    st.className = "form-status";
    if (!$("legTerms").checked || !$("legPrivacy").checked || !$("legPolicies").checked) {
      st.className = "form-status error";
      st.textContent = "Please check all three boxes.";
      return;
    }
    st.textContent = "Saving…";
    try {
      await api("/api/auth/accept-legal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          accept_terms: true,
          accept_privacy: true,
          accept_policies: true,
        }),
      });
      show($("legalStep"), false);
      show($("idStep"), true);
      st.textContent = "";
    } catch (err) {
      st.className = "form-status error";
      st.textContent = err.message;
    }
  });

  preview($("idFront"), $("idFrontPreview"));
  preview($("idSelfie"), $("idSelfiePreview"));

  $("idForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const st = $("idStatus");
    st.className = "form-status";
    const front = $("idFront").files && $("idFront").files[0];
    if (!front) {
      st.className = "form-status error";
      st.textContent = "Upload a government ID photo.";
      return;
    }
    st.textContent = "Running AI ID check… this can take a few seconds.";
    const fd = new FormData();
    fd.append("id_front", front);
    const selfie = $("idSelfie").files && $("idSelfie").files[0];
    if (selfie) fd.append("selfie", selfie);
    try {
      const r = await api("/api/auth/identity/submit", { method: "POST", body: fd });
      $("statusLine").innerHTML = `Signed in as <strong>${r.user.email}</strong> · ${pill(r.status)}`;
      if (r.status === "approved") {
        show($("idStep"), false);
        show($("doneStep"), true);
        $("doneMsg").textContent = "AI verified your ID. Selling is unlocked.";
      } else if (r.status === "pending") {
        show($("idStep"), false);
        show($("doneStep"), true);
        $("doneMsg").textContent = r.notes || "Submitted for staff review. We’ll unlock selling once approved.";
      } else {
        st.className = "form-status error";
        st.textContent = r.notes || "Could not verify. Try a clearer photo of a government ID.";
      }
    } catch (err) {
      st.className = "form-status error";
      st.textContent = err.message;
    }
  });
}

document.addEventListener("DOMContentLoaded", boot);
