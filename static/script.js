/*
  Aura customer UI.
  - Sends {message | action+payload, reply_language, language_mode, tz, via_button} to /chat.
  - Renders reply text, quick replies, date hints and cards ("blocks").
  - All buttons use event delegation (data-act / data-send), so a restored
    chat history stays clickable.
  - The reply language (select) is separate from the speech-recognition
    language (mic select). Voice input fills the box; the user edits and sends.
*/
(function () {
  "use strict";

  const chatWindow = document.getElementById("chat-window");
  const input = document.getElementById("user-input");
  const sendBtn = document.getElementById("send-btn");
  const replySel = document.getElementById("reply-lang-select");
  const micSel = document.getElementById("voice-lang-select");
  const micBtn = document.getElementById("mic-btn");
  const voiceBtn = document.getElementById("voice-reply-btn");
  const hint = document.getElementById("transcript-hint");
  const TZ = (Intl.DateTimeFormat().resolvedOptions().timeZone) || "Asia/Kolkata";

  let S = {};                // UI strings for the current reply language
  let replyLang = "en";      // language the bot is currently replying in
  let busy = false;
  let voiceReply = false;
  const cache = {};

  // ------------------------------------------------------------------ helpers
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const inr = (n) => "₹" + Number(n || 0).toLocaleString("en-IN");
  const fmt = (key, vals) => (S[key] || key).replace(/\{(\w+)\}/g, (_, k) => (vals && vals[k] != null ? vals[k] : ""));
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  function scrollDown() { chatWindow.scrollTop = chatWindow.scrollHeight; }

  async function loadStrings(lang) {
    if (!cache[lang]) {
      try { cache[lang] = (await (await fetch(`/api/i18n/${lang}`)).json()).strings; }
      catch (e) { cache[lang] = cache.en || {}; }
    }
    S = cache[lang];
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach((n) => { if (S[n.dataset.i18n]) n.textContent = S[n.dataset.i18n]; });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((n) => { if (S[n.dataset.i18nPlaceholder]) n.placeholder = S[n.dataset.i18nPlaceholder]; });
    document.querySelectorAll("[data-i18n-title]").forEach((n) => { const v = S[n.dataset.i18nTitle]; if (v) { n.title = v; n.setAttribute("aria-label", v); } });
  }

  // ------------------------------------------------------------------ persistence (per tab)
  function save() {
    try {
      sessionStorage.setItem("aura_chat_html", chatWindow.innerHTML);
      sessionStorage.setItem("aura_reply_lang", replySel.value);
      sessionStorage.setItem("aura_bot_lang", replyLang);
    } catch (e) { /* storage full or disabled: history just won't persist */ }
  }
  function restore() {
    try {
      const html = sessionStorage.getItem("aura_chat_html");
      replySel.value = sessionStorage.getItem("aura_reply_lang") || "auto";
      replyLang = sessionStorage.getItem("aura_bot_lang") || (replySel.value === "auto" ? "en" : replySel.value);
      if (html) { chatWindow.innerHTML = html; if (chatWindow.querySelector(".msg.user")) document.querySelector(".chat-main").classList.add("has-chat"); chatWindow.querySelectorAll(".quick-reply-bar, .date-picker-widget, .thinking").forEach((n) => n.remove()); scrollDown(); return true; }
    } catch (e) { /* ignore */ }
    return false;
  }

  // ------------------------------------------------------------------ bubbles & widgets
  function bubble(text, who) {
    if (who === "user") document.querySelector(".chat-main").classList.add("has-chat");
    const b = el("div", "msg " + who);
    b.textContent = text;
    chatWindow.appendChild(b);
    scrollDown();
  }
  function clearWidgets() { chatWindow.querySelectorAll(".quick-reply-bar, .date-picker-widget").forEach((n) => n.remove()); }

  function quickReplies(list) {
    if (!list || !list.length) return;
    const bar = el("div", "quick-reply-bar");
    list.forEach((q) => {
      const b = el("button", "quick-reply-btn");
      b.textContent = q.label;
      b.dataset.send = q.value;
      b.dataset.label = q.label;
      bar.appendChild(b);
    });
    chatWindow.appendChild(bar);
  }

  function datePicker(h) {
    const w = el("div", "date-picker-widget");
    const min = h.min || new Date().toISOString().slice(0, 10);
    w.innerHTML = `<div class="date-picker-label">📅 ${esc(S.pick_date)}</div>
      <div class="date-picker-row"><input type="date" class="date-input" min="${esc(min)}" value="${esc(min)}">
      <button class="date-confirm-btn" data-act="pick-date">${esc(S.confirm)}</button></div>
      <div class="date-hint">${esc(S.or_type)}</div>`;
    chatWindow.appendChild(w);
  }

  function feedback(id) {
    const row = el("div", "feedback-bar");
    row.dataset.interactionId = id;
    row.innerHTML = `${esc(S.helpful)} <button class="feedback-btn" data-rating="1" aria-label="👍">👍</button><button class="feedback-btn" data-rating="-1" aria-label="👎">👎</button>`;
    chatWindow.appendChild(row);
  }

  // ------------------------------------------------------------------ cards
  function sampleBadge() { return `<span class="sample-badge">${esc(S.sample_data)}</span>`; }

  function flightsBlock(b) {
    const wrap = el("div", "cards flights-block");
    b.legs.forEach((leg) => {
      const sec = el("div", "leg-section");
      sec.dataset.leg = leg.leg;
      sec.innerHTML = `<div class="leg-head"><span class="leg-title">${esc(leg.title)}</span><span class="leg-route">${esc(leg.route)} · ${esc(leg.date_label)}</span>${sampleBadge()}</div>`;
      leg.options.forEach((o) => {
        const stops = o.stops ? `<span class="tag warn">${esc(fmt("one_stop_via", { via: o.via }))}</span>` : `<span class="tag good">${esc(S.nonstop)}</span>`;
        const plus = o.arrive_day_offset ? ` <sup>${esc(fmt("next_day", { n: o.arrive_day_offset }))}</sup>` : "";
        const card = el("div", "flight-card");
        card.innerHTML = `<div>
            <div class="flight-airline">${esc(o.airline)} · ${esc(o.flight_no)}</div>
            <div class="flight-route">${esc(o.origin)} → ${esc(o.destination)} · ${esc(o.cabin)}</div>
            <div class="flight-times">${esc(o.depart)} – ${esc(o.arrive)}${plus}</div>
            <div class="flight-meta"><span class="tag">${esc(o.duration)}</span>${stops}</div>
          </div>
          <div class="flight-price-col">
            <div class="flight-price">${inr(o.total_for_pax)}<small>${esc(S.for_travellers)}</small><small>${inr(o.fare_adult)} ${esc(S.per_adult)}</small></div>
            <button class="select-btn" data-act="select_flight" data-leg="${o.leg}" data-id="${esc(o.id)}">${esc(S.select)}</button>
          </div>`;
        sec.appendChild(card);
      });
      wrap.appendChild(sec);
    });
    wrap.appendChild(el("div", "sample-note", esc(S.sample_note)));
    chatWindow.appendChild(wrap);
  }

  function hotelsBlock(b) {
    const wrap = el("div", "cards hotel-grid");
    wrap.appendChild(el("div", "leg-head", `<span class="leg-title">${esc(b.city)}</span><span class="leg-route">${esc(b.checkin_label)} – ${esc(b.checkout_label)}</span>${sampleBadge()}`));
    const grid = el("div", "hotel-list");
    b.hotels.forEach((h) => {
      const am = (h.amenities || []).map((a) => `<span class="tag">${esc(S["am_" + a] || a)}</span>`).join("");
      const src = h.image_url || h.image;
      const card = el("div", "hotel-card");
      card.innerHTML = `<img class="hotel-img" src="${esc(src)}" alt="${esc(h.name)}" loading="lazy" data-fallback="${esc(h.image_fallback)}">
        <div class="hotel-body">
          <div class="hotel-name">${esc(h.name)}</div>
          <div class="hotel-area">📍 ${esc(h.area)}, ${esc(h.city)}</div>
          <div class="hotel-rating">★ ${esc(h.rating)} <small>${esc(S.rating)}</small></div>
          <div class="hotel-perks">${am}</div>
          <div class="hotel-foot">
            <div class="hotel-price">${inr(h.price_per_night)}<small>${esc(S.per_night)}</small>
              <small>${inr(h.stay_total)} · ${esc(fmt("stay_total", { nights: h.nights, rooms: h.rooms }))}</small></div>
            <button class="select-btn" data-act="select_hotel" data-id="${esc(h.id)}">${esc(S.select)}</button>
          </div>
        </div>`;
      grid.appendChild(card);
    });
    wrap.appendChild(grid);
    wrap.appendChild(el("div", "sample-note", esc(S.sample_note)));
    chatWindow.appendChild(wrap);
  }

  function linesTable(lines) {
    return lines.map((l) => `<div class="sum-line"><div><div class="sum-label">${esc(l.label)}</div><div class="sum-detail">${esc(l.detail || "")}</div></div><div class="sum-amt">${esc(l.amount_label)}</div></div>`).join("");
  }

  function reviewBlock(b) {
    const c = el("div", "cards summary-card");
    c.innerHTML = `<div class="leg-head"><span class="leg-title">🧾 ${esc(S.review_title)}</span>${sampleBadge()}</div>
      ${linesTable(b.lines)}
      <div class="sum-total"><span>${esc(S.total_indicative)}</span><span>${esc(b.total_label)}</span></div>
      <div class="sample-note">${esc(S.sample_note)}</div>
      <button class="primary-btn" data-act="checkout">${esc(S.demo_checkout)}</button>`;
    chatWindow.appendChild(c);
  }

  function checkoutBlock(b) {
    const c = el("div", "cards summary-card checkout-card");
    c.innerHTML = `<div class="leg-head"><span class="leg-title">${esc(S.checkout_title)}</span>${sampleBadge()}</div>
      <div class="demo-notice">⚠️ ${esc(S.checkout_notice)}</div>
      ${linesTable(b.lines)}
      <div class="sum-total"><span>${esc(S.total_indicative)}</span><span>${esc(b.total_label)}</span></div>
      <div class="demo-status">${esc(S.checkout_status)}</div>`;
    chatWindow.appendChild(c);
  }

  function alertBlock(b) {
    const c = el("div", "cards alert-card");
    c.innerHTML = `<div class="alert-head"><span class="alert-badge">⏱️ ${esc(S.alert_badge)}</span></div>
      <div class="flight-airline">${esc(b.airline)} · ${esc(b.flight_no)} <span class="leg-route">${esc(b.route)}</span></div>
      <div class="alert-times">${esc(S.departure)}: <s>${esc(b.old)}</s> → <b>${esc(b.new)}</b> <span class="tag warn">${esc(fmt("delay", { n: b.delay_min }))}</span></div>
      <div class="sample-note">${esc(S.alert_notice)}</div>`;
    chatWindow.appendChild(c);
  }

  function routeSvg(route) {
    if (!route || route.length < 2) return "";
    const W = 340, H = 150, pad = 26;
    const lats = route.map((r) => r.lat), lons = route.map((r) => r.lon);
    const [minLa, maxLa, minLo, maxLo] = [Math.min(...lats), Math.max(...lats), Math.min(...lons), Math.max(...lons)];
    const sx = (lo) => pad + ((lo - minLo) / ((maxLo - minLo) || 1)) * (W - 2 * pad);
    const sy = (la) => H - pad - ((la - minLa) / ((maxLa - minLa) || 1)) * (H - 2 * pad);
    const pts = route.map((r) => [sx(r.lon), sy(r.lat)]);
    const path = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
    const dots = pts.map((p, i) => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="6" class="r-dot"/><text x="${p[0].toFixed(1)}" y="${(p[1] - 11).toFixed(1)}" class="r-num">${i + 1}</text>`).join("");
    const names = route.map((r, i) => `<li><b>${i + 1}</b> ${esc(r.name)}</li>`).join("");
    return `<div class="route-box"><div class="route-label">${esc(S.route)}</div>
      <svg viewBox="0 0 ${W} ${H}" class="route-svg" role="img" aria-label="${esc(route.map((r) => r.name).join(" → "))}">
      <path d="${path}" class="r-line"/>${dots}</svg><ol class="route-stops">${names}</ol></div>`;
  }

  function itineraryBlock(b) {
    const c = el("div", "cards itinerary-card");
    const badge = b.adjusted ? S.adjusted_badge : S.curated_badge;
    const days = b.days.map((d) => `<details class="day" ${d.n <= 2 ? "open" : ""}><summary><b>${esc(fmt("day_n", { n: d.n }))}</b> · ${esc(d.title)} <span class="day-stop">${esc(d.stop)}</span></summary>
        <ul>${d.activities.map((a) => `<li>${esc(a.text)}${a.tag ? ` <span class="tag">${esc(a.tag_label || a.tag)}</span>` : ""}</li>`).join("")}</ul></details>`).join("");
    const notes = (b.notes || []).map((n) => `<li>${esc(n)}</li>`).join("");
    c.innerHTML = `<div class="leg-head"><span class="leg-title">🗺️ ${esc(b.title)}</span><span class="sample-badge">${esc(badge)}</span></div>
      <div class="it-summary">${esc(b.summary)}${b.interests && b.interests.length ? " · " + esc(b.interests.join(", ")) : ""}</div>
      ${routeSvg(b.route)}
      <div class="it-days">${days}</div>
      <div class="it-budget"><div class="route-label">${esc(S.budget)}</div>
        <div class="sum-total"><span>${esc(fmt("plan_total", { amount: b.budget.total_label, n: b.budget.travellers }))}</span></div>
        <div class="sum-detail">${esc(fmt("pp_day", { amount: b.budget.pp_day_label, style: b.budget.style_label }))}</div></div>
      ${notes ? `<ul class="it-notes">${notes}</ul>` : ""}
      <div class="sample-note">${esc(S.plan_disclaimer)}</div>`;
    chatWindow.appendChild(c);
  }

  const RENDER = { flights: flightsBlock, hotels: hotelsBlock, review: reviewBlock, checkout: checkoutBlock, alert: alertBlock, itinerary: itineraryBlock };

  // ------------------------------------------------------------------ transport
  function thinking() {
    const t = el("div", "thinking", `${esc(S.thinking || "…")} <span class="dots"><span></span><span></span><span></span></span>`);
    chatWindow.appendChild(t);
    scrollDown();
    return t;
  }

  async function post(body) {
    const sel = replySel.value;
    Object.assign(body, { tz: TZ, language_mode: sel === "auto" ? "auto" : "manual" });
    if (sel !== "auto") body.reply_language = sel;
    const res = await fetch("/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await res.json();
    if (!res.ok && !data.reply) throw new Error("bad_response");
    return data;
  }

  // Requests are queued, so a click made while a reply is still rendering is never lost.
  let queue = Promise.resolve();
  function send(body, display) {
    queue = queue.then(() => doSend(body, display)).catch((e) => console.error(e));
    return queue;
  }

  async function doSend(body, display) {
    busy = true;
    clearWidgets();
    hint.hidden = true;
    if (display) bubble(display, "user");
    const t = thinking();
    try {
      const data = await post(body);
      t.remove();
      await render(data);
    } catch (e) {
      t.remove();
      bubble(S.server_error || "Sorry, I couldn't reach the server.", "bot");
      console.error(e);
    } finally {
      busy = false;
      save();
    }
  }

  async function render(data) {
    if (data.language && data.language !== replyLang) {
      replyLang = data.language;
      await loadStrings(replyLang);
    }
    if (data.language_mode === "manual" && replySel.value !== data.language) replySel.value = data.language;
    if (data.clear_results) chatWindow.querySelectorAll(".cards").forEach((n) => n.remove());
    if (data.reply) bubble(data.reply, "bot");
    if (data.rag_sources && data.rag_sources.length) {
      chatWindow.appendChild(el("div", "rag-source", `📚 ${esc(S.source)} · ${esc(data.rag_sources.map((s) => s.title).join(", "))}`));
    }
    (data.blocks || []).forEach((b) => RENDER[b.type] && RENDER[b.type](b));
    if (data.input_hint && data.input_hint.kind === "date") datePicker(data.input_hint);
    quickReplies(data.quick_replies);
    if (data.ask_feedback && data.interaction_id) feedback(data.interaction_id);
    if (data.show_seat_selection && data.seat_params) openSeats(data.seat_params);
    if (voiceReply && data.reply) speak(data.reply, replyLang);
    scrollDown();
  }

  function sendText(text, opts) {
    const msg = (text || "").trim();
    if (!msg) return;
    input.value = "";
    send({ message: msg, via_button: !!(opts && opts.button) }, (opts && opts.label) || msg);
  }
  function sendAction(action, payload, label) { send({ action, payload: payload || {} }, label || null); }

  // ------------------------------------------------------------------ delegated clicks
  chatWindow.addEventListener("click", async (ev) => {
    const q = ev.target.closest("[data-send]");
    if (q) { sendText(q.dataset.send, { button: true, label: q.dataset.label }); return; }
    const a = ev.target.closest("[data-act]");
    if (a) {
      const act = a.dataset.act;
      if (act === "pick-date") {
        const v = a.closest(".date-picker-widget").querySelector(".date-input").value;
        if (v) sendText(v, { button: true });
        return;
      }
      if (act === "select_flight") {
        const sec = a.closest(".leg-section");
        sec.querySelectorAll(".flight-card").forEach((c) => c.classList.remove("selected"));
        a.closest(".flight-card").classList.add("selected");
        sec.querySelectorAll(".select-btn").forEach((b) => (b.textContent = S.select));
        a.textContent = S.selected;
        sendAction("select_flight", { leg: Number(a.dataset.leg), id: a.dataset.id });
        return;
      }
      if (act === "select_hotel") {
        const grid = a.closest(".hotel-list");
        grid.querySelectorAll(".hotel-card").forEach((c) => c.classList.remove("selected"));
        a.closest(".hotel-card").classList.add("selected");
        grid.querySelectorAll(".select-btn").forEach((b) => (b.textContent = S.select));
        a.textContent = S.selected;
        sendAction("select_hotel", { id: a.dataset.id });
        return;
      }
      if (act === "checkout") { a.disabled = true; sendAction("checkout", {}, S.demo_checkout); return; }
    }
    const fb = ev.target.closest(".feedback-btn");
    if (fb) {
      const row = fb.closest(".feedback-bar");
      try {
        const r = await fetch("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ interaction_id: Number(row.dataset.interactionId), rating: Number(fb.dataset.rating) }) });
        if (!r.ok) throw new Error("feedback");
        row.textContent = S.thanks_feedback; row.classList.add("submitted");
      } catch (e) { row.textContent = S.feedback_failed; }
      save();
    }
  });

  // image fallback (error events don't bubble, so capture them)
  chatWindow.addEventListener("error", (ev) => {
    const img = ev.target;
    if (img.tagName === "IMG" && img.dataset.fallback && img.src.indexOf(img.dataset.fallback) === -1) img.src = img.dataset.fallback;
  }, true);

  // ------------------------------------------------------------------ seat map overlay
  function openSeats(params) {
    let ov = document.getElementById("seat-selection-overlay");
    if (!ov) {
      ov = el("div");
      ov.id = "seat-selection-overlay";
      ov.appendChild(el("iframe", "seat-frame"));
      document.body.appendChild(ov);
    }
    ov.querySelector("iframe").src = "/seat-selection?p=" + encodeURIComponent(JSON.stringify(params));
    ov.style.display = "block";
  }
  function closeSeats() {
    const ov = document.getElementById("seat-selection-overlay");
    if (ov) { ov.style.display = "none"; ov.querySelector("iframe").src = "about:blank"; }
  }
  window.addEventListener("message", (ev) => {
    if (ev.origin !== window.location.origin || !ev.data) return;
    if (ev.data.action === "back_from_seat_selection") { closeSeats(); sendAction("back_from_seat_selection"); }
    if (ev.data.action === "seats_selected") { closeSeats(); sendAction("seats_selected", { leg: ev.data.leg, seats: ev.data.seats }); }
  });

  // ------------------------------------------------------------------ voice
  const VOICE_LANG = { en: "en-IN", kn: "kn-IN", hi: "hi-IN" };
  function speak(text, lang) {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, ""));
    const want = VOICE_LANG[lang] || "en-IN";
    const v = window.speechSynthesis.getVoices().find((x) => x.lang === want || x.lang.startsWith(want.slice(0, 2)));
    if (v) u.voice = v;
    u.lang = v ? v.lang : want;
    window.speechSynthesis.speak(u);
  }

  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, recording = false;
  if (Rec) {
    rec = new Rec();
    rec.continuous = false; rec.interimResults = true; rec.maxAlternatives = 1;
    rec.onstart = () => { recording = true; micBtn.classList.add("recording"); input.placeholder = S.listening || "…"; };
    rec.onresult = (e) => { input.value = Array.from(e.results).map((r) => r[0].transcript).join(" "); };
    rec.onerror = (e) => { if (e.error !== "aborted" && e.error !== "no-speech") bubble(S.voice_error, "bot"); };
    rec.onend = () => {
      recording = false; micBtn.classList.remove("recording"); input.placeholder = S.placeholder || "";
      if (input.value.trim()) { hint.hidden = false; input.focus(); }  // user reviews, then sends
    };
  }
  micBtn.addEventListener("click", () => {
    if (!rec) { bubble(S.voice_unsupported, "bot"); return; }
    if (recording) { rec.stop(); return; }
    rec.lang = micSel.value;   // speech-recognition language, independent of reply language
    input.value = "";
    try { rec.start(); } catch (e) { /* already started */ }
  });
  voiceBtn.addEventListener("click", () => {
    voiceReply = !voiceReply;
    voiceBtn.classList.toggle("active", voiceReply);
    voiceBtn.setAttribute("aria-pressed", String(voiceReply));
    if (!voiceReply && "speechSynthesis" in window) window.speechSynthesis.cancel();
  });

  // ------------------------------------------------------------------ controls
  sendBtn.addEventListener("click", () => sendText(input.value));
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") sendText(input.value); });
  input.addEventListener("input", () => { if (!input.value) hint.hidden = true; });
  document.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => sendText(c.dataset.message, { button: true, label: c.textContent.trim() })));

  replySel.addEventListener("change", async () => {
    const v = replySel.value;
    if (v !== "auto") { replyLang = v; await loadStrings(v); }
    save();
  });

  document.getElementById("new-chat-btn").addEventListener("click", async () => {
    await fetch("/reset", { method: "POST" }).catch(() => {});
    chatWindow.innerHTML = "";
    document.querySelector(".chat-main").classList.remove("has-chat");
    sessionStorage.removeItem("aura_chat_html");
    send({ action: "welcome" }, null);
  });

  // ------------------------------------------------------------------ start
  window.addEventListener("load", async () => {
    const restored = restore();
    await loadStrings(replyLang);
    if (!restored) send({ action: "welcome" }, null);
  });

  // exposed for tests/debugging
  window.Aura = { sendText, sendAction, render, loadStrings };
})();
