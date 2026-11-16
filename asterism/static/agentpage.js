// The agent page (#agent-page, m1f5_agent_page_design.md): what its three tabs (agents.js, tasktable.js, schedules.js)
// share, Asterism.agentPage.
// - The scope of the tab shown is the address's query, changed in place with history.pushState (the data is already
//   loaded); an unknown value shows the tab's first scope. The second column (#agent-scopes) lists the tab's scopes as
//   chat lists its places, under small headings: the chosen one is the current place, a count is plain dim text and
//   absent when 0. Below 900 px the column is in the drawer, so the content starts with one line naming the scope
//   with its count (#scope-line), a button that opens the drawer.
// - The rail's agent button returns to the address last shown here (without an open form).
// - A tab redraws only when its data changed, never while an act is armed, a menu or a floating box is open, or the
//   tab says it is busy (a form being written); what it missed is drawn as soon as that is over. The focus is kept
//   (A.keepFocus, data-key).
// - Every row's acts are behind one "..." control (G.acts), also opened by right click, the context-menu key and
//   Shift+F10 on the row (G.menuOn).
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("agent-page");
  if (!A || !root) return;
  var t = A.t, make = A.make;
  var SLUG = root.dataset.slug, TAB = root.dataset.tab;
  var scopes = document.getElementById("agent-scopes"), line = document.getElementById("scope-line");
  var LANG = document.documentElement.lang || undefined, EVERY_MS = 4000;
  var G = A.agentPage = {
    slug: SLUG, me: root.dataset.me, tab: TAB, api: "/" + encodeURIComponent(SLUG) + "/api/",
    home: "/" + encodeURIComponent(SLUG) + "/agent",
    canEditTasks: !!root.dataset.canEditTasks, canManage: !!root.dataset.canManage, canCreate: !!root.dataset.canCreate
  };
  G.base = G.home + (TAB === "agents" ? "" : "/" + TAB);
  var tab = null;              // what the tab registered: {scopes(), current(), draw(), title(), busy()}
  var pending = false;

  // ------------------------------------------------------------------ the scope in the address

  G.params = function () { return new URLSearchParams(window.location.search); };
  G.href = function (query) { return G.base + (query ? "?" + query : ""); };

  function remember() {
    var p = G.params();
    p.delete("new");
    var q = p.toString();
    if (A.rail && A.rail.agentKey) A.store.set(A.rail.agentKey, G.base + (q ? "?" + q : ""));
  }

  // Show another scope (a query, "" for the first): the address changes in place; `replace` keeps the history.
  G.go = function (query, replace) {
    var url = G.href(query);
    if (url !== window.location.pathname + window.location.search) {
      window.history[replace ? "replaceState" : "pushState"](null, "", url);
    }
    remember();
    G.redraw(true);
  };
  window.addEventListener("popstate", function () { remember(); G.redraw(true); });

  // ------------------------------------------------------------------ the column of scopes

  // A scope row: {query, label, count, mono, presence: {kind, online}}; a heading: {heading}.
  function drawScopes() {
    var list = tab.scopes(), cur = tab.current(), sec = null, ul = null;
    scopes.textContent = "";
    list.forEach(function (x) {
      if (x.heading !== undefined) {
        sec = make("section", "side-sec");
        var head = make("div", "side-head");
        head.appendChild(make("h2", "", x.heading));
        ul = make("ul", "side-list");
        sec.append(head, ul);
        scopes.appendChild(sec);
        return;
      }
      var li = make("li", "place-row"), a = make("a", "place");
      a.href = G.href(x.query);
      a.dataset.query = x.query;
      a.dataset.key = "scope:" + x.query;
      if (x.query === cur) a.setAttribute("aria-current", "page");
      if (x.presence && A.side) a.appendChild(A.side.presence(x.presence));
      a.appendChild(make("span", "place-name" + (x.mono ? " mono" : ""), x.label));
      if (x.count) {
        var c = make("span", "count", String(x.count));
        c.setAttribute("aria-hidden", "true");
        a.append(c, make("span", "vh", t("tt.count", {n: x.count})));
      }
      li.appendChild(a);
      ul.appendChild(li);
    });
    var title = tab.title();
    line.hidden = !title;
    line.textContent = title;
  }
  scopes.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest("a[data-query]");
    if (!a || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
    ev.preventDefault();
    if (A.rail) A.rail.closeDrawer(false);
    G.go(a.dataset.query);
  });
  line.addEventListener("click", function () {
    var open = document.getElementById("side-open");
    if (open) open.click();
  });

  // ------------------------------------------------------------------ drawing

  function blocked() {
    return A.isArmed(root) || A.isArmed(scopes) || !!document.querySelector(".menu.shown") || A.popup.isOpen() ||
           !!document.querySelector("dialog[open]");
  }

  // Draw the tab and its scopes again; without `force`, not while the reader is in the middle of something (with
  // `mine`, the change is the reader's own act or its outcome: only an armed act or an open menu holds it back).
  G.redraw = function (force, mine) {
    if (!tab) return;
    if (!force && (blocked() || (!mine && tab.busy && tab.busy()))) { pending = true; return; }
    pending = false;
    A.keepFocus(root, function () { tab.draw(); });
    A.keepFocus(scopes, drawScopes);
  };

  G.register = function (spec) {
    tab = spec;
    remember();
    G.redraw(true);
  };
  setInterval(function () {
    if (!tab) return;
    if (tab.load) tab.load();
    if (pending) G.redraw(false);
  }, EVERY_MS);

  // ------------------------------------------------------------------ small shared parts

  // A time in the reader's words: "12:02" today, a date with the time otherwise; `days` says today and tomorrow.
  G.time = function (iso, days) {
    var d = new Date(iso);
    if (!iso || isNaN(d.getTime())) return "";
    var now = new Date(), hm = d.toLocaleTimeString(LANG, {hour: "2-digit", minute: "2-digit", hour12: false});
    function same(a, b) { return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate(); }
    var tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    if (same(d, now)) return days ? t("ag.today", {time: hm}) : hm;
    if (days && same(d, tomorrow)) return t("ag.tomorrow", {time: hm});
    var opts = {month: "long", day: "numeric"};
    if (d.getFullYear() !== now.getFullYear()) opts.year = "numeric";
    return d.toLocaleDateString(LANG, opts) + " " + hm;
  };

  // The "..." control of a row: `open(where, opener)` opens its menu.
  G.acts = function (label, key, open) {
    var b = A.button("row-acts");
    b.appendChild(A.glyph("dots"));
    b.setAttribute("aria-label", label);
    b.title = label;
    b.setAttribute("aria-haspopup", "menu");
    b.setAttribute("aria-expanded", "false");
    b.dataset.key = key;
    b.addEventListener("click", function () { open({anchor: b}, b); });
    return b;
  };
  // The same menu by right click, the context-menu key and Shift+F10 on the row (not in a form being written).
  G.menuOn = function (row, b, open) {
    row.addEventListener("contextmenu", function (ev) {
      if (ev.target.closest("form, a, input, textarea")) return;
      ev.preventDefault();
      open({x: ev.clientX, y: ev.clientY}, b);
    });
    row.addEventListener("keydown", function (ev) {
      if (!(ev.key === "ContextMenu" || (ev.key === "F10" && ev.shiftKey)) || ev.target.closest("form")) return;
      ev.preventDefault();
      open({anchor: b}, b);
    });
  };

  // A line of facts joined by " · ": each part a string or a node.
  G.facts = function (cls, parts) {
    var p = make("div", cls);
    parts.filter(function (x) { return x !== null && x !== undefined && x !== ""; }).forEach(function (x, i) {
      if (i) p.appendChild(document.createTextNode(" · "));
      p.appendChild(typeof x === "string" ? document.createTextNode(x) : x);
    });
    return p;
  };

  // A refusal or an outcome said on a row: its .out, for a moment when `brief`.
  G.say = function (out, text, brief) {
    if (!out) return;
    out.textContent = text;
    if (brief) setTimeout(function () { if (out.textContent === text) out.textContent = ""; }, 2500);
  };

  // Long text shown up to four lines; "顯示全部" opens it in place (remembered in `opened` by `key`).
  G.clamp = function (text, key, opened) {
    var box = make("div", "tt-body"), p = make("div", "tt-text" + (opened[key] ? "" : " clamped"), text);
    box.appendChild(p);
    requestAnimationFrame(function () {
      if (opened[key] || !p.isConnected || p.scrollHeight <= p.clientHeight + 1) return;
      var more = A.button("btn tt-more", t("tt.more"), function () {
        opened[key] = true;
        p.classList.remove("clamped");
        more.remove();
      });
      more.dataset.key = "more:" + key;
      box.appendChild(more);
    });
    return box;
  };
})();
