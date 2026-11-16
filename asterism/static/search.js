// Search over messages. The search icon of the top bar (#search-open) opens search in the right column
// (#search-results, right.js): the field (#search-input) at its top, the results under it. Typing offers the filters
// as suggestions (#search-suggest: from: a member, in: a channel or a private conversation); Enter searches. In a
// channel the search starts limited to it, shown as a chip (#search-chip) that can be removed. The results are newest
// first, with the words marked; a result opens its place at that message (Asterism.chat.openAt). Escape clears the
// field, and on an empty field closes search and gives the right column back, as the x does. It speaks only
// /api/search.
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("chat");
  var input = document.getElementById("search-input");
  if (!A || !root || !input || !A.right || !A.chat) return;
  var t = A.t, make = A.make;
  var SLUG = root.dataset.slug, API = "/" + encodeURIComponent(SLUG) + "/api/", PAGE = 25;
  var LANG = document.documentElement.lang || undefined, DOT = " · ";
  var FILTERS = ["from:", "in:"];          // the filters' syntax (as Discord's and Slack's), not interface text
  var chip = document.getElementById("search-chip"), chipText = chip.querySelector(".search-chip-text");
  var chipX = document.getElementById("search-chip-x"), list = document.getElementById("search-suggest");
  var body = document.getElementById("search-body"), summary = document.getElementById("search-summary");
  var close = document.querySelector("#search-results .search-close");
  var scope = {place: null, removed: false};
  var shown = null;                         // the search on show: {params, words, results, more}

  // ------------------------------------------------------------------ the chip: limited to the channel open

  function syncChip() {
    var on = !!scope.place && scope.place.charAt(0) === "#" && !scope.removed;
    chip.hidden = !on;
    if (!on) return;
    chipText.textContent = "in:" + scope.place;
    chipX.setAttribute("aria-label", t("srch.chip_remove", {place: scope.place}));
    chipX.title = t("srch.chip_remove", {place: scope.place});
  }
  A.chat.onOpen(function (place) {
    if (shown) return;                      // a result was opened: the search on show keeps its limit
    scope.place = place;
    scope.removed = false;
    syncChip();
  });
  chipX.addEventListener("click", function () {
    scope.removed = true;
    syncChip();
    input.focus();
  });

  // ------------------------------------------------------------------ what was typed

  function parse(text) {
    var out = {words: [], from: "", "in": ""};
    text.split(/\s+/).filter(Boolean).forEach(function (w) {
      var low = w.toLowerCase();
      if (low.indexOf("from:") === 0 && w.length > 5) out.from = w.slice(5);
      else if (low.indexOf("in:") === 0 && w.length > 3) out["in"] = w.slice(3);
      else out.words.push(w);
    });
    return out;
  }

  // ------------------------------------------------------------------ suggestions

  var options = [], active = -1;

  function lastToken() {
    var v = input.value, cut = v.lastIndexOf(" ") + 1;
    return {start: cut, text: v.slice(cut)};
  }

  function candidates() {
    var tok = lastToken().text, low = tok.toLowerCase(), out = [];
    if (low.indexOf("from:") === 0) {
      var who = low.slice(5), v = A.side.members;
      var names = v ? v.people.map(function (x) { return x.name; }).concat(v.agents.map(function (x) { return x.name; }))
                    : Object.keys(A.side.directory);
      names.filter(function (n) { return n.toLowerCase().indexOf(who) === 0; }).slice(0, 8).forEach(function (n) {
        out.push({text: "from:" + n + " ", label: "from:" + n, hint: A.side.directory[n] && A.side.directory[n].kind === "agent"
                                                                  ? t("msg.kind_agent") : ""});
      });
    } else if (low.indexOf("in:") === 0) {
      var where = low.slice(3), places = A.side.places || {channels: [], "private": []};
      places.channels.map(function (c) { return "#" + c.name; }).concat(places["private"].map(function (p) { return p["with"]; }))
        .filter(function (p) { return p.toLowerCase().indexOf(where) === 0 || p.toLowerCase().indexOf("#" + where) === 0; })
        .slice(0, 8).forEach(function (p) { out.push({text: "in:" + p + " ", label: "in:" + p, hint: ""}); });
    } else if (low.indexOf(":") < 0) {
      FILTERS.filter(function (f) { return f.indexOf(low) === 0; }).forEach(function (f) {
        out.push({text: f, label: f, hint: t(f === "from:" ? "srch.from" : "srch.in")});
      });
    }
    return out;
  }

  function setActive(i) {
    active = i;
    Array.prototype.forEach.call(list.children, function (li, j) { li.setAttribute("aria-selected", String(j === i)); });
    if (i >= 0 && list.children[i]) input.setAttribute("aria-activedescendant", list.children[i].id);
    else input.removeAttribute("aria-activedescendant");
  }

  function suggest() {
    options = candidates();
    list.textContent = "";
    options.forEach(function (o, i) {
      var li = make("li", "search-option");
      li.id = "search-opt-" + i;
      li.setAttribute("role", "option");
      li.append(make("span", "mono", o.label));
      if (o.hint) li.append(make("span", "dim", o.hint));
      li.addEventListener("mousedown", function (ev) { ev.preventDefault(); choose(i); });
      list.appendChild(li);
    });
    var open = options.length > 0 && document.activeElement === input;
    list.hidden = !open;
    input.setAttribute("aria-expanded", String(open));
    setActive(-1);
  }

  function hideSuggestions() {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    setActive(-1);
  }

  function choose(i) {
    var o = options[i], tok = lastToken();
    if (!o) return;
    input.value = input.value.slice(0, tok.start) + o.text;
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
    suggest();
  }

  // ------------------------------------------------------------------ the results

  function placeLabel(place) {
    return place.charAt(0) === "#" ? place : t("msg.private_with", {name: place});
  }
  function when(iso) {
    return new Date(iso).toLocaleString(LANG, {month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit",
                                               hourCycle: "h23"});
  }

  // The text of a message on one line around its first match, every word marked.
  function marked(text, words) {
    var all = String(text).replace(/\s+/g, " ").trim(), low = all.toLowerCase(), first = -1;
    words.forEach(function (w) { var i = low.indexOf(w); if (i >= 0 && (first < 0 || i < first)) first = i; });
    var start = first > 60 ? first - 60 : 0, cut = all.slice(start, start + 260), lowCut = cut.toLowerCase();
    var frag = document.createDocumentFragment(), i = 0;
    if (start > 0) frag.append("…");
    while (i < cut.length) {
      var at = -1, len = 0;
      words.forEach(function (w) {
        var j = lowCut.indexOf(w, i);
        if (j >= 0 && (at < 0 || j < at || (j === at && w.length > len))) { at = j; len = w.length; }
      });
      if (at < 0 || !len) { frag.append(cut.slice(i)); break; }
      if (at > i) frag.append(cut.slice(i, at));
      frag.append(make("mark", "", cut.slice(at, at + len)));
      i = at + len;
    }
    if (start + 260 < all.length) frag.append("…");
    return frag;
  }

  function resultItem(m, words) {
    var li = make("li", "sres");
    var b = A.button("sres-btn", null, function () {
      if (window.matchMedia("(max-width: 899.98px)").matches) A.right.show(null);
      A.chat.openAt(m["in"], m.id);
    });
    b.dataset.key = "res:" + m.id;
    b.title = t("srch.open");
    var head = make("span", "sres-head");
    head.append(make("span", "sres-from", m.from_kind === "system" ? t("msg.system") : m.from),
                make("span", "sres-where", placeLabel(m["in"]) + DOT + when(m.sent_at)));
    var text = make("span", "sres-text");
    text.appendChild(marked(m.text, words));
    b.append(head, text);
    li.appendChild(b);
    return li;
  }

  function draw() {
    var s = shown;
    body.textContent = "";
    summary.textContent = s.results.length ? t(s.more ? "srch.count_more" : "srch.count", {n: s.results.length}) : "";
    if (s.error) { body.appendChild(make("p", "out", s.error)); return; }
    if (!s.results.length) { body.appendChild(make("p", "dim", t("srch.none"))); return; }
    var ul = make("ul", "sres-list");
    s.results.forEach(function (m) { ul.appendChild(resultItem(m, s.words)); });
    body.appendChild(ul);
    if (s.more) {
      var more = A.button("btn quiet sres-more", t("srch.more"), function () { run(true); });
      more.dataset.key = "more";
      body.appendChild(more);
    }
  }

  async function run(next) {
    var s = shown;
    if (next && !s) return;
    if (!next) {
      var typed = parse(input.value), params = {limit: PAGE};
      if (typed.words.length) params.q = typed.words.join(" ");
      if (typed.from) params.from = typed.from;
      if (typed["in"]) params["in"] = typed["in"];
      else if (!chip.hidden) params["in"] = scope.place;
      if (!params.q && !params.from && !params["in"]) return;
      s = shown = {params: params, words: typed.words.map(function (w) { return w.toLowerCase(); }), results: [], more: false};
      summary.textContent = t("srch.searching");
      body.textContent = "";
      A.right.show("search");
    }
    var ask = Object.assign({}, s.params);
    if (next && s.results.length) ask.before = s.results[s.results.length - 1].id;
    var r = await A.request(API + "search", ask);
    if (shown !== s) return;
    if (!r.ok) {
      s.error = A.refusal("srch.refused", r.data);
    } else {
      s.error = null;
      s.results = s.results.concat(r.data.results || []);
      s.more = !!r.data.more;
    }
    A.keepFocus(body, draw);
    if (next && !body.contains(document.activeElement)) {
      var last = body.querySelector(".sres:last-of-type .sres-btn");
      if (last) last.focus();
    }
  }

  // Empty the field and the results; `close`: also close search, the right column going back to what it showed.
  function clear(close) {
    shown = null;
    input.value = "";
    hideSuggestions();
    summary.textContent = "";
    body.textContent = "";
    var place = A.chat.place();
    if (place !== scope.place) { scope.place = place; scope.removed = false; }
    syncChip();
    if (close) {
      A.right.giveBack();
      var opener = document.getElementById("search-open");
      if (opener) opener.focus();
    } else {
      input.focus();
    }
  }

  // ------------------------------------------------------------------ wiring

  input.addEventListener("focus", suggest);
  input.addEventListener("input", suggest);
  input.addEventListener("blur", hideSuggestions);
  input.addEventListener("keydown", function (ev) {
    var open = !list.hidden && options.length;
    if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
      if (!open) { suggest(); return; }
      ev.preventDefault();
      var n = options.length;
      setActive(active < 0 ? (ev.key === "ArrowDown" ? 0 : n - 1) : (active + (ev.key === "ArrowDown" ? 1 : n - 1)) % n);
    } else if (ev.key === "Enter" && !ev.isComposing && ev.keyCode !== 229) {
      ev.preventDefault();
      if (open && active >= 0) { choose(active); return; }
      hideSuggestions();
      run(false);
    } else if (ev.key === "Escape") {
      ev.preventDefault();
      if (open) { hideSuggestions(); return; }
      clear(!input.value && !shown);
    } else if (ev.key === "Backspace" && !input.value && !chip.hidden) {
      scope.removed = true;               // as a chip in a field: Backspace at the start takes it away
      syncChip();
    }
  });
  // The native clear control of a search field clears the search too.
  input.addEventListener("search", function () { if (!input.value) clear(false); });
  if (close) close.addEventListener("click", function () { clear(true); });
  document.getElementById("search-results").addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && !ev.defaultPrevented) { ev.preventDefault(); clear(true); }
  });
  A.right.onShow(function (now) {
    if (now !== "search" && shown) { shown = null; summary.textContent = ""; body.textContent = ""; }
  });
})();
