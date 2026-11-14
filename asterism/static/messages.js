// The messages page: the places on the left, the messages of the chosen place, the input box.
// It speaks only the project's JSON API (/api/channels, /api/messages, /api/read, mute, new channel) and asks
// for news every few seconds. All texts come from the page's message catalogue (body data-msg).
//
// Message text is hostile input. It is rendered as Markdown with these rules: raw HTML in a message is shown
// as text, Markdown images become plain links, and the HTML that Markdown produces goes through DOMPurify
// with a strict allow-list (no scripts, no event attributes, no iframes/objects/forms/images, only http(s)
// and mailto links, which open with rel="noopener noreferrer"). Mathematics ($...$, $$...$$) is taken out
// before Markdown sees it and drawn by KaTeX (trust off) into elements this script creates.
"use strict";
(function () {
  var root = document.getElementById("chat");
  if (!root || !window.marked || !window.DOMPurify || !window.katex) return;

  function parseJSON(raw, fallback) {
    try { return JSON.parse(raw); } catch (err) { return fallback; }
  }
  var MSG = parseJSON(document.body.dataset.msg || "{}", {});
  function t(key, vars) {
    var s = MSG[key] || key;
    Object.keys(vars || {}).forEach(function (k) { s = s.split("{" + k + "}").join(String(vars[k])); });
    return s;
  }
  function errorText(code) {
    return MSG["error." + code] || (MSG["error.generic"] || "{code}").replace("{code}", code || "?");
  }

  var SLUG = root.dataset.slug;
  var AGENTS = parseJSON(root.dataset.agents, []);
  var AGENT_MUTES = parseJSON(root.dataset.agentMutes, {});
  var API = "/" + encodeURIComponent(SLUG) + "/api/";
  var PAGE = 50, NEWS_EVERY_MS = 4000;

  var el = {
    channels: document.getElementById("channels"), privates: document.getElementById("privates"),
    title: document.getElementById("place-title"), list: document.getElementById("messages"),
    older: document.getElementById("older"), settings: document.getElementById("settings"),
    settingsToggle: document.getElementById("settings-toggle"), form: document.getElementById("composer"),
    text: document.getElementById("text"), out: document.getElementById("composer-out"),
    reply: document.getElementById("reply-target"), replyCancel: document.getElementById("reply-cancel"),
    newChannel: document.getElementById("new-channel"), newPrivate: document.getElementById("new-private")
  };
  var state = {place: null, first: 0, last: 0, replyTo: null, places: {channels: [], "private": []}, busy: false};

  // ------------------------------------------------------------------ the JSON API

  async function call(method, path, params, body) {
    var url = new URL(API + path, window.location.origin);
    Object.keys(params || {}).forEach(function (k) { url.searchParams.set(k, params[k]); });
    var opts = {method: method, credentials: "same-origin", headers: {"Accept": "application/json"}};
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    var data = {}, r;
    try {
      r = await fetch(url, opts);
      data = await r.json();
    } catch (err) {
      return {ok: false, data: {error: "network"}};
    }
    return {ok: r.ok, data: data || {}};
  }
  function get(path, params) { return call("GET", path, params); }
  function post(path, body) { return call("POST", path, null, body); }

  // ------------------------------------------------------------------ rendering a text safely

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }
  var md = new window.marked.Marked();
  md.use({
    gfm: true, breaks: true,
    renderer: {
      html: function (html) {                    // raw HTML in a message is shown, never interpreted
        return escapeHtml(typeof html === "string" ? html : (html && (html.raw || html.text)) || "");
      },
      image: function (href, title, text) {      // never load an image: show it as a link
        if (href && typeof href === "object") { text = href.text; href = href.href; }
        return '<a href="' + escapeHtml(href || "") + '">' + escapeHtml(text || href || "") + "</a>";
      }
    }
  });
  var PURIFY = {
    ALLOWED_TAGS: ["p", "br", "hr", "em", "strong", "del", "s", "code", "pre", "blockquote", "ul", "ol", "li",
                   "h1", "h2", "h3", "h4", "h5", "h6", "a", "table", "thead", "tbody", "tr", "th", "td"],
    ALLOWED_ATTR: ["href", "title", "start", "align"],
    ALLOWED_URI_REGEXP: /^(?:https?:|mailto:)/i,
    ALLOW_DATA_ATTR: false,
    RETURN_DOM_FRAGMENT: true
  };
  window.DOMPurify.addHook("afterSanitizeAttributes", function (node) {
    if (node.tagName === "A" && node.hasAttribute("href")) {
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer");
    }
  });
  // Code first, so that a $ inside code stays code; then display and inline mathematics.
  var MATH_RE = /(```[\s\S]*?```|`[^`\n]*`)|\$\$([\s\S]+?)\$\$|\$(?![\s$])([^$\n]*?[^\s$\\])\$/g;
  var MARK_OPEN = "", MARK_CLOSE = "";

  function renderText(text) {
    var maths = [];
    var src = String(text).replace(MATH_RE, function (all, code, display, inline) {
      if (code) return all;
      maths.push({tex: display !== undefined ? display : inline, display: display !== undefined});
      return MARK_OPEN + (maths.length - 1) + MARK_CLOSE;
    });
    var box = document.createElement("div");
    box.className = "text";
    box.appendChild(window.DOMPurify.sanitize(md.parse(src, {async: false}), PURIFY));
    if (maths.length) drawMaths(box, maths);
    return box;
  }

  function drawMaths(box, maths) {
    var walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT), nodes = [], n;
    while ((n = walker.nextNode())) if (n.nodeValue.indexOf(MARK_OPEN) >= 0) nodes.push(n);
    var mark = new RegExp(MARK_OPEN + "(\\d+)" + MARK_CLOSE, "g");
    nodes.forEach(function (node) {
      var frag = document.createDocumentFragment(), at = 0, m, s = node.nodeValue;
      mark.lastIndex = 0;
      while ((m = mark.exec(s))) {
        frag.appendChild(document.createTextNode(s.slice(at, m.index)));
        var item = maths[Number(m[1])], span = document.createElement("span");
        try {
          window.katex.render(item.tex, span, {displayMode: item.display, throwOnError: false, trust: false,
                                                strict: "ignore", maxSize: 50, maxExpand: 1000});
        } catch (err) {
          span.textContent = item.display ? "$$" + item.tex + "$$" : "$" + item.tex + "$";
        }
        frag.appendChild(span);
        at = m.index + m[0].length;
      }
      frag.appendChild(document.createTextNode(s.slice(at)));
      node.parentNode.replaceChild(frag, node);
    });
  }

  // ------------------------------------------------------------------ places

  function placeFromHash() {
    var raw = window.location.hash.slice(1);
    try { raw = decodeURIComponent(raw); } catch (err) { raw = ""; }
    return raw || "#general";
  }
  function hashOf(place) { return "#" + encodeURIComponent(place); }

  function placeItem(place, label, unread, important) {
    var li = document.createElement("li"), a = document.createElement("a");
    a.href = hashOf(place);
    a.textContent = label;
    if (place === state.place) a.className = "current";
    li.appendChild(a);
    if (unread) {
      var c = document.createElement("span");
      c.className = "count" + (important ? " important" : "");
      c.textContent = String(unread);
      c.title = t("msg.unread", {n: unread}) + (important ? " · " + t("msg.important") : "");
      li.appendChild(document.createTextNode(" "));
      li.appendChild(c);
    }
    return li;
  }

  function drawPlaces() {
    var p = state.places;
    el.channels.textContent = "";
    p.channels.forEach(function (c) {
      el.channels.appendChild(placeItem("#" + c.name, "#" + c.name, c.unread, c.important));
    });
    el.privates.textContent = "";
    var seen = false;
    p["private"].forEach(function (c) {
      if (c["with"] === state.place) seen = true;
      el.privates.appendChild(placeItem(c["with"], c["with"], c.unread, c.important));
    });
    if (state.place && state.place.charAt(0) !== "#" && !seen) {   // a conversation not started yet
      el.privates.insertBefore(placeItem(state.place, state.place, 0, 0), el.privates.firstChild);
    }
  }

  async function loadPlaces() {
    var r = await get("channels");
    if (r.ok) {
      state.places = {channels: r.data.channels || [], "private": r.data["private"] || []};
      drawPlaces();
    }
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
    el.list.scrollTop += anchor.getBoundingClientRect().top - before;
  }

  function foldButton(onClick) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "fold-toggle";
    b.setAttribute("aria-expanded", "false");
    b.addEventListener("click", onClick);
    return b;
  }

  // A long message: clamped by CSS (the whole text is rendered underneath), decided by its rendered height.
  // Once the person chose, nothing folds or opens it again by itself.
  function clampable(li, box, id) {
    var key = "long:" + id;
    box.id = "t-" + id;
    var button = foldButton(function () {
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

  function isMessage(li) { return li.id && li.id.indexOf("m-") === 0; }
  function idOf(li) { return Number(li.id.slice(2)); }

  // Runs of three or more system notices fold into one row. A notice that is important for the viewer is
  // never folded: it ends the run. Called after every change of the list.
  function regroup() {
    var items = Array.prototype.filter.call(el.list.children, isMessage), runs = [], cur = [];
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
      var time = last.sent_at ? new Date(last.sent_at).toLocaleTimeString(document.documentElement.lang,
                                                                         {hour: "numeric", minute: "2-digit"}) : "";
      var button = row.firstChild;
      button.setAttribute("aria-expanded", String(open));
      button.textContent = open ? t("msg.fold_run", {n: ids.length})
                                : t("msg.folded_run", {n: ids.length, text: last.text || "", time: time});
    });
    rows.forEach(function (r, first) { if (!used.has(first)) r.remove(); });
  }

  function runRow() {
    var row = document.createElement("li");
    row.className = "fold system";
    row.appendChild(foldButton(function () {
      toggleBlock(row, function () { setRun(row._ids, row.firstChild.getAttribute("aria-expanded") !== "true"); });
    }));
    return row;
  }

  function setRun(ids, open) {
    ids.forEach(function (id) { if (open) folds.set("run:" + id, true); else folds.delete("run:" + id); });
    regroup();
  }

  // The messages added to the list are fitted (long ones clamped) once they are in the page.
  function settle(added) {
    regroup();
    added.forEach(function (li) { if (li._fit) li._fit(); });
  }

  // ------------------------------------------------------------------ messages

  var known = new Map();                  // message id -> the message object, for the folded rows

  function messageItem(m) {
    known.set(m.id, m);
    var li = document.createElement("li");
    li.id = "m-" + m.id;
    li.className = (m.from_kind === "system" ? "system " : "") + (m.level === "important" ? "important" : "");
    var meta = document.createElement("div");
    meta.className = "meta";
    var from = document.createElement("span");
    from.className = "from";
    from.textContent = m.from_kind === "system" ? t("msg.system") : m.from;
    meta.appendChild(from);
    if (m.from_kind === "agent") {
      var tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = t("msg.kind_agent");
      meta.appendChild(tag);
    }
    if (m.level === "important") {
      var imp = document.createElement("span");
      imp.className = "tag";
      imp.textContent = t("msg.important");
      meta.appendChild(imp);
    }
    var when = document.createElement("time");
    when.dateTime = m.sent_at;
    when.textContent = " " + new Date(m.sent_at).toLocaleString(document.documentElement.lang) + " · #" + m.id + " ";
    meta.appendChild(when);
    if (m.reply_to) {
      var link = document.createElement("a");
      link.href = "#";
      link.textContent = t("msg.reply_to_link", {id: m.reply_to});
      link.addEventListener("click", function (ev) { ev.preventDefault(); jumpTo(m.reply_to); });
      meta.appendChild(link);
      meta.appendChild(document.createTextNode(" "));
    }
    if (m.from_kind !== "system") {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = t("msg.reply");
      btn.addEventListener("click", function () { setReply(m.id); el.text.focus(); });
      meta.appendChild(btn);
    }
    li.appendChild(meta);
    var box = renderText(m.text);
    li.appendChild(box);
    li.appendChild(clampable(li, box, m.id));
    return li;
  }

  function showEmpty() {
    if (!el.list.children.length) {
      var li = document.createElement("li");
      li.className = "empty muted";
      li.textContent = t("msg.empty");
      el.list.appendChild(li);
    }
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
    var before = el.list.scrollHeight, top = el.list.firstChild, added = [];
    msgs.forEach(function (m) {
      if (document.getElementById("m-" + m.id)) return;
      added.push(el.list.insertBefore(messageItem(m), top));
      if (!state.first || m.id < state.first) state.first = m.id;
      state.last = Math.max(state.last, m.id);
    });
    settle(added);
    el.list.scrollTop += el.list.scrollHeight - before;
  }

  function atBottom() { return el.list.scrollHeight - el.list.scrollTop - el.list.clientHeight < 40; }
  function toBottom() { el.list.scrollTop = el.list.scrollHeight; }

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
    target.classList.add("flash");
    setTimeout(function () { target.classList.remove("flash"); }, 1500);
  }

  async function open(place) {
    state.place = place;
    state.first = 0;
    state.last = 0;
    setReply(null);
    el.list.textContent = "";
    el.out.textContent = "";
    el.title.textContent = place.charAt(0) === "#" ? place : t("msg.private_with", {name: place});
    drawPlaces();
    drawSettings();
    state.busy = true;
    try {
      var r = await get("messages", {"in": place, limit: PAGE});
      if (place !== state.place) return;
      if (!r.ok) { el.out.textContent = errorText(r.data.error); return; }
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
      }
      await loadPlaces();
    } finally {
      state.busy = false;
    }
  }

  // ------------------------------------------------------------------ writing

  function setReply(id) {
    state.replyTo = id;
    el.reply.hidden = !id;
    el.reply.firstChild.textContent = id ? t("msg.replying_to", {id: id}) : "";
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

  async function send() {
    var text = el.text.value;
    if (!text.trim() || !state.place) return;
    var body = {to: state.place, text: text};
    if (state.replyTo) body.reply_to = state.replyTo;
    var r = await post("messages", body);
    if (!r.ok) { el.out.textContent = errorText(r.data.error); return; }
    el.text.value = "";
    setReply(null);
    el.out.textContent = outcome(r.data.mentions);
    await news();
    toBottom();
  }

  // ------------------------------------------------------------------ channel settings

  function settingBox(label, checked, agent) {
    var div = document.createElement("div"), lab = document.createElement("label"), box = document.createElement("input");
    var out = document.createElement("span");
    box.type = "checkbox";
    box.checked = !!checked;
    out.className = "out";
    lab.appendChild(box);
    lab.appendChild(document.createTextNode(" " + label));
    div.appendChild(lab);
    div.appendChild(document.createTextNode(" "));
    div.appendChild(out);
    box.addEventListener("change", async function () {
      var name = state.place.slice(1), body = {muted: box.checked};
      if (agent) body.agent = agent;
      var r = await post("channels/" + encodeURIComponent(name) + "/mute", body);
      if (!r.ok) { box.checked = !box.checked; out.textContent = errorText(r.data.error); return; }
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
    if (!state.place || state.place.charAt(0) !== "#") {
      var p = document.createElement("p");
      p.className = "muted";
      p.textContent = t("msg.settings_private");
      el.settings.appendChild(p);
      return;
    }
    var name = state.place.slice(1);
    var ch = state.places.channels.filter(function (c) { return c.name === name; })[0];
    el.settings.appendChild(settingBox(t("msg.mute_me"), ch && ch.muted, null));
    AGENTS.forEach(function (a) {
      el.settings.appendChild(settingBox(t("msg.mute_agent", {name: a}), (AGENT_MUTES[name] || []).indexOf(a) >= 0, a));
    });
  }

  // ------------------------------------------------------------------ wiring

  el.text.addEventListener("keydown", function (ev) {
    // Enter sends; Shift+Enter is a new line; Enter that ends an input-method composition does neither.
    if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing && ev.keyCode !== 229) {
      ev.preventDefault();
      send();
    }
  });
  el.form.addEventListener("submit", function (ev) { ev.preventDefault(); send(); });
  el.replyCancel.addEventListener("click", function () { setReply(null); });
  el.older.addEventListener("click", loadOlder);
  el.settingsToggle.addEventListener("click", function () {
    el.settings.hidden = !el.settings.hidden;
    el.settingsToggle.setAttribute("aria-expanded", String(!el.settings.hidden));
    if (!el.settings.hidden) drawSettings();
  });
  if (el.newChannel) {
    el.newChannel.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var input = el.newChannel.elements.name, out = el.newChannel.querySelector("[data-out]");
      var name = input.value.trim().replace(/^#/, "");
      var r = await post("channels", {name: name});
      if (!r.ok) { out.textContent = errorText(r.data.error); return; }
      out.textContent = "";
      input.value = "";
      await loadPlaces();
      window.location.hash = hashOf("#" + r.data.name);
    });
  }
  if (el.newPrivate) {
    el.newPrivate.addEventListener("submit", function (ev) {
      ev.preventDefault();
      window.location.hash = hashOf(el.newPrivate.elements["with"].value);
    });
  }
  window.addEventListener("hashchange", function () { open(placeFromHash()); });
  setInterval(news, NEWS_EVERY_MS);
  loadPlaces().then(function () { open(placeFromHash()); });
})();
