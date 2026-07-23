// RAGNAR Dispatch — AI shipping agent UX.
"use strict";

(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  let convId = localStorage.getItem("ragnar_dispatch_id") || null;
  let busy = false;

  const DEFAULT_CHIPS = [
    "Orders to ship",
    "Create a label",
    "Quote shipping rates",
    "How should I pack a slab?",
    "Talk to a human",
  ];

  function setRail(data) {
    const status = (data.status || "open").replace(/_/g, " ");
    const intent = (data.intent || "—").replace(/_/g, " ");
    const conf = data.confidence != null ? Math.round(data.confidence * 100) + "%" : "—";
    const order = data.order_id != null ? "#" + data.order_id
      : (data.entities && data.entities.order_id ? "#" + data.entities.order_id : "—");

    $("railStatus").textContent = status;
    $("railStatus").className = "";
    if (/escalat|pending review/i.test(status)) $("railStatus").classList.add("escalated");
    else if (/resolv|closed/i.test(status)) $("railStatus").classList.add("resolved");
    else if (/workflow|in /i.test(status)) $("railStatus").classList.add("acting");
    else $("railStatus").classList.add("listening");

    $("railIntent").textContent = intent;
    $("railConf").textContent = conf;
    $("railOrder").textContent = order;
    $("dispatchCaseId").textContent = data.id || data.conversation_id || convId || "—";

    if (/escalat/i.test(status)) {
      $("railHeadline").textContent = "With a human reviewer";
      $("railCopy").textContent = "Dispatch gathered tracking and packaging facts, then queued this for review.";
    } else if (/resolv/i.test(status)) {
      $("railHeadline").textContent = "Pipeline step done";
      $("railCopy").textContent = "Label, tracking, or advice is recorded. Check My Store / Account for updates.";
    } else if (data.intent && data.intent !== "greeting") {
      $("railHeadline").textContent = "Working the shipment";
      $("railCopy").textContent = "Rate shopping, packing, or label purchase in progress.";
    } else {
      $("railHeadline").textContent = "Ready to fulfill";
      $("railCopy").textContent = "Dispatch owns quote → pack → label → track. Every decision shows here.";
    }
  }

  function renderChips(list) {
    const box = $("dispatchIntents");
    box.innerHTML = "";
    (list || DEFAULT_CHIPS).forEach((t) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "counsel-intent";
      b.textContent = t;
      b.addEventListener("click", () => {
        $("dispatchInput").value = t;
        send();
      });
      box.appendChild(b);
    });
  }

  function receiptHtml(workflow) {
    if (!workflow) return "";
    const decision = workflow.decision || (workflow.policy && workflow.policy.decision);
    const order = workflow.order || (workflow.quote && workflow.quote.order) || {};
    const label = workflow.label || {};
    const rec = (workflow.quote && workflow.quote.recommended) || {};
    const pack = workflow.packaging || (workflow.quote && workflow.quote.packaging) || {};
    const tracking = workflow.tracking || {};
    const rows = [];

    if (decision) {
      const cls = decision === "approve" || decision === "inform" ? "ok"
        : decision === "escalate" ? "warn" : decision === "deny" ? "bad" : "";
      rows.push(`<div class="cx-receipt-row"><span>Decision</span><strong class="${cls}">${esc(decision)}</strong></div>`);
    }
    if (order.id) {
      rows.push(`<div class="cx-receipt-row"><span>Order</span><strong>#${esc(order.id)} · ${esc(order.status || "")}</strong></div>`);
    }
    if (rec.provider) {
      rows.push(`<div class="cx-receipt-row"><span>Rate</span><strong>${esc(rec.provider)} ${esc(rec.service || "")} · $${esc(rec.amount)}</strong></div>`);
    }
    if (pack.label) {
      rows.push(`<div class="cx-receipt-row"><span>Pack</span><strong>${esc(pack.label)}</strong></div>`);
    }
    if (label.label_id) {
      rows.push(`<div class="cx-receipt-row"><span>Label</span><strong>${esc(label.label_id)}</strong></div>`);
    }
    if (label.tracking_number || tracking.tracking_number) {
      rows.push(`<div class="cx-receipt-row"><span>Tracking</span><strong>${esc(label.tracking_number || tracking.tracking_number)}</strong></div>`);
    }
    if ((workflow.to_ship || []).length) {
      rows.push(`<div class="cx-receipt-row"><span>Queue</span><strong>${workflow.to_ship.length} to ship</strong></div>`);
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
    return `<div class="cx-receipt"><div class="cx-receipt-label">Shipment record</div>
      <div class="cx-receipt-rows">${rows.join("")}</div>${strip}</div>`;
  }

  function formatBody(body) {
    // Light markdown: **bold** and newlines.
    let html = esc(body);
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\n/g, "<br>");
    return html;
  }

  function addMsg(body, who, extra) {
    const wrap = document.createElement("div");
    wrap.className = "cx-msg" + (who === "me" ? " me" : "");
    const meta = who === "me" ? "You" : "Dispatch";
    wrap.innerHTML = `
      <div class="cx-meta">${meta}</div>
      <div class="cx-bubble">${formatBody(body)}${extra || ""}</div>`;
    $("dispatchFeed").appendChild(wrap);
    $("dispatchFeed").scrollTop = $("dispatchFeed").scrollHeight;
    return wrap;
  }

  function showTyping() {
    const el = document.createElement("div");
    el.className = "cx-msg";
    el.id = "dispatchTyping";
    el.innerHTML = `<div class="cx-meta">Dispatch</div><div class="cx-typing" aria-label="Thinking"><span></span><span></span><span></span></div>`;
    $("dispatchFeed").appendChild(el);
    $("dispatchFeed").scrollTop = $("dispatchFeed").scrollHeight;
  }
  function hideTyping() {
    $("dispatchTyping")?.remove();
  }

  async function ensureConv() {
    if (convId) {
      try {
        const r = await fetch(`/api/shipping/conversations/${encodeURIComponent(convId)}`);
        if (r.ok) return await r.json();
      } catch (_) {}
      convId = null;
      localStorage.removeItem("ragnar_dispatch_id");
    }
    const r = await fetch("/api/shipping/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel: "web" }),
    });
    const data = await r.json();
    convId = data.id;
    localStorage.setItem("ragnar_dispatch_id", convId);
    return data;
  }

  async function bootstrap() {
    try {
      const data = await ensureConv();
      $("dispatchFeed").innerHTML = "";
      (data.messages || []).forEach((m) => {
        addMsg(m.body, m.role === "user" ? "me" : "bot");
      });
      if (!(data.messages || []).length && data.reply) addMsg(data.reply, "bot");
      renderChips(data.chips || DEFAULT_CHIPS);
      setRail(data);
    } catch (_) {
      addMsg("Dispatch is warming up — refresh in a moment.", "bot");
    }
  }

  async function send(preset) {
    if (busy) return;
    const input = $("dispatchInput");
    const text = (preset || input.value || "").trim();
    if (!text) return;
    input.value = "";
    busy = true;
    $("dispatchSend").disabled = true;
    addMsg(text, "me");
    showTyping();
    try {
      await ensureConv();
      const r = await fetch("/api/shipping/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, conversation_id: convId }),
      });
      const data = await r.json();
      hideTyping();
      if (data.id) {
        convId = data.id;
        localStorage.setItem("ragnar_dispatch_id", convId);
      }
      const extra = receiptHtml(data.workflow);
      addMsg(data.reply || "Done.", "bot", extra);
      renderChips(data.chips || DEFAULT_CHIPS);
      setRail(data);
    } catch (err) {
      hideTyping();
      addMsg("Something went wrong talking to Dispatch. Try again.", "bot");
    } finally {
      busy = false;
      $("dispatchSend").disabled = false;
      $("dispatchInput").focus();
    }
  }

  $("dispatchSend")?.addEventListener("click", () => send());
  $("dispatchInput")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); send(); }
  });
  $("dispatchStart")?.addEventListener("click", () => {
    $("dispatchInput")?.focus();
    $("dispatchStage")?.scrollIntoView({ behavior: "smooth", block: "center" });
  });
  $("dispatchToShip")?.addEventListener("click", () => send("Orders to ship"));
  $("dispatchLanes")?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-prompt]");
    if (!btn) return;
    send(btn.getAttribute("data-prompt"));
  });

  bootstrap();
})();
