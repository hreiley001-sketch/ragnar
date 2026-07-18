// RAGNAR / BirdmanOS — live ride (auction rollercoaster) client.
"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const RIDE_ID = decodeURIComponent(location.pathname.split("/ride/")[1] || "").replace(/\/$/, "");
const PHASES = ["lobby", "showcase", "bidding", "cooldown"];
const CREST = `<svg viewBox="0 0 120 80" xmlns="http://www.w3.org/2000/svg" style="width:60%;opacity:.3"><g fill="#7fa8c9"><path d="M60 24 L48 30 L44 44 L52 42 L48 54 L60 66 L72 54 L68 42 L76 44 L72 30 Z"/></g></svg>`;

let toastTimer, localLeft = null, timerInt = null, lastState = null;
function toast(m) { const e = $("toast"); e.textContent = m; e.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => e.classList.remove("show"), 2600); }

async function api(p, o = {}) {
  const r = await fetch(p, { ...o, headers: { "Content-Type": "application/json", ...(o.headers || {}) } });
  let d = null; try { d = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error((d && (d.detail || d.error)) || `Request failed (${r.status})`);
  return d;
}

function renderTrack(state) {
  const idx = PHASES.indexOf(state.current_phase);
  $("track").innerHTML = PHASES.map((p, i) => {
    const cls = state.status === "archived" ? "done" : (i === idx ? "active" : (i < idx ? "done" : ""));
    return `<div class="stop ${cls}">${cls === "active" ? '<span class="cart">🎢</span>' : ""}${esc(p)}</div>`;
  }).join("");
}

function applyState(s) {
  lastState = s;
  $("rideTitle").textContent = s.title;
  $("phaseName").textContent = (s.status || "").toUpperCase();
  renderTrack(s);

  // card
  const l = s.listing;
  if (l) {
    $("cardImg").src = l.image_url || "";
    if (!l.image_url) $("cardImg").outerHTML = `<div class="cardimg" style="display:grid;place-items:center">${CREST}</div>`;
    $("cardTitle").textContent = l.title;
    const grade = l.grading_company ? `${l.grading_company} ${l.grade}` : (l.condition || "");
    $("cardSub").textContent = [l.category, grade].filter(Boolean).join(" · ");
  } else {
    $("cardTitle").textContent = s.title;
  }
  $("marketPrice").textContent = money(s.market_price);

  // bidding
  $("currentBid").textContent = s.current_bid != null ? money(s.current_bid) : money(s.starting_bid) + " (start)";
  $("currentBidder").textContent = s.current_bidder ? `High bidder: ${s.current_bidder}` : "No bids yet";
  $("minBid").textContent = money(s.min_next_bid);
  if (!$("bidAmount").value) $("bidAmount").value = Math.ceil(s.min_next_bid);
  $("viewers").textContent = `👁 ${s.viewer_count}`;

  const biddingOpen = s.status === "bidding";
  $("bidControls").style.display = biddingOpen ? "" : "none";
  $("biddingClosed").hidden = biddingOpen;

  // winner
  if (s.status === "archived") {
    $("winnerBox").hidden = false;
    $("winnerBox").innerHTML = s.winner
      ? `🏆 SOLD to <b>${esc(s.winner)}</b> for ${money(s.current_bid)}${s.market_price ? ` · market est. ${money(s.market_price)}` : ""}`
      : "Ride ended — reserve not met, no sale.";
    $("phaseName").textContent = "ENDED";
    $("countdown").textContent = "—";
    stopTimer();
  }

  // countdown sync
  if (s.seconds_left != null && s.status !== "archived") { localLeft = s.seconds_left; startTimer(); }
}

function startTimer() {
  if (timerInt) return;
  timerInt = setInterval(() => {
    if (localLeft == null) return;
    localLeft = Math.max(0, localLeft - 1);
    const m = Math.floor(localLeft / 60), sec = localLeft % 60;
    $("countdown").textContent = `${m}:${String(sec).padStart(2, "0")}`;
  }, 1000);
}
function stopTimer() { clearInterval(timerInt); timerInt = null; }

function addFeed(type, data, at) {
  const label = {
    ride_phase_changed: `➡️ Phase: <b>${esc(data.phase || "")}</b>`,
    bid_placed: `💰 <b>${esc(data.bidder)}</b> bid ${money(data.amount)}`,
    user_joined_ride: `👋 A car entered (${data.viewer_count} watching)`,
    market_price_fetched: `📊 Market est. ${money(data.market_price)}`,
    bidding_open: `🟢 Bidding is OPEN`,
    ride_tuned: `⚙️ Tuned: ${esc(data.reason)}${data.extended_sec ? ` (+${data.extended_sec}s)` : ""}`,
    payment_captured: `✅ Payment captured — ${esc(data.winner)} ${money(data.amount)}`,
    ride_complete: data.winner ? `🏁 Complete — winner ${esc(data.winner)} at ${money(data.final_price)}` : `🏁 Complete — no sale`,
    lobby_open: `🚪 Lobby open`,
    cooldown_open: `❄️ Cooldown`,
  }[type] || `• ${esc(type)}`;
  const el = document.createElement("div");
  el.className = "feed-item";
  el.innerHTML = label;
  $("feed").prepend(el);
}

async function placeBid() {
  const bidder = $("bidderName").value.trim();
  const amount = parseFloat($("bidAmount").value);
  if (!bidder) { toast("Enter your name to bid."); return; }
  if (!amount) { toast("Enter a bid amount."); return; }
  $("bidStatus").className = "form-status"; $("bidStatus").textContent = "Placing…";
  try {
    const r = await api(`/api/rides/${RIDE_ID}/bid`, { method: "POST", body: JSON.stringify({ bidder, amount }) });
    $("bidStatus").className = "form-status ok"; $("bidStatus").textContent = `You're the high bidder at ${money(r.current_bid)}!`;
    $("bidAmount").value = Math.ceil(r.min_next_bid);
  } catch (e) { $("bidStatus").className = "form-status error"; $("bidStatus").textContent = e.message; }
}

function connectSSE() {
  const es = new EventSource(`/api/rides/${RIDE_ID}/events`);
  es.onmessage = (m) => {
    try {
      const msg = JSON.parse(m.data);
      if (msg.kind === "state") applyState(msg.state);
      else if (msg.kind === "event") addFeed(msg.type, msg.data || {}, msg.at);
      else if (msg.kind === "error") { es.close(); pollFallback(); }
    } catch (_) {}
  };
  es.onerror = () => { es.close(); pollFallback(); };
}
function pollFallback() {
  const load = async () => {
    try {
      const s = await api(`/api/rides/${RIDE_ID}/state`);
      (s.events || []).forEach((e) => {});
      applyState(s);
    } catch (_) {}
  };
  load(); setInterval(load, 3000);
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!RIDE_ID) { document.body.innerHTML = "<p style='padding:40px'>No ride specified.</p>"; return; }
  $("bidBtn").addEventListener("click", placeBid);
  try { await api(`/api/rides/${RIDE_ID}/join`, { method: "POST" }); } catch (_) {}
  try { applyState(await api(`/api/rides/${RIDE_ID}/state`)); } catch (e) { toast(e.message); }
  if ("EventSource" in window) connectSSE(); else pollFallback();
});
