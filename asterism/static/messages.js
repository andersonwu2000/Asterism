// The messages pages, middle column: chat (#chat data-mode="chat": a channel, named by the address's hash) and
// private messages (data-mode="dm": the conversation the address names, /slug/dm/name; the bare /slug/dm opens the
// newest one). The place's name is in the top bar (a channel's opens its settings, a private conversation's the other
// member's card); then its messages and the composer. A message shows no number: its id stays in the page's data
// (the row's id) for replies and jumps. An address with ?m=<id> opens its place at that message. It speaks only the
// project's JSON API (/api/messages, /api/read) and asks for news every few seconds; the places (and their unread
// counts) come from the frame (frame.js, Asterism.side), the text rendering from render.js, the right column from
// right.js, tasks.js, people.js and search.js. Asterism.chat lets the others put a mention into the composer and
// open a place at one message (in the other mode's page when the place is there). All texts come from the page's
// message catalogue.
"use strict";
(function () {
  var A = window.Asterism;
  var root = document.getElementById("chat");
  if (!root || !A || !A.renderText || !A.side) return;
  var t = A.t, make = A.make;

  var SLUG = root.dataset.slug, MODE = root.dataset.mode === "dm" ? "dm" : "chat";
  var API = "/" + encodeURIComponent(SLUG) + "/api/";
  var PAGE = 50, NEWS_EVERY_MS = 4000, GROUP_MS = 5 * 60 * 1000;
  var LANG = document.documentElement.lang || undefined;
  var DOT = " · ";

  var el = {
    title: document.getElementById("place-button"), list: document.getElementById("messages"),
    scroll: document.getElementById("scroller"),
    older: document.getElementById("older"), form: document.getElementById("composer"),
    text: document.getElementById("text"), out: document.getElementById("composer-out"),
    reply: document.getElementById("reply-target"), replyCancel: document.getElementById("reply-cancel")
  };
  var state = {place: null, first: 0, last: 0, replyTo: null, places: {channels: [], "private": []}, busy: false};

  function get(path, params) { return A.request(API + path, params); }
  function post(path, body) { return A.request(API + path, null, body); }

  // ------------------------------------------------------------------ places

  // Chat: the channel the hash names (#general by default). Private messages: the conversation the address names.
  function placeFromHash() {
    if (MODE === "dm") return root.dataset.place || "";
    var raw = window.location.hash.slice(1);
    try { raw = decodeURIComponent(raw); } catch (err) { raw = ""; }
    return raw || "#general";
  }
  function isChannel(place) { return !!place && place.charAt(0) === "#"; }
  function inThisMode(place) { return MODE === "dm" ? !!place && !isChannel(place) : isChannel(place); }
  // The address of `place`, opened at the message `id` (when given): chat's for a channel, private messages' else.
  function addressOf(place, id) {
    var base = "/" + encodeURIComponent(SLUG), at = id ? "?m=" + encodeURIComponent(id) : "";
    return isChannel(place) ? base + at + "#" + encodeURIComponent(place)
                            : base + "/dm/" + encodeURIComponent(place) + at;
  }

  A.side.onChange(function (places) { state.places = places; });
  function loadPlaces() { return A.side.refresh(); }

  // ------------------------------------------------------------------ folding
  //
  // One mechanism for two cases: a block that is folded or open, with a button (aria-expanded) that toggles
  // it. The state lives in `folds` for as long as the page is open, so the periodic refresh and loading older
  // messages keep it. Keys: "long:<message id>" for a long message; "run:<message id>" for every member of a
  // run of system notices (a run is open when any of its members is), so a run that grows at either end
  // keeps its state.

  var folds = new Map();
  var RUN_MIN = 3, CLAMP_EM = 18, CLAMP_SLACK = 1.15;     // 12 lines of 1.5em; a little over is not folded

  // Toggle a block without making the list jump: the block's top stays where it was.
  function toggleBlock(anchor, change) {
    var before = anchor.getBoundingClientRect().top;
    change();
    el.scroll.scrollTop += anchor.getBoundingClientRect().top - before;
  }

  function foldButton(cls, onClick) {
    var b = A.button(cls, null, onClick);
    b.setAttribute("aria-expanded", "false");
    return b;
  }

  // A long message: clamped by CSS (the whole text is rendered underneath), decided by its rendered height.
  // Once the person chose, nothing folds or opens it again by itself.
  function clampable(li, box, id) {
    var key = "long:" + id;
    box.id = "t-" + id;
    var button = foldButton("fold-toggle", function () {
      toggleBlock(li, function () { folds.set(key, box.classList.contains("clamped")); fit(); });
    });
    button.setAttribute("aria-controls", box.id);
    button.hidden = true;
    function fit() {
      var choice = folds.get(key);
      var tall = box.scrollHeight > parseFloat(getComputedStyle(box).fontSize) * CLAMP_EM * CLAMP_SLACK;
      var clamped = choice === undefined ? tall : !choice;
      box.classList.toggle("clamped", clamped);
      button.hidden = choice === undefined && !tall;
      button.setAttribute("aria-expanded", String(!clamped));
      button.textContent = t(clamped ? "msg.show_all" : "msg.collapse");
    }
    li._fit = fit;
    if (window.ResizeObserver) {          // a late font or formula: look again, unless the person chose
      new ResizeObserver(function () {
        if (!folds.has(key)) window.requestAnimationFrame(fit);
      }).observe(box);
    }
    return button;
  }

  function isMessage(li) { return !!li.id && li.id.indexOf("m-") === 0; }
  function idOf(li) { return Number(li.id.slice(2)); }
  function messageRows() { return Array.prototype.filter.call(el.list.children, isMessage); }

  function clock(iso) {
    return new Date(iso).toLocaleTimeString(LANG, {hour: "2-digit", minute: "2-digit", hourCycle: "h23"});
  }

  // Runs of three or more system notices fold into one row. A notice that is important for the viewer is
  // never folded: it ends the run.
  function regroup() {
    var items = messageRows(), runs = [], cur = [];
    items.forEach(function (li) {
      if (li.classList.contains("system") && !li.classList.contains("important")) { cur.push(li); return; }
      runs.push(cur);
      cur = [];
    });
    runs.push(cur);
    var rows = new Map();
    Array.prototype.forEach.call(el.list.querySelectorAll("li.fold"), function (r) { rows.set(r.dataset.first, r); });
    items.forEach(function (li) { if (li.dataset.run) { li.hidden = false; delete li.dataset.run; } });
    var used = new Set();
    runs.filter(function (run) { return run.length >= RUN_MIN; }).forEach(function (run) {
      var first = String(idOf(run[0])), ids = run.map(idOf);
      var row = rows.get(first) || runRow();
      used.add(first);
      row.dataset.first = first;
      row._ids = ids;
      if (run[0].previousSibling !== row) el.list.insertBefore(row, run[0]);
      var open = ids.some(function (id) { return folds.get("run:" + id); });
      run.forEach(function (li) { li.hidden = !open; li.dataset.run = first; });
      var last = known.get(ids[ids.length - 1]) || {};
      var button = row.querySelector(".fold-row");
      row.querySelector("time").textContent = last.sent_at ? clock(last.sent_at) : "";
      button.setAttribute("aria-expanded", String(open));
      button.textContent = open ? t("msg.fold_run", {n: ids.length})
                                : t("msg.folded_run", {n: ids.length, text: last.text || "",
                                                       time: last.sent_at ? clock(last.sent_at) : ""});
    });
    rows.forEach(function (r, first) { if (!used.has(first)) r.remove(); });
  }

  function runRow() {
    var row = make("li", "msg fold system");
    var gutter = make("div", "gutter"), body = make("div", "body");
    gutter.appendChild(make("time"));
    body.appendChild(foldButton("fold-row", function () {
      toggleBlock(row, function () {
        setRun(row._ids, row.querySelector(".fold-row").getAttribute("aria-expanded") !== "true");
      });
    }));
    row.append(gutter, body);
    return row;
  }

  function setRun(ids, open) {
    ids.forEach(function (id) { if (open) folds.set("run:" + id, true); else folds.delete("run:" + id); });
    settle([]);
  }

  // A line for each day, before its first message (or before the folded row that starts with it).
  function days() {
    Array.prototype.slice.call(el.list.querySelectorAll("li.day")).forEach(function (d) { d.remove(); });
    var last = "", year = new Date().getFullYear();
    messageRows().forEach(function (li) {
      var m = known.get(idOf(li)), d = new Date(m.sent_at), key = d.toDateString();
      if (key === last) return;
      last = key;
      var anchor = li, prev = li.previousElementSibling;
      if (prev && prev.classList.contains("fold") && prev.dataset.first === String(m.id)) anchor = prev;
      var opts = {month: "long", day: "numeric", weekday: "short"};
      if (d.getFullYear() !== year) opts.year = "numeric";
      var row = make("li", "day", d.toLocaleDateString(LANG, opts));
      row.setAttribute("role", "separator");
      el.list.insertBefore(row, anchor);
    });
  }

  // Consecutive messages of one sender within five minutes share one header. A reply, a scheduled message, a
  // message important for the reader and the system's lines always have their own.
  function authors() {
    var prev = null;
    Array.prototype.forEach.call(el.list.children, function (li) {
      if (!isMessage(li)) { prev = null; return; }
      if (li.hidden) return;
      var m = known.get(idOf(li));
      var cont = !!prev && m.from_kind !== "system" && !m.reply_to && !m.scheduled && m.level !== "important" &&
                 prev.from === m.from && prev.from_kind === m.from_kind &&
                 Date.parse(m.sent_at) - Date.parse(prev.sent_at) < GROUP_MS;
      li.classList.toggle("cont", cont);
      li.classList.toggle("head", !cont);
      prev = m.from_kind === "system" ? null : m;
    });
  }

  // After every change of the list: fold the runs, mark the days, group the senders, fit the long messages.
  function settle(added) {
    regroup();
    days();
    authors();
    added.forEach(function (li) { if (li._fit) li._fit(); });
  }

  // ------------------------------------------------------------------ messages

  var known = new Map();                  // message id -> the message object

  function snippet(text) {
    var s = String(text).replace(/\s+/g, " ").trim();
    return s.length > 140 ? s.slice(0, 140) + "…" : s;
  }
  function senderName(m) { return m.from_kind === "system" ? t("msg.system") : m.from; }

  // The quiet line above a reply: who and what it answers, when that message is loaded.
  function replyLabel(id) {
    var m = known.get(id);
    return m ? t("msg.reply_line", {name: senderName(m), text: snippet(m.text)}) : t("msg.reply_to_link", {id: id});
  }
  function refreshReplyLines() {
    Array.prototype.forEach.call(el.list.querySelectorAll(".reply-line .link-btn"), function (b) {
      b.textContent = replyLabel(Number(b.dataset.reply));
    });
  }

  function agentTag(name) {
    var who = A.side.directory[name];
    return who && who.owner ? t("msg.agent_of", {owner: who.owner}) : t("msg.kind_agent");
  }

  function messageItem(m) {
    known.set(m.id, m);
    var li = make("li", "msg" + (m.from_kind === "system" ? " system" : "") + (m.level === "important" ? " important" : ""));
    li.id = "m-" + m.id;
    var gutter = make("div", "gutter"), body = make("div", "body");
    var when = make("time", "", clock(m.sent_at));
    when.dateTime = m.sent_at;
    when.title = new Date(m.sent_at).toLocaleString(LANG);
    gutter.appendChild(when);

    if (m.reply_to) {
      var line = make("div", "reply-line");
      var jump = A.button("link-btn", replyLabel(m.reply_to), function () { jumpTo(m.reply_to); });
      jump.dataset.reply = String(m.reply_to);
      jump.title = t("msg.jump_hint");
      line.appendChild(jump);
      body.appendChild(line);
    }

    var meta = make("div", "meta");
    meta.appendChild(m.from_kind === "system" || !A.people ? make("span", "from", senderName(m))
                                                           : A.people.nameButton(m.from, "from name-btn"));
    if (m.from_kind === "agent") meta.appendChild(make("span", "tag", agentTag(m.from)));
    if (m.scheduled) {
      var sch = make("span", "tag", t("msg.scheduled"));
      sch.title = t("msg.scheduled_hint", {name: m.from});
      meta.appendChild(sch);
    }
    if (m.level === "important") meta.appendChild(make("span", "pill", t("msg.important")));
    body.appendChild(meta);

    var box = A.renderText(m.text);
    if (A.paths) A.paths.scan(box);
    body.appendChild(box);
    body.appendChild(clampable(li, box, m.id));

    var acts = make("div", "acts");
    acts.setAttribute("role", "group");
    acts.setAttribute("aria-label", t("msg.acts"));
    if (m.from_kind !== "system") {
      acts.appendChild(A.button("", t("msg.reply"), function () { setReply(m.id); el.text.focus(); }));
      body.appendChild(acts);
    }
    li.append(gutter, body);
    return li;
  }

  function showEmpty() {
    if (!el.list.children.length) el.list.appendChild(make("li", "empty", t("msg.empty")));
  }
  function dropEmpty() {
    var e = el.list.querySelector("li.empty");
    if (e) e.remove();
  }

  function append(msgs) {
    if (!msgs.length) return;
    dropEmpty();
    var added = [];
    msgs.forEach(function (m) {
      if (document.getElementById("m-" + m.id)) return;
      added.push(el.list.appendChild(messageItem(m)));
      state.last = Math.max(state.last, m.id);
      if (!state.first || m.id < state.first) state.first = m.id;
    });
    settle(added);
  }

  function prepend(msgs) {
    if (!msgs.length) return;
    dropEmpty();
    var before = el.scroll.scrollHeight, top = el.list.firstChild, added = [];
    msgs.forEach(function (m) {
      if (document.getElementById("m-" + m.id)) return;
      added.push(el.list.insertBefore(messageItem(m), top));
      if (!state.first || m.id < state.first) state.first = m.id;
      state.last = Math.max(state.last, m.id);
    });
    settle(added);
    refreshReplyLines();
    el.scroll.scrollTop += el.scroll.scrollHeight - before;
  }

  function atBottom() { return el.scroll.scrollHeight - el.scroll.scrollTop - el.scroll.clientHeight < 40; }
  function toBottom() { el.scroll.scrollTop = el.scroll.scrollHeight; }

  async function markRead() {
    if (state.last) await post("read", {"in": state.place, upto: state.last});
  }

  async function loadOlder() {
    if (!state.first) return false;
    var place = state.place;
    var r = await get("messages", {"in": place, before: state.first, limit: PAGE});
    if (!r.ok || place !== state.place) return false;
    var msgs = r.data.messages || [];
    prepend(msgs);
    el.older.hidden = msgs.length < PAGE;
    return msgs.length > 0;
  }

  async function jumpTo(id) {
    var target = document.getElementById("m-" + id);
    for (var i = 0; !target && i < 10 && id < state.first; i++) {
      if (!(await loadOlder())) break;
      target = document.getElementById("m-" + id);
    }
    if (!target) { el.out.textContent = t("msg.not_here"); return; }
    if (target.hidden && target.dataset.run) {          // inside a folded run: open it first
      var row = el.list.querySelector('li.fold[data-first="' + target.dataset.run + '"]');
      if (row) setRun(row._ids, true);
    }
    target.scrollIntoView({block: "center"});
    target.tabIndex = -1;
    target.focus({preventScroll: true});
    target.classList.add("flash");
    clearTimeout(target._flash);
    target._flash = setTimeout(function () { target.classList.remove("flash"); }, 1500);
  }

  // The channel bar's name: a channel's opens its settings; a private conversation's the other member's card
  // (people.js, by data-member).
  function drawTitle(place) {
    var b = el.title;
    b.textContent = place;
    if (isChannel(place)) {
      delete b.dataset.member;
      b.removeAttribute("aria-haspopup");
      b.setAttribute("aria-label", t("bar.channel_settings", {place: place}));
    } else {
      b.dataset.member = place;
      b.setAttribute("aria-haspopup", "dialog");
      b.setAttribute("aria-label", t("bar.profile", {name: place}));
    }
    b.title = b.getAttribute("aria-label");
  }
  el.title.addEventListener("click", function () {
    if (isChannel(state.place) && A.project) A.project.openSettings(A.side.settingsHref(state.place.slice(1)));
  });

  // Private messages with no conversation chosen: the newest one, else a sentence and no composer.
  function nothingChosen() {
    var newest = state.places["private"][0];
    if (newest) {
      root.dataset.place = newest["with"];
      history.replaceState(null, "", addressOf(newest["with"]));
      open(newest["with"]);
      return;
    }
    el.title.textContent = "";
    el.title.hidden = true;
    el.form.hidden = true;
    el.list.textContent = "";
    el.list.appendChild(make("li", "empty", t("msg.private_none")));
  }

  var target = null;                      // a message to open the next place at (Asterism.chat.openAt)
  var opened = [];                        // what wants to know when a place is opened (Asterism.chat.onOpen)

  async function open(place) {
    var at = target;
    target = null;
    state.place = place;
    el.title.hidden = false;
    el.form.hidden = false;
    if (A.rail && MODE === "chat") A.store.set(A.rail.chatPlaceKey, place);
    state.first = 0;
    state.last = 0;
    setReply(null);
    known.clear();
    el.list.textContent = "";
    el.out.textContent = "";
    drawTitle(place);
    opened.forEach(function (fn) { fn(place); });
    document.title = place + DOT + (document.title.split(DOT).slice(-1)[0] || "");
    A.side.setCurrent(place);
    state.busy = true;
    try {
      // At one message: the messages up to it and after it; otherwise the newest.
      var r = await get("messages", at ? {"in": place, before: at + 1, limit: PAGE} : {"in": place, limit: PAGE});
      var after = at && r.ok ? await get("messages", {"in": place, after: at, limit: PAGE}) : null;
      if (place !== state.place) return;
      if (!r.ok) { el.out.textContent = A.errorText(r.data.error); return; }
      var msgs = r.data.messages || [];
      append(msgs.concat(after && after.ok ? after.data.messages || [] : []));
      showEmpty();
      el.older.hidden = msgs.length < PAGE;
      if (at) await jumpTo(at); else toBottom();
      takeMention();
      await markRead();
      await loadPlaces();
    } finally {
      state.busy = false;
    }
  }

  // Text put into the composer, unsent, after what is there; the focus goes to its end.
  function insert(text) {
    var v = el.text.value;
    el.text.value = v + (v && !/\s$/.test(v) ? " " : "") + text;
    grow();
    el.text.focus();
    el.text.setSelectionRange(el.text.value.length, el.text.value.length);
  }

  // Files mode's "mention in chat" leaves a path here: it goes into the composer, unsent.
  function takeMention() {
    if (!A.rail) return;
    var text = A.store.take(A.rail.mentionKey);
    if (typeof text === "string" && text) insert(text);
  }

  A.chat = {
    place: function () { return state.place; },
    onOpen: function (fn) { opened.push(fn); if (state.place) fn(state.place); },
    // "@name " into the composer (the profile card's and the member menu's "mention").
    mention: function (name) { insert("@" + name + " "); },
    // Open `place` at the message `id` (a search result): scrolled to and marked for a moment. A place of the other
    // mode opens in its own page.
    openAt: function (place, id) {
      if (place === state.place && document.getElementById("m-" + id)) { jumpTo(id); return; }
      if (!inThisMode(place) || MODE === "dm") { window.location.href = addressOf(place, id); return; }
      target = id;
      if (placeFromHash() === place) open(place); else window.location.hash = encodeURIComponent(place);
    }
  };

  async function news() {
    if (!state.place || state.busy) return;
    state.busy = true;
    try {
      var place = state.place;
      var r = await get("messages", {"in": place, after: state.last, limit: 200});
      if (r.ok && place === state.place && (r.data.messages || []).length) {
        var bottom = atBottom();
        append(r.data.messages);
        if (bottom) toBottom();
        await markRead();
        await loadPlaces();
      }
    } finally {
      state.busy = false;
    }
  }

  // ------------------------------------------------------------------ writing

  function setReply(id) {
    state.replyTo = id;
    el.reply.hidden = !id;
    var m = id ? known.get(id) : null;
    el.reply.firstChild.textContent = id ? t("msg.replying_to") + (m ? DOT + senderName(m) + ": " + snippet(m.text) : "") : "";
  }

  function outcome(mentions) {
    var by = {offline: [], closed: [], unknown: []};
    (mentions || []).forEach(function (m) {
      if (by[m.result]) by[m.result].push(m.name);
    });
    var parts = [];
    if (by.offline.length) parts.push(t("msg.sent_offline", {names: by.offline.join(", ")}));
    if (by.closed.length) parts.push(t("msg.sent_closed", {names: by.closed.join(", ")}));
    if (by.unknown.length) parts.push(t("msg.sent_unknown", {names: by.unknown.join(", ")}));
    return parts.join(" ");
  }

  // The input grows with its text up to a limit (CSS max-height), then scrolls.
  function grow() {
    el.text.style.height = "auto";
    if (!el.text.value) {                 // empty: one line, whatever the placeholder's length on a narrow screen
      el.text.style.height = "";
      el.text.style.overflowY = "hidden";
      return;
    }
    var max = parseFloat(getComputedStyle(el.text).maxHeight) || Infinity;
    el.text.style.height = Math.min(el.text.scrollHeight + 2, max) + "px";
    el.text.style.overflowY = el.text.scrollHeight + 2 > max ? "auto" : "hidden";
  }
  grow();

  async function send() {
    var text = el.text.value;
    if (!text.trim() || !state.place) return;
    var body = {to: state.place, text: text};
    if (state.replyTo) body.reply_to = state.replyTo;
    var r = await post("messages", body);
    if (!r.ok) { el.out.textContent = A.errorText(r.data.error); return; }
    el.text.value = "";
    grow();
    setReply(null);
    el.out.textContent = outcome(r.data.mentions);
    await news();
    toBottom();
  }

  // ------------------------------------------------------------------ wiring

  el.text.addEventListener("keydown", function (ev) {
    // Enter sends; Shift+Enter is a new line; Enter that ends an input-method composition does neither.
    if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing && ev.keyCode !== 229) {
      ev.preventDefault();
      send();
    } else if (ev.key === "Escape" && state.replyTo) {
      setReply(null);
    }
  });
  el.text.addEventListener("input", grow);
  el.form.addEventListener("submit", function (ev) { ev.preventDefault(); send(); });
  el.replyCancel.addEventListener("click", function () { setReply(null); el.text.focus(); });
  el.older.addEventListener("click", loadOlder);
  // Chat's places are its hash; a private conversation named there (an older address) has its own page now.
  function start() {
    var place = placeFromHash();
    if (MODE === "chat" && !isChannel(place)) { window.location.replace(addressOf(place)); return; }
    if (!place) { nothingChosen(); return; }
    open(place);
  }
  if (MODE === "chat") window.addEventListener("hashchange", function () { start(); });
  // Coming back to this tab from files mode with a mention waiting.
  window.addEventListener("focus", takeMention);
  setInterval(news, NEWS_EVERY_MS);
  // ?m=<id>: open the place at that message (a search result from the other mode's page); then a plain address.
  var asked = new URLSearchParams(window.location.search).get("m");
  if (asked && /^\d{1,18}$/.test(asked)) {
    target = Number(asked);
    history.replaceState(null, "", window.location.pathname + window.location.hash);
  }
  loadPlaces().then(start);
})();
