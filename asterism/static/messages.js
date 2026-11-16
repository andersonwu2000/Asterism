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
// New messages: opening a place draws a quiet line "new" above its first unread message (the read position the API
// answers); messages that arrive while the reader is scrolled up (or the tab is hidden) are not marked read until the
// end of the list is seen, and a pill over the foot of the list says so (inverted when one of them is important for
// the reader) and goes to the first of them, then to the end. The browser tab's title starts with the count of
// messages important for the reader in the whole project, from the frame's places.
// The composer keeps one draft per place (sessionStorage: this tab's, gone with it). It completes, in one list over the
// composer (arrow keys, Enter or Tab, Escape; it never sends): in a channel, "@" and the members (my agents first, then
// the other agents and the people, then the groups); "#" and the channels; "/" right after "@<an agent of mine> " at the
// start, the commands for it (1x: /goal, /goal clear, /compact, /model, each with one line). A mention of a name that is
// no member or group holds the message back once, said under the composer, and sending again sends it as it is. A
// mention that reached someone is drawn in bold. A command's outcome is the system's reply to it, drawn in the page's
// own words from its `outcome`.
"use strict";
(function () {
  var A = window.Asterism;
  var root = document.getElementById("chat");
  if (!root || !A || !A.renderText || !A.side) return;
  var t = A.t, make = A.make;

  var SLUG = root.dataset.slug, MODE = root.dataset.mode === "dm" ? "dm" : "chat", ME = root.dataset.me || "";
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
  // readAt: the read position when the place was opened, openedLast: its newest message then (the unread line goes
  // above the first message between them); seenUpto: what was marked read; fresh: the first message that arrived
  // while the end of the list was out of sight (0: none), freshImportant: one of those is important for the reader.
  var state = {place: null, first: 0, last: 0, replyTo: null, places: {channels: [], "private": []}, busy: false,
               readAt: 0, openedLast: 0, seenUpto: 0, fresh: 0, freshCount: 0, freshImportant: false};

  function get(path, params) { return A.request(API + path, params); }
  function post(path, body) { return A.request(API + path, null, body); }

  // ------------------------------------------------------------------ places

  // Chat: the channel the hash names, by default the first channel the reader may read (the second column's first).
  // Private messages: the conversation the address names.
  function placeFromHash() {
    if (MODE === "dm") return root.dataset.place || "";
    var raw = window.location.hash.slice(1);
    try { raw = decodeURIComponent(raw); } catch (err) { raw = ""; }
    var first = document.querySelector("#side-channels a.place[data-place]");
    return raw || (first ? first.dataset.place : "");
  }
  function isChannel(place) { return !!place && place.charAt(0) === "#"; }
  function inThisMode(place) { return MODE === "dm" ? !!place && !isChannel(place) : isChannel(place); }
  // The address of `place`, opened at the message `id` (when given): chat's for a channel, private messages' else.
  function addressOf(place, id) {
    var base = "/" + encodeURIComponent(SLUG), at = id ? "?m=" + encodeURIComponent(id) : "";
    return isChannel(place) ? base + at + "#" + encodeURIComponent(place)
                            : base + "/dm/" + encodeURIComponent(place) + at;
  }

  // The browser tab's title: "(n) place · Asterism", n the messages important for the reader in the whole project.
  var TAIL = document.title.split(DOT).slice(-1)[0] || "";
  A.side.onChange(function (places) { state.places = places; tabTitle(); });
  function loadPlaces() { return A.side.refresh(); }

  function tabTitle() {
    var p = state.places, n = 0;
    (p.channels || []).concat(p["private"] || []).forEach(function (c) { n += Number(c.important) || 0; });
    var title = (state.place ? state.place + DOT : "") + TAIL;
    document.title = n ? "(" + n + ") " + title : title;
  }

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

  function mine(m) { return m.from_kind === "person" && m.from === ME; }

  // A quiet line "new" above the first message that was unread when the place was opened (not one of mine), after
  // its day's line; above the folded row when that message is folded into a run.
  function unreadLine() {
    var old = el.list.querySelector("li.unread-line");
    if (old) old.remove();
    var first = messageRows().filter(function (li) {
      var m = known.get(idOf(li));
      return m.id > state.readAt && m.id <= state.openedLast && !mine(m);
    })[0];
    if (!first) return;
    var anchor = first;
    if (first.hidden && first.dataset.run) {
      anchor = el.list.querySelector('li.fold[data-first="' + first.dataset.run + '"]') || first;
    }
    var row = make("li", "day unread-line", t("msg.new_line"));
    row.setAttribute("role", "separator");
    el.list.insertBefore(row, anchor);
  }

  // After every change of the list: fold the runs, mark the days and the first unread, group the senders, fit the
  // long messages.
  function settle(added) {
    regroup();
    days();
    unreadLine();
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

  // The system's reply that tells how a command to an agent went (1x), in the reader's words; the stored text is the
  // same sentence in English.
  function outcomeText(o) {
    var key = "msg.cmd." + o.result, vars = {agent: o.agent, command: o.command, detail: o.detail || ""};
    if (o.detail && A.MSG[key + "_why"]) key += "_why";
    return A.MSG[key] ? t(key, vars) : o.result;
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
    if (m.from_kind === "agent") {
      meta.appendChild(make("span", "tag", agentTag(m.from)));
      var model = A.modelTag(m.model);          // the sender's model when it sent this message
      if (model) meta.appendChild(model);
    }
    if (m.scheduled) {
      var sch = make("span", "tag", t("msg.scheduled"));
      sch.title = t("msg.scheduled_hint", {name: m.from});
      meta.appendChild(sch);
    }
    if (m.level === "important") meta.appendChild(make("span", "pill", t("msg.important")));
    body.appendChild(meta);

    var box = A.renderText(m.outcome ? outcomeText(m.outcome) : m.text, {mentions: m.mentions});
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
  // Whether the reader sees the end of the list: the tab is shown and the list is at its foot.
  function caughtUp() { return !document.hidden && atBottom(); }
  // Scroll so that `row` is at the top of the list's view (a little under it).
  function toTop(row) {
    el.scroll.scrollTop += row.getBoundingClientRect().top - el.scroll.getBoundingClientRect().top - 8;
  }

  async function markRead() {
    if (!state.last) return;
    state.seenUpto = Math.max(state.seenUpto, state.last);
    await post("read", {"in": state.place, upto: state.last});
  }

  // ------------------------------------------------------------------ new messages out of sight
  //
  // The pill floats over the foot of the list (a line of no height between the list and the composer holds it).

  var pill = A.button("news-pill", null, function () {
    var row = state.fresh ? document.getElementById("m-" + state.fresh) : null;
    if (row && row.hidden && row.dataset.run) {
      row = el.list.querySelector('li.fold[data-first="' + row.dataset.run + '"]') || row;
    }
    // First to the first new message, unless it is already at the top; then to the end.
    if (row && row.getBoundingClientRect().top > el.scroll.getBoundingClientRect().top + 16) toTop(row); else toBottom();
    seen();
  });
  pill.hidden = true;
  var pillLine = make("div", "news-line");
  pillLine.appendChild(pill);
  root.insertBefore(pillLine, el.form);

  function drawPill() {
    pill.hidden = !state.fresh;
    if (!state.fresh) return;
    pill.classList.toggle("important", state.freshImportant);
    pill.textContent = t(state.freshImportant ? "msg.news_important" : "msg.news");
    pill.setAttribute("aria-label", t(state.freshImportant ? "msg.news_important_label" : "msg.news_label",
                                      {n: state.freshCount}));
    pill.title = pill.getAttribute("aria-label");
  }
  function forgetFresh() {
    state.fresh = 0;
    state.freshCount = 0;
    state.freshImportant = false;
    drawPill();
  }
  // Messages appended while the end of the list is out of sight: the pill counts the others'.
  function noteFresh(msgs) {
    msgs.filter(function (m) { return !mine(m) && m.id > state.seenUpto; }).forEach(function (m) {
      if (!state.fresh) state.fresh = m.id;
      state.freshCount += 1;
      if (m.level === "important") state.freshImportant = true;
    });
    drawPill();
  }

  // The end of the list came into sight: what is there is read now.
  var marking = false;
  async function seen() {
    if (!state.place || !caughtUp()) return;
    if (state.fresh) forgetFresh();
    if (marking || state.busy || state.last <= state.seenUpto) return;
    marking = true;
    try {
      await markRead();
      await loadPlaces();
    } finally {
      marking = false;
    }
  }
  var looking = false;
  el.scroll.addEventListener("scroll", function () {
    if (looking) return;
    looking = true;
    window.requestAnimationFrame(function () { looking = false; seen(); });
  }, {passive: true});
  document.addEventListener("visibilitychange", seen);

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
    state.readAt = 0;
    state.openedLast = 0;
    state.seenUpto = 0;
    forgetFresh();
    setReply(null);
    known.clear();
    el.list.textContent = "";
    el.out.textContent = "";
    loadDraft();
    drawTitle(place);
    opened.forEach(function (fn) { fn(place); });
    tabTitle();
    A.side.setCurrent(place);
    state.busy = true;
    try {
      // At one message: the messages up to it and after it; otherwise the newest.
      var r = await get("messages", at ? {"in": place, before: at + 1, limit: PAGE} : {"in": place, limit: PAGE});
      var after = at && r.ok ? await get("messages", {"in": place, after: at, limit: PAGE}) : null;
      if (place !== state.place) return;
      if (!r.ok) { el.out.textContent = A.refusal("msg.load", r.data); return; }
      var msgs = r.data.messages || [], all = msgs.concat(after && after.ok ? after.data.messages || [] : []);
      state.readAt = Number(r.data.read) || 0;
      state.openedLast = all.reduce(function (n, m) { return Math.max(n, m.id); }, 0);
      append(all);
      showEmpty();
      el.older.hidden = msgs.length < PAGE;
      if (at) {
        await jumpTo(at);
      } else {
        toBottom();
        var line = el.list.querySelector("li.unread-line");          // the first unread above the view: start there
        if (line && line.getBoundingClientRect().top < el.scroll.getBoundingClientRect().top) toTop(line);
      }
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
    saveDraft();
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
        // Read only when the reader sees them; otherwise the pill says they are there.
        if (caughtUp()) await markRead(); else noteFresh(r.data.messages);
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

  // ------------------------------------------------------------------ drafts
  //
  // One per place, in sessionStorage: it belongs to this tab (two tabs on one place do not overwrite each other's),
  // survives a reload and the move between chat's and private messages' pages, and is gone with the tab, so no
  // unsent text stays behind in the browser. Refused storage keeps nothing; the page goes on.

  var DRAFT = "asterism-draft:" + SLUG + ":";
  function saveDraft() {
    if (!state.place) return;
    try {
      if (el.text.value) sessionStorage.setItem(DRAFT + state.place, el.text.value);
      else sessionStorage.removeItem(DRAFT + state.place);
    } catch (err) { /* not kept */ }
  }
  function loadDraft() {
    var v = "";
    try { v = sessionStorage.getItem(DRAFT + state.place) || ""; } catch (err) { v = ""; }
    el.text.value = v;
    held = null;
    atClose();
    grow();
  }

  // ------------------------------------------------------------------ completion in the composer: @, # and /

  // The server's rule for a mention: "@" not after a name's character, then the name's characters; a name that is
  // nobody loses its trailing ".", "_" or "-" before it is given up.
  var MENTION_RE = /(^|[^A-Za-z0-9._-])@([A-Za-z0-9._-]+)/g;
  var AT_MAX = 12;
  // The commands a person gives an agent of theirs (1x): `@agent /command ...` at the start of a message. What each
  // puts into the composer; the ones that take an argument leave the caret after a space.
  var COMMANDS = [{name: "/goal", insert: "/goal ", hint: "msg.cmd_hint.goal"},
                  {name: "/goal clear", insert: "/goal clear", hint: "msg.cmd_hint.goal_clear"},
                  {name: "/compact", insert: "/compact", hint: "msg.cmd_hint.compact"},
                  {name: "/model", insert: "/model ", hint: "msg.cmd_hint.model"}];
  var atList = make("ul", "mention-list");
  atList.id = "mention-list";
  atList.setAttribute("role", "listbox");
  atList.setAttribute("aria-label", t("msg.at_label"));
  atList.hidden = true;
  el.form.appendChild(atList);
  el.text.setAttribute("aria-autocomplete", "list");
  el.text.setAttribute("aria-controls", "mention-list");
  el.text.setAttribute("aria-expanded", "false");
  var at = {options: [], active: -1, start: -1, shut: -1};

  function isMyAgent(name) {
    var v = A.side.members;
    return !!v && (v.agents || []).some(function (a) { return a.name === name && a.owner === ME; });
  }

  // What is being completed at the caret, or null: {kind, start, end, query}, where kind is
  // - "/": a command right after "@<an agent of mine> " at the very start of the text (any place);
  // - "@": a name to mention (a channel only: a private message mentions nobody);
  // - "#": a channel's name (any place).
  function atToken() {
    if (el.text.selectionStart !== el.text.selectionEnd) return null;
    var caret = el.text.selectionStart, before = el.text.value.slice(0, caret), m;
    if ((m = /^@([A-Za-z0-9._-]+) \/([A-Za-z]*)$/.exec(before)) && isMyAgent(m[1])) {
      return {kind: "/", start: caret - m[2].length - 1, end: caret, query: m[2]};
    }
    if (isChannel(state.place) && (m = /(^|[^A-Za-z0-9._-])@([A-Za-z0-9._-]*)$/.exec(before))) {
      return {kind: "@", start: caret - m[2].length - 1, end: caret, query: m[2]};
    }
    if ((m = /(^|[^A-Za-z0-9._#-])#([a-z0-9-]*)$/.exec(before))) {
      return {kind: "#", start: caret - m[2].length - 1, end: caret, query: m[2]};
    }
    return null;
  }

  // Whom a mention can name, in the order offered: my agents, the other agents and the people (not me), the groups.
  function mentionable() {
    var v = A.side.members, out = [];
    if (v) {
      var agents = v.agents || [];
      agents.filter(function (a) { return a.owner === ME; }).forEach(function (a) {
        out.push({name: a.name, kind: "agent", model: a.model, who: a, note: t("nav.my_agent")});
      });
      agents.filter(function (a) { return a.owner !== ME; }).forEach(function (a) {
        out.push({name: a.name, kind: "agent", model: a.model, who: a,
                  note: a.owner ? t("msg.agent_of", {owner: a.owner}) : t("msg.kind_agent")});
      });
      (v.people || []).filter(function (p) { return p.name !== ME; }).forEach(function (p) {
        out.push({name: p.name, kind: "person", note: ""});
      });
      (v.groups || []).forEach(function (g) {
        out.push({name: g.name, kind: "group",
                  note: g.kind === "ownership" && g.owner ? t("group.ownership", {owner: g.owner}) : t("msg.at_group")});
      });
    } else {                              // before the members are read: the names the page came with
      Object.keys(A.side.directory).forEach(function (n) {
        var d = A.side.directory[n];
        if (n !== ME) out.push({name: n, kind: d.kind, note: d.owner === ME ? t("nav.my_agent") : ""});
      });
    }
    return out.map(function (o) { return Object.assign(o, {key: o.name, insert: "@" + o.name + " "}); });
  }

  // The channels the reader may read, in their order.
  function channelChoices() {
    var p = A.side.places;
    return (p ? p.channels : []).map(function (c) {
      return {key: c.name, name: "#" + c.name, kind: "channel", insert: "#" + c.name + " ", note: ""};
    });
  }

  function commandChoices() {
    return COMMANDS.map(function (c) {
      return {key: c.name.slice(1), name: c.name, kind: "command", insert: c.insert, note: t(c.hint)};
    });
  }

  function atOption(o, i) {
    var li = make("li", "mention-option" + (o.kind === "command" ? " command-option" : ""));
    li.id = "mention-opt-" + i;
    li.setAttribute("role", "option");
    if (o.kind === "group" || o.kind === "channel" || o.kind === "command") li.appendChild(make("span", "mention-mark"));
    else li.appendChild(A.side.presence(A.side.directory[o.name] || {kind: o.kind}));
    li.appendChild(make("span", "mono mention-name", o.name));
    var model = o.kind === "agent" ? A.modelTag(o.model) : null;
    if (model) li.appendChild(model);
    var work = o.kind === "agent" && o.who ? A.side.workText(o.who) : "";
    if (work) li.appendChild(make("span", "dim", work));
    if (o.note) li.appendChild(make("span", "dim mention-note", o.note));
    li.addEventListener("mousedown", function (ev) { ev.preventDefault(); atChoose(i); });
    return li;
  }

  var LIST_LABEL = {"@": "msg.at_label", "#": "msg.hash_label", "/": "msg.cmd_label"};
  function atDraw() {
    var tok = atToken();
    if (!tok) at.shut = -1;                         // Escape shuts the list for that one token only
    if (!tok || tok.start === at.shut) { atClose(); return; }
    var q = tok.query.toLowerCase();
    var all = tok.kind === "/" ? commandChoices() : tok.kind === "#" ? channelChoices() : mentionable();
    // Names starting with what was typed first, then names holding it; each in the order above.
    var ranked = all.map(function (o, i) {
      var low = o.key.toLowerCase(), where = low.indexOf(q);
      return {o: o, i: i, score: where === 0 ? 0 : where > 0 ? 1 : 2};
    }).filter(function (x) { return x.score < 2; });
    ranked.sort(function (a, b) { return a.score - b.score || a.i - b.i; });
    at.options = ranked.slice(0, AT_MAX).map(function (x) { return x.o; });
    if (!at.options.length) { atClose(); return; }
    at.start = tok.start;
    atList.setAttribute("aria-label", t(LIST_LABEL[tok.kind]));
    atList.textContent = "";
    at.options.forEach(function (o, i) { atList.appendChild(atOption(o, i)); });
    atList.hidden = false;
    el.text.setAttribute("aria-expanded", "true");
    atActive(0);
  }

  function atActive(i) {
    at.active = i;
    Array.prototype.forEach.call(atList.children, function (li, j) { li.setAttribute("aria-selected", String(j === i)); });
    var li = atList.children[i];
    if (li) {
      el.text.setAttribute("aria-activedescendant", li.id);
      li.scrollIntoView({block: "nearest"});
    } else {
      el.text.removeAttribute("aria-activedescendant");
    }
  }

  function atClose() {
    if (atList.hidden) return;
    atList.hidden = true;
    at.options = [];
    el.text.setAttribute("aria-expanded", "false");
    el.text.removeAttribute("aria-activedescendant");
  }

  // Taking a choice puts its text in the token's place; it never sends.
  function atChoose(i) {
    var o = at.options[i], tok = atToken();
    if (!o || !tok) { atClose(); return; }
    var v = el.text.value, put = o.insert;
    el.text.value = v.slice(0, tok.start) + put + v.slice(tok.end).replace(/^ /, "");
    var caret = tok.start + put.length;
    el.text.setSelectionRange(caret, caret);
    atClose();
    grow();
    saveDraft();
    el.text.focus();
  }

  // The names mentioned in `text` that are no member or group (in a channel, once the members are known).
  function unknownMentions(text) {
    var v = A.side.members;
    if (!v || !isChannel(state.place)) return [];
    var names = new Set();
    (v.people || []).concat(v.agents || [], v.groups || []).forEach(function (x) { names.add(x.name); });
    var out = [], m;
    MENTION_RE.lastIndex = 0;
    while ((m = MENTION_RE.exec(text))) {
      var cand = m[2];
      while (cand && !names.has(cand) && /[._-]$/.test(cand)) cand = cand.slice(0, -1);
      if (cand && !names.has(cand) && out.indexOf(cand) < 0) out.push(cand);
    }
    return out;
  }

  // ------------------------------------------------------------------ sending

  // The words a refused command needs: the agent it names and that agent's person.
  function commandVars(text) {
    var m = /^@([A-Za-z0-9._-]+) \//.exec(text), who = m && A.side.directory[m[1]];
    return m ? {agent: m[1], person: (who && who.owner) || "?"} : {};
  }

  var held = null;                        // the text held back once for a mention of nobody

  async function send() {
    var text = el.text.value;
    if (!text.trim() || !state.place) return;
    // A command to an agent mentions nobody (the server's rule): nothing in it is held back.
    var unknown = /^@[A-Za-z0-9._-]+ \/(goal|compact|model)(\s|$)/.test(text) ? [] : unknownMentions(text);
    if (unknown.length && held !== text) {          // said in place; sending the same text again sends it
      held = text;
      el.out.textContent = t("msg.unknown_hold", {names: unknown.map(function (n) { return "@" + n; }).join(", ")});
      return;
    }
    held = null;
    var body = {to: state.place, text: text};
    if (state.replyTo) body.reply_to = state.replyTo;
    var place = state.place;
    var r = await post("messages", body);
    if (!r.ok) { el.out.textContent = A.refusal("msg.send", r.data, commandVars(text)); return; }
    if (place === state.place) {
      el.text.value = "";
      grow();
      setReply(null);
      var c = r.data.command;
      el.out.textContent = c ? (c.delivered ? t("msg.cmd.sent", {agent: c.agent, command: "/" + c.command}) : "")
                             : outcome(r.data.mentions);
    }
    try { sessionStorage.removeItem(DRAFT + place); } catch (err) { /* nothing kept */ }
    await news();
    toBottom();
    seen();
  }

  // ------------------------------------------------------------------ wiring

  el.text.addEventListener("keydown", function (ev) {
    var composing = ev.isComposing || ev.keyCode === 229;
    if (!atList.hidden && !composing) {             // the list of names: arrows move, Enter or Tab take, Escape shuts
      var n = at.options.length;
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        atActive((at.active + (ev.key === "ArrowDown" ? 1 : n - 1)) % n);
        return;
      }
      if ((ev.key === "Enter" && !ev.shiftKey) || ev.key === "Tab") {
        ev.preventDefault();
        atChoose(at.active < 0 ? 0 : at.active);
        return;
      }
      if (ev.key === "Escape") {
        ev.preventDefault();
        ev.stopPropagation();
        at.shut = at.start;
        atClose();
        return;
      }
    }
    // Enter sends; Shift+Enter is a new line; Enter that ends an input-method composition does neither.
    if (ev.key === "Enter" && !ev.shiftKey && !composing) {
      ev.preventDefault();
      send();
    } else if (ev.key === "Escape" && state.replyTo) {
      setReply(null);
    }
  });
  el.text.addEventListener("input", function () {
    grow();
    saveDraft();
    if (held !== null && el.text.value !== held) { held = null; el.out.textContent = ""; }
    atDraw();
  });
  // The caret moved without typing: the list follows the name at the caret.
  el.text.addEventListener("keyup", function (ev) {
    if (/^(ArrowLeft|ArrowRight|Home|End)$/.test(ev.key)) atDraw();
  });
  el.text.addEventListener("click", atDraw);
  el.text.addEventListener("blur", atClose);
  el.form.addEventListener("submit", function (ev) { ev.preventDefault(); send(); });
  el.replyCancel.addEventListener("click", function () { setReply(null); el.text.focus(); });
  el.older.addEventListener("click", loadOlder);
  // Chat's places are its hash; a private conversation named there (an older address) has its own page now.
  function start() {
    var place = placeFromHash();
    if (!place) { nothingChosen(); return; }          // no channel the reader may read, or no conversation chosen
    if (MODE === "chat" && !isChannel(place)) { window.location.replace(addressOf(place)); return; }
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
