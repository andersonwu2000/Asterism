// The messages page, middle column: the chosen place's header, its pins, its messages and the composer.
// It speaks only the project's JSON API (/api/messages, /api/read, mute, pins) and asks for news every few seconds;
// the places (and their unread counts) come from the frame (frame.js, Asterism.side), the text rendering from
// render.js, the task table on the right from tasks.js. All texts come from the page's message catalogue.
"use strict";
(function () {
  var A = window.Asterism;
  var root = document.getElementById("chat");
  if (!root || !A || !A.renderText || !A.side) return;
  var t = A.t, make = A.make;

  var SLUG = root.dataset.slug;
  var AGENTS = A.parseJSON(root.dataset.agents, []);
  var AGENT_MUTES = A.parseJSON(root.dataset.agentMutes, {});
  var API = "/" + encodeURIComponent(SLUG) + "/api/";
  var PAGE = 50, NEWS_EVERY_MS = 4000, GROUP_MS = 5 * 60 * 1000;
  var LANG = document.documentElement.lang || undefined;
  var DOT = " · ";

  var el = {
    title: document.getElementById("place-title"), list: document.getElementById("messages"),
    scroll: document.getElementById("scroller"),
    older: document.getElementById("older"), settings: document.getElementById("settings"),
    settingsToggle: document.getElementById("settings-toggle"), form: document.getElementById("composer"),
    text: document.getElementById("text"), out: document.getElementById("composer-out"),
    reply: document.getElementById("reply-target"), replyCancel: document.getElementById("reply-cancel"),
    pins: document.getElementById("pins")
  };
  var CAN_PIN = !!(el.pins && el.pins.dataset.canPin);
  var state = {place: null, first: 0, last: 0, replyTo: null, places: {channels: [], "private": []}, busy: false};

  function get(path, params) { return A.request(API + path, params); }
  function post(path, body) { return A.request(API + path, null, body); }

  // ------------------------------------------------------------------ places

  function placeFromHash() {
    var raw = window.location.hash.slice(1);
    try { raw = decodeURIComponent(raw); } catch (err) { raw = ""; }
    return raw || "#general";
  }
  function isChannel(place) { return !!place && place.charAt(0) === "#"; }

  A.side.onChange(function (places) {
    state.places = places;
    drawPins();
  });
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

  // A refusal or a note at a message: under its text, where the act was.
  function messageOut(li) {
    var out = li.querySelector(".body > .out");
    if (!out) {
      out = make("div", "out");
      out.setAttribute("aria-live", "polite");
      li.querySelector(".body").appendChild(out);
    }
    return out;
  }

  function messageItem(m) {
    known.set(m.id, m);
    var li = make("li", "msg" + (m.from_kind === "system" ? " system" : "") + (m.level === "important" ? " important" : ""));
    li.id = "m-" + m.id;
    var gutter = make("div", "gutter"), body = make("div", "body");
    var when = make("time", "", clock(m.sent_at));
    when.dateTime = m.sent_at;
    when.title = new Date(m.sent_at).toLocaleString(LANG) + DOT + "#" + m.id;
    gutter.appendChild(when);

    if (m.reply_to) {
      var line = make("div", "reply-line");
      var jump = A.button("link-btn", replyLabel(m.reply_to), function () { jumpTo(m.reply_to); });
      jump.dataset.reply = String(m.reply_to);
      jump.title = t("msg.jump_hint", {id: m.reply_to});
      line.appendChild(jump);
      body.appendChild(line);
    }

    var meta = make("div", "meta");
    meta.appendChild(make("span", "from", senderName(m)));
    if (m.from_kind === "agent") meta.appendChild(make("span", "tag", agentTag(m.from)));
    if (m.scheduled) {
      var sch = make("span", "tag", t("msg.scheduled"));
      sch.title = t("msg.scheduled_hint", {name: m.from});
      meta.appendChild(sch);
    }
    if (m.level === "important") meta.appendChild(make("span", "pill", t("msg.important")));
    meta.appendChild(make("span", "mid", "#" + m.id));
    body.appendChild(meta);

    var box = A.renderText(m.text);
    body.appendChild(box);
    body.appendChild(clampable(li, box, m.id));

    var acts = make("div", "acts");
    acts.setAttribute("role", "group");
    acts.setAttribute("aria-label", t("msg.acts") + " #" + m.id);
    if (m.from_kind !== "system") {
      acts.appendChild(A.button("", t("msg.reply"), function () { setReply(m.id); el.text.focus(); }));
    }
    if (CAN_PIN && isChannel(m["in"])) {
      acts.appendChild(A.button("", t("msg.pin"), function () { addPin({message: m.id}, messageOut(li)); }));
    }
    if (acts.children.length) {
      var mid = make("span", "mid", "#" + m.id);
      mid.setAttribute("aria-hidden", "true");
      acts.appendChild(mid);
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
    if (!target) { el.out.textContent = t("msg.not_here", {id: id}); return; }
    if (target.hidden && target.dataset.run) {          // inside a folded run: open it first
      var row = el.list.querySelector('li.fold[data-first="' + target.dataset.run + '"]');
      if (row) setRun(row._ids, true);
    }
    target.scrollIntoView({block: "center"});
    target.tabIndex = -1;
    target.focus({preventScroll: true});
    target.classList.add("flash");
    setTimeout(function () { target.classList.remove("flash"); }, 1500);
  }

  async function open(place) {
    state.place = place;
    state.first = 0;
    state.last = 0;
    setReply(null);
    known.clear();
    el.list.textContent = "";
    el.out.textContent = "";
    el.title.textContent = isChannel(place) ? place : t("msg.private_with", {name: place});
    A.side.setCurrent(place);
    drawSettings();
    drawPins();
    state.busy = true;
    try {
      var r = await get("messages", {"in": place, limit: PAGE});
      if (place !== state.place) return;
      if (!r.ok) { el.out.textContent = A.errorText(r.data.error); return; }
      var msgs = r.data.messages || [];
      append(msgs);
      showEmpty();
      el.older.hidden = msgs.length < PAGE;
      toBottom();
      await markRead();
      await loadPlaces();
    } finally {
      state.busy = false;
    }
  }

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
    el.reply.firstChild.textContent = id ? t("msg.replying_to", {id: id}) + (m ? DOT + senderName(m) + ": " + snippet(m.text) : "") : "";
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

  // ------------------------------------------------------------------ channel settings

  function settingBox(label, checked, agent) {
    var div = make("div", "check"), lab = make("label"), box = make("input"), out = make("span", "out");
    box.type = "checkbox";
    box.checked = !!checked;
    lab.append(box, document.createTextNode(" " + label));
    div.append(lab, document.createTextNode(" "), out);
    box.addEventListener("change", async function () {
      var name = state.place.slice(1), body = {muted: box.checked};
      if (agent) body.agent = agent;
      var r = await post("channels/" + encodeURIComponent(name) + "/mute", body);
      if (!r.ok) { box.checked = !box.checked; out.textContent = A.errorText(r.data.error); return; }
      out.textContent = t("msg.saved");
      if (agent) {
        var list = (AGENT_MUTES[name] || []).filter(function (a) { return a !== agent; });
        if (box.checked) list.push(agent);
        AGENT_MUTES[name] = list;
      } else {
        await loadPlaces();
      }
    });
    return div;
  }

  function drawSettings() {
    el.settings.textContent = "";
    if (!isChannel(state.place)) {
      el.settings.appendChild(make("p", "muted", t("msg.settings_private")));
      return;
    }
    var name = state.place.slice(1);
    var ch = state.places.channels.filter(function (c) { return c.name === name; })[0];
    el.settings.setAttribute("aria-label", t("msg.place_settings", {place: state.place}));
    el.settings.appendChild(settingBox(t("msg.mute_me"), ch && ch.muted, null));
    AGENTS.forEach(function (a) {
      el.settings.appendChild(settingBox(t("msg.mute_agent", {name: a}), (AGENT_MUTES[name] || []).indexOf(a) >= 0, a));
    });
  }

  // ------------------------------------------------------------------ pins
  //
  // One line under the header: a channel's pins, oldest first, as /api/channels gives them, and "all" which opens
  // the whole list under it. A file opens its address in a new tab; a message jumps to that message (loading older
  // ones when needed). A person who may pin (data-can-pin) pins a file by its path in the list and a message with
  // the act on the message, and removes either. Redrawn only when it changed, and never while a path is typed.
  // Private conversations have no pins.

  var pinsShown = "", pinsOpen = false;

  function currentPins() {
    if (!isChannel(state.place)) return null;
    var name = state.place.slice(1);
    var ch = state.places.channels.filter(function (c) { return c.name === name; })[0];
    return ch ? (ch.pins || []) : [];
  }

  function pinText(p) { return "#" + p.message + " " + (p.from || "") + ": " + p.text; }

  function pinLink(p, cls) {
    var link;
    if (p.kind === "file") {
      link = make("a", cls ? cls + " file" : "", p.path);
      link.href = p.url;
      link.target = "_blank";
      link.rel = "noopener";
      link.title = t("pin.file_hint");
    } else {
      link = A.button(cls || "link-btn", null, function () { jumpTo(p.message); });
      link.appendChild(make("span", "", pinText(p)));
      link.title = t("pin.message_hint");
    }
    return link;
  }

  function pinItem(p) {
    var li = make("li");
    li.appendChild(pinLink(p, ""));
    li.appendChild(make("span", "pin-by", t("pin.by", {name: p.by})));
    if (CAN_PIN) {
      var x = A.button("icon-btn small", null, async function () {
        var r = await post("channels/" + encodeURIComponent(state.place.slice(1)) + "/pins/" + p.id + "/remove", {});
        if (!r.ok) { pinOut(r.data); return; }
        await loadPlaces();
      });
      x.appendChild(make("span", "cross"));
      x.firstChild.setAttribute("aria-hidden", "true");
      x.title = t("pin.remove");
      x.dataset.key = "unpin:" + p.id;
      x.setAttribute("aria-label", t("pin.remove_label", {what: p.kind === "file" ? p.path : "#" + p.message}));
      li.appendChild(x);
    }
    return li;
  }

  function pinOut(data, out) {
    out = out || el.pins.querySelector(".pins-panel .out");
    if (out) out.textContent = A.refusal("pin.refused", data);
  }

  function setPinsOpen(open, refocus) {
    pinsOpen = open;
    pinsShown = "";
    drawPins();
    var more = el.pins.querySelector(".pins-more");
    if (refocus && more) more.focus();
    if (open) {
      var first = el.pins.querySelector(".pins-panel input, .pins-panel a, .pins-panel button");
      if (first) first.focus();
    }
  }

  function drawPins() {
    if (!el.pins) return;
    var list = currentPins();
    var input = el.pins.querySelector("input");
    if (input && input.value && document.activeElement === input) return;
    var key = JSON.stringify([state.place, list, pinsOpen]);
    if (key === pinsShown) return;
    pinsShown = key;
    el.pins.hidden = list === null || (!list.length && !CAN_PIN);
    if (el.pins.hidden) { el.pins.textContent = ""; return; }
    A.keepFocus(el.pins, function () {
      el.pins.textContent = "";
      var bar = make("div", "pins-bar"), chips = make("div", "pins-chips");
      bar.appendChild(make("span", "pins-label", t("pin.title")));
      list.forEach(function (p) {
        var chip = pinLink(p, "pin-chip");
        chip.dataset.key = "pin:" + p.id;
        chips.appendChild(chip);
      });
      if (!list.length) chips.appendChild(make("span", "pins-none", t("pin.none")));
      bar.appendChild(chips);
      var more = A.button("btn quiet pins-more", list.length ? t("pin.all", {n: list.length}) : t("pin.manage"),
                          function () { setPinsOpen(!pinsOpen, false); });
      more.dataset.key = "pins-more";
      more.setAttribute("aria-expanded", String(pinsOpen));
      more.setAttribute("aria-controls", "pins-panel");
      bar.appendChild(more);
      el.pins.appendChild(bar);
      if (!pinsOpen) return;
      var panel = make("div", "pins-panel");
      panel.id = "pins-panel";
      panel.setAttribute("role", "region");
      panel.setAttribute("aria-label", t("pin.list_label"));
      var ul = make("ul");
      list.forEach(function (p) { ul.appendChild(pinItem(p)); });
      panel.appendChild(ul);
      if (CAN_PIN) {
        var form = make("form", "pin-add"), path = make("input"), out = make("span", "out");
        path.name = "path";
        path.maxLength = 300;
        path.required = true;
        path.placeholder = t("pin.path");
        path.dataset.key = "pin-path";
        path.setAttribute("aria-label", t("pin.path"));
        var btn = make("button", "btn", t("pin.add_file"));
        form.append(path, btn, out);
        form.addEventListener("submit", function (ev) {
          ev.preventDefault();
          if (path.value.trim()) addPin({path: path.value}, out);
        });
        panel.appendChild(form);
      }
      panel.addEventListener("keydown", function (ev) {
        if (ev.key === "Escape") { ev.stopPropagation(); setPinsOpen(false, true); }
      });
      el.pins.appendChild(panel);
    });
  }

  async function addPin(body, out) {
    if (!isChannel(state.place)) return;
    var r = await post("channels/" + encodeURIComponent(state.place.slice(1)) + "/pins", body);
    if (!r.ok) { pinOut(r.data, out); return; }
    if (out) out.textContent = "";
    var input = el.pins.querySelector("input");
    if (input) input.value = "";
    await loadPlaces();
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
  el.settingsToggle.addEventListener("click", function () {
    el.settings.hidden = !el.settings.hidden;
    el.settingsToggle.setAttribute("aria-expanded", String(!el.settings.hidden));
    if (!el.settings.hidden) drawSettings();
  });
  window.addEventListener("hashchange", function () { open(placeFromHash()); });
  setInterval(news, NEWS_EVERY_MS);
  loadPlaces().then(function () { open(placeFromHash()); });
})();
