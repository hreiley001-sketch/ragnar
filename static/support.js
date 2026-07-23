// RAGNAR Counsel — full-page support UX.
"use strict";

(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  let convId = localStorage.getItem("ragnar_support_id") || null;
  let accessToken = localStorage.getItem("ragnar_support_token") || null;
  let busy = false;

  function supportHeaders(extra) {
    const h = { "Content-Type": "application/json", ...(extra || {}) };
    if (accessToken) h["X-Support-Token"] = accessToken;
    return h;
  }

  function persistConv(data) {
    if (data && data.id) {
      convId = data.id;
      localStorage.setItem("ragnar_support_id", convId);
    }
    if (data && data.access_token) {
      accessToken = data.access_token;
      localStorage.setItem("ragnar_support_token", accessToken);
    }
  }

  const DEFAULT_CHIPS = [
    "Track my order",
    "I need a refund",
    "Item not received",
    "Cancel my order",
    "Talk to a human",
  ];

  function setRail(data) {
    const status = (data.status || "open").replace(/_/g, " ");
    const intent = (data.intent || "—").replace(/_/g, " ");
    const conf = data.confidence != null ? Math.round(data.confidence * 100) + "%" : "—";
    const order = data.order_id != null ? "#" + data.order_id : (data.entities && data.entities.order_id ? "#" + data.entities.order_id : "—");

    $("railStatus").textContent = status;
    $("railStatus").className = "";
    if (/escalat|pending review/i.test(status)) $("railStatus").classList.add("escalated");
    else if (/resolv|closed/i.test(status)) $("railStatus").classList.add("resolved");
    else if (/workflow|in /i.test(status)) $("railStatus").classList.add("acting");
    else $("railStatus").classList.add("listening");

    $("railIntent").textContent = intent;
    $("railConf").textContent = conf;
    $("railOrder").textContent = order;
    $("counselCaseId").textContent = data.id || data.conversation_id || convId || "—";

    if (/escalat/i.test(status)) {
      $("railHeadline").textContent = "With a human governor";
      $("railCopy").textContent = "Counsel gathered the facts and routed this for review. You’ll get an update in Account.";
    } else if (/resolv/i.test(status)) {
      $("railHeadline").textContent = "Resolved";
      $("railCopy").textContent = "Decision recorded. Check Account → Orders for refunds, labels, and tracking.";
    } else if (data.intent && data.intent !== "greeting") {
      $("railHeadline").textContent = "Working the case";
      $("railCopy").textContent = "Policy-aware reasoning in progress. Clarify if Counsel asks for an order number.";
    } else {
      $("railHeadline").textContent = "Ready when you are";
      $("railCopy").textContent = "Counsel owns intake, policy, and action. You’ll see every decision here.";
    }
  }

  function renderChips(list) {
    const box = $("counselIntents");
    box.innerHTML = "";
    (list || DEFAULT_CHIPS).forEach((t) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "counsel-intent";
      b.textContent = t;
      b.addEventListener("click", () => {
        $("counselInput").value = t;
        send();
      });
      box.appendChild(b);
    });
  }

  function receiptHtml(workflow) {
    if (!workflow) return "";
    const decision = workflow.decision || (workflow.policy && workflow.policy.decision);
    const order = workflow.order || {};
    const refund = workflow.refund || {};
    const label = workflow.return_label || {};
    const policy = workflow.policy || {};
    const rows = [];

    if (decision) {
      const cls = decision === "approve" || decision === "partial" || decision === "inform" ? "ok"
        : decision === "escalate" ? "warn" : decision === "deny" ? "bad" : "";
      rows.push(`<div class="cx-receipt-row"><span>Decision</span><strong class="${cls}">${esc(decision)}</strong></div>`);
    }
    if (order.id) {
      rows.push(`<div class="cx-receipt-row"><span>Order</span><strong>#${esc(order.id)} · ${esc(order.status || "")}</strong></div>`);
    }
    if (refund.amount != null) {
      rows.push(`<div class="cx-receipt-row"><span>Refund</span><strong class="ok">$${Number(refund.amount).toFixed(2)}</strong></div>`);
    }
    if (label.label_id) {
      rows.push(`<div class="cx-receipt-row"><span>Return label</span><strong>${esc(label.label_id)}</strong></div>`);
    }
    if (policy.keep_item) {
      rows.push(`<div class="cx-receipt-row"><span>Return</span><strong>Not required — keep item</strong></div>`);
    }
    if ((workflow.policy_refs || policy.policy_refs || []).length) {
      const refs = (workflow.policy_refs || policy.policy_refs).slice(0, 3).join(", ");
      rows.push(`<div class="cx-receipt-row"><span>Policy</span><strong>${esc(refs)}</strong></div>`);
    }
    if (!rows.length) return "";

    let strip = "";
    if (order.id) {
      strip = `<div class="cx-order-strip">
        <span class="oid">#${esc(order.id)}</span>
        <span class="otitle">${esc(order.title || "Order")}</span>
        <span class="ostatus">${esc(order.status || "")}</span>
      </div>`;
    }
    return `<div class="cx-receipt"><div class="cx-receipt-label">Action record</div>
      <div class="cx-receipt-rows">${rows.join("")}</div>${strip}</div>`;
  }

  function addMsg(body, who, extra) {
    const wrap = document.createElement("div");
    wrap.className = "cx-msg" + (who === "me" ? " me" : "");
    const meta = who === "me" ? "You" : "Counsel";
    wrap.innerHTML = `
      <div class="cx-meta">${meta}</div>
      <div class="cx-bubble">${esc(body)}${extra || ""}</div>`;
    $("counselFeed").appendChild(wrap);
    $("counselFeed").scrollTop = $("counselFeed").scrollHeight;
    return wrap;
  }

  function showTyping() {
    const el = document.createElement("div");
    el.className = "cx-msg";
    el.id = "counselTyping";
    el.innerHTML = `<div class="cx-meta">Counsel</div><div class="cx-typing" aria-label="Thinking"><span></span><span></span><span></span></div>`;
    $("counselFeed").appendChild(el);
    $("counselFeed").scrollTop = $("counselFeed").scrollHeight;
  }
  function hideTyping() {
    $("counselTyping")?.remove();
  }

  async function ensureConv() {
    if (convId) {
      try {
        const r = await fetch(`/api/support/conversations/${encodeURIComponent(convId)}`, {
          headers: supportHeaders(),
        });
        if (r.ok) {
          const data = await r.json();
          persistConv(data);
          return data;
        }
      } catch (_) {}
      convId = null;
      accessToken = null;
      localStorage.removeItem("ragnar_support_id");
      localStorage.removeItem("ragnar_support_token");
    }
    const r = await fetch("/api/support/conversations", {
      method: "POST",
      headers: supportHeaders(),
      body: JSON.stringify({ channel: "web" }),
    });
    const data = await r.json();
    persistConv(data);
    return data;
  }

  async function bootstrap() {
    try {
      const data = await ensureConv();
      $("counselFeed").innerHTML = "";
      (data.messages || []).forEach((m) => {
        addMsg(m.body, m.role === "user" ? "me" : "bot");
      });
      if (!(data.messages || []).length && data.reply) addMsg(data.reply, "bot");
      renderChips(data.chips || DEFAULT_CHIPS);
      setRail(data);
    } catch (_) {
      addMsg("Counsel is warming up — refresh in a moment.", "bot");
    }
  }

  async function send(preset) {
    if (busy) return;
    const input = $("counselInput");
    const text = (preset || input.value || "").trim();
    if (!text) return;
    input.value = "";
    busy = true;
    $("counselSend").disabled = true;
    addMsg(text, "me");
    showTyping();
    try {
      await ensureConv();
      const r = await fetch("/api/support/chat", {
        method: "POST",
        headers: supportHeaders(),
        body: JSON.stringify({ message: text, conversation_id: convId }),
      });
      const data = await r.json();
      hideTyping();
      persistConv(data);
      const extra = receiptHtml(data.workflow);
      addMsg(data.reply || "Done.", "bot", extra);
      renderChips(data.chips || DEFAULT_CHIPS);
      setRail(data);
      if (data.queue || data.decision === "escalate") {
        addMsg(`Case ${data.conversation_id || convId} is in the human review queue.`, "bot");
      }
    } catch (_) {
      hideTyping();
      addMsg("Something went wrong — try again, or say “Talk to a human”.", "bot");
    } finally {
      busy = false;
      $("counselSend").disabled = false;
      input.focus();
    }
  }

  function focusComposer(seed) {
    if (seed) $("counselInput").value = seed;
    $("counselInput").focus();
    $("counselStage").scrollIntoView({ behavior: "smooth", block: "center" });
  }

  $("counselSend").addEventListener("click", () => send());
  $("counselInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });
  $("counselStart").addEventListener("click", () => focusComposer());
  $("counselTrack").addEventListener("click", () => focusComposer("Track order #"));
  document.querySelectorAll(".counsel-lane").forEach((btn) => {
    btn.addEventListener("click", () => {
      const p = btn.getAttribute("data-prompt");
      if (p) send(p);
    });
  });

  // Hide the floating Support FAB on this page — the page IS the counsel surface.
  const hideFab = () => {
    const fab = document.getElementById("fab-support");
    const panel = document.getElementById("panel-support");
    if (fab) fab.style.display = "none";
    if (panel) panel.style.display = "none";
  };
  hideFab();
  setTimeout(hideFab, 200);

  bootstrap();
})();
