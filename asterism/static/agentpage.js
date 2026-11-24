// The agent page (m1g_agent_page_design.md; 1g), from the members and the places (frame.js), the statuses
// (statuses.js) and one agent's timeline (/api/agents/{name}/timeline). All texts come from the page's catalogue.
// - The second column (#agent-list): every agent of the project by group (the custom groups in their order, then each
//   person's agent group, else AI). A row: presence, avatar, name, model, what it is doing, and the unread count of
//   the reader's conversation with it (the pill when one is important), its name in ink at 600 while there is one.
// - Top right (#agent-head): the chosen agent (avatar, presence, name, model, what it is doing, the quota of one of
//   mine, kind · owner); at the right one "..." control (#agent-acts: groups, avatar, removal; its outcome said beside
//   it, #agent-said) and "invite agent".
// - The head both views share: the offline line while it is offline (#agent-offline: why, short); the status as a
//   disclosure (#agent-status: its title line is the button; open from 900 px, closed below, the reader's choice kept).
// - Two views (#agent-views): 對話 (#agent-conversation), the reader's private conversation with an agent of theirs,
//   which is the private page's own room (messages.js, mode "agent": one implementation); and 動態 (#agent-timeline),
//   its activity as a log: newest first, one folded line per entry (time, mark, a sentence without its subject, a dim
//   excerpt) under day headings, runs of three or more alike folded into one row, a row opening in place to the whole
//   text and the link to where it is; the filter, "expand all", older entries at the foot, new ones at the top. My own
//   agent opens in 對話 (or the view I chose last), anybody else's in 動態, its only view, with the line saying who may
//   write to it (#tl-other).
// - The address: ?name= (the agent), &view=activity (動態), &m= (對話 at that message; it leaves the address once shown).
//   Back and forward move through agents and views. The rail's agent button returns to the address last shown.
// - Unread: the list's counts; the 對話 tab carries the count only while the list is out of sight and 動態 is shown.
//   Only seeing the end of 對話 reads a message (messages.js); 動態 never does.
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("agent-page");
  if (!A || !root || !A.side || !A.renderText) return;
  var t = A.t, make = A.make, S = A.side, P = A.people, St = A.statuses;
  var SLUG = root.dataset.slug, ME = root.dataset.me, API = "/" + encodeURIComponent(SLUG) + "/api/";
  var HOME = "/" + encodeURIComponent(SLUG) + "/agent";
  var PAGE = 50, EVERY_MS = 4000, RUN_MIN = 3, LANG = document.documentElement.lang || undefined;
  var narrow = window.matchMedia("(max-width: 899.98px)");

  function byId(id) { return document.getElementById(id); }
  var el = {
    list: byId("agent-list"), head: byId("agent-head"), acts: byId("agent-acts"), said: byId("agent-said"),
    offline: byId("agent-offline"), status: byId("agent-status"), views: byId("agent-views"),
    convo: byId("agent-conversation"), log: byId("agent-timeline"), filter: byId("tl-filter"),
    expand: byId("tl-expand"), news: byId("tl-news"), scroll: byId("tl-scroller"), items: byId("tl-list"),
    foot: byId("tl-foot"), older: byId("tl-older"), other: byId("tl-other")
  };
  var VIEW_KEY = "asterism-agent-view:" + SLUG, STATUS_KEY = "asterism-agent-status:" + SLUG;
  var FILTER_KEY = "asterism-agent-filter:" + SLUG;
  var filter = A.store.get(FILTER_KEY, "concerns") === "all" ? "all" : "concerns";

  var chosen = "", view = "";            // the agent shown and its view ("chat" or "activity")
  var mine = null, mineRaw = "";         // /api/my, for the quotas of my agents

  function agents() { return S.members ? S.members.agents || [] : []; }
  function find(name) { return agents().filter(function (a) { return a.name === name; })[0] || null; }
  function rules() { return S.members && P ? P.rules(S.members) : null; }
  function isMine(a) { return !!a && a.owner === ME; }
  function viewsOf(a) { return isMine(a) ? ["chat", "activity"] : ["activity"]; }
  function ownerWord(a) { return isMine(a) ? t("nav.my_agent") : t("mem.agent_of", {owner: a.owner || "?"}); }

  // The reader's conversation with each agent, from the places: name -> {unread, important}.
  function unreadOf(name) {
    var p = S.places && (S.places["private"] || []).filter(function (c) { return c.kind === "agent" && c["with"] === name; })[0];
    return p ? {unread: p.unread || 0, important: p.important || 0} : {unread: 0, important: 0};
  }

  // ------------------------------------------------------------------ the address

  function hrefOf(name, v) {
    var a = find(name), q = "?name=" + encodeURIComponent(name);
    return HOME + q + (v === "activity" && isMine(a) ? "&view=activity" : "");
  }
  // The view an agent opens in: another person's agent, 動態; mine, 對話 when its conversation has unread messages,
  // else the view I chose last (對話 until I choose).
  function defaultView(a) {
    if (!isMine(a)) return "activity";
    if (unreadOf(a.name).unread) return "chat";
    return A.store.get(VIEW_KEY, "chat") === "activity" ? "activity" : "chat";
  }

  // ------------------------------------------------------------------ the list

  function sections() {
    var v = S.members, R = rules();
    if (!v || !R) return [];
    var list = agents(), out = [], placed = {};
    function place(g, home) {
      var here = list.filter(function (a) { return !placed[a.name] && home(a) === g.name; });
      here.forEach(function (a) { placed[a.name] = true; });
      if (here.length) out.push({title: R.label(g), agents: here});
    }
    function firstOf(kind) {
      return function (a) {
        var g = R.plainOf(a).filter(function (x) { return kind === "ownership" ? x.kind === kind : x.kind !== "ownership"; })[0];
        return g ? g.name : null;
      };
    }
    v.groups.forEach(function (g) { if (!R.isDefault(g) && g.kind !== "ownership") place(g, firstOf("custom")); });
    v.groups.forEach(function (g) { if (g.kind === "ownership") place(g, firstOf("ownership")); });
    var rest = list.filter(function (a) { return !placed[a.name]; });
    if (rest.length) out.push({title: R.label(R.group("ai")) || "AI", agents: rest});
    return out;
  }

  function row(a) {
    var li = make("li", "place-row"), n = isMine(a) ? unreadOf(a.name) : {unread: 0, important: 0};
    var link = make("a", "place" + (n.unread ? " unread" : ""));
    link.href = hrefOf(a.name, n.unread ? "chat" : defaultView(a));
    link.dataset.name = a.name;
    link.dataset.key = "agent:" + a.name;
    if (a.name === chosen) link.setAttribute("aria-current", "page");
    link.append(S.presence({kind: "agent", online: !!a.online}), S.avatar(a.name, 16, {kind: "agent", avatar: a.avatar}),
                make("span", "place-name", a.name));
    var model = A.modelTag(a.model);
    if (model) link.appendChild(model);
    var state = S.workMark(a, "work-word");
    if (state) link.appendChild(state);
    if (S.counts) S.counts(link, n.unread, n.important, false);
    li.appendChild(link);
    return li;
  }

  function drawList() {
    A.keepFocus(el.list, function () {
      el.list.textContent = "";
      if (S.members && !agents().length) {
        el.list.appendChild(make("p", "agent-none", t("agp.none")));
        return;
      }
      sections().forEach(function (s) {
        var sec = make("section", "side-sec"), head = make("div", "side-head"), ul = make("ul", "side-list");
        head.appendChild(make("h2", "", s.title));
        s.agents.forEach(function (a) { ul.appendChild(row(a)); });
        sec.append(head, ul);
        el.list.appendChild(sec);
      });
    });
  }

  el.list.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest("a[data-name]");
    if (!a || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
    ev.preventDefault();
    var who = find(a.dataset.name);
    choose(a.dataset.name, who && isMine(who) && unreadOf(who.name).unread ? "chat" : defaultView(who), true);
    if (A.rail) A.rail.closeDrawer(false);
  });

  // ------------------------------------------------------------------ the chosen agent, top right

  // The quota of an agent of the reader's own, as its computer's program last reported it (1x).
  function quotaText(a, full) {
    if (!isMine(a) || !mine) return "";
    var me = (mine.agents || []).filter(function (x) { return x.name === a.name; })[0];
    var cred = me && (mine.credentials || []).filter(function (c) { return c.id === me.credential; })[0];
    var q = cred && (cred.quotas || []).filter(function (x) { return x.product === a.kind; })[0];
    return q && (q.windows || []).length ? A.quotaText(q, full) : "";
  }
  function facts(a) {
    var kind = A.MSG["kind." + a.kind] ? t("kind." + a.kind) : a.kind;
    return [kind, ownerWord(a)].join(" · ");
  }

  function drawHead() {
    var a = find(chosen);
    el.head.textContent = "";
    el.acts.textContent = "";
    if (!a) return;
    el.head.appendChild(S.avatar(a.name, 24, {kind: "agent", avatar: a.avatar}));
    el.head.appendChild(S.presence({kind: "agent", online: !!a.online}));
    el.head.appendChild(make("span", "agent-name", a.name));
    var model = A.modelTag(a.model);
    if (model) el.head.appendChild(model);
    var state = S.workMark(a, "agent-state");
    if (state) el.head.appendChild(state);
    var quota = quotaText(a, false);
    if (quota) {
      var span = make("span", "agent-quota", quota);
      span.title = quotaText(a, true);
      span.setAttribute("aria-label", t("quota.label", {text: quotaText(a, true)}));
      el.head.appendChild(span);
    }
    el.head.appendChild(make("span", "agent-facts", facts(a)));
    if (menuItems(a).length) {
      var more = A.button("icon-btn agent-more");
      more.appendChild(A.glyph("dots"));
      more.setAttribute("aria-label", t("agp.acts"));
      more.title = t("agp.acts");
      more.setAttribute("aria-haspopup", "menu");
      more.setAttribute("aria-expanded", "false");
      more.dataset.key = "agent-more";
      more.addEventListener("click", function () {
        var who = find(chosen);
        if (who) A.menu({label: t("agp.acts"), anchor: more}, menuItems(who, more), more);
      });
      el.acts.appendChild(more);
    }
  }

  // Whether the last reading of the members succeeded (frame.js tells after each).
  var membersRead = true;
  if (S.onMembersRead) S.onMembersRead(function (ok) { membersRead = ok; });

  // The one menu: 群組 (check boxes), 頭像 (its own person), then 移出專案 (floats, the name typed).
  function menuItems(a, opener) {
    var R = rules(), items = [];
    if (!R) return items;
    var boxes = P.groupItems(R, a, true, function (r) {
      if (r && !r.ok) said(A.refusal("mem.regroup", r.data));
      // The act went through, but the members could not be read again: the page would show what was there before.
      S.loadMembers().then(function () { if (r && r.ok && !membersRead) said(t("people.failed")); });
    });
    if (boxes.length) items.push({label: t("people.groups"), items: boxes});
    if (isMine(a)) {
      var url = API + "agents/" + encodeURIComponent(a.name) + "/avatar";
      var faces = [{label: t("agp.avatar_pick", {name: a.name}), run: async function () {
        var r = await S.pickAvatar(url);
        if (r.cancelled) return;
        said(r.ok ? t("agp.avatar_saved", {name: a.name}) : A.refusal("me.avatar", r.data));
      }}];
      if (a.avatar) {
        faces.push({label: t("agp.avatar_remove", {name: a.name}), run: async function () {
          var r = await S.removeAvatar(url);
          said(r.ok ? t("agp.avatar_removed", {name: a.name}) : A.refusal("me.avatar", r.data));
        }});
      }
      items.push({label: t("agp.avatar"), items: faces});
    }
    if (R.mayRemove(a, true)) {
      items.push({separator: true}, {label: t("people.remove"), run: function () {
        P.remove(a, true, opener, null, function () { S.loadMembers(); });
      }});
    }
    return items;
  }

  // The outcome or refusal of an act, beside the "..." control for a moment.
  function said(text) {
    el.said.textContent = text;
    clearTimeout(said.timer);
    said.timer = setTimeout(function () { if (el.said.textContent === text) el.said.textContent = ""; }, 4000);
  }

  async function loadMine() {
    var r = await A.request(API + "my");
    if (!r.ok) return;
    var raw = JSON.stringify(r.data);
    if (raw === mineRaw) return;
    mineRaw = raw;
    mine = r.data;
    A.keepFocus(el.head.parentNode, drawHead);
    drawStatus();
  }

  // ------------------------------------------------------------------ the head: the offline line and the status

  function drawOffline() {
    var a = find(chosen);
    el.offline.hidden = !a || !!a.online;
    if (el.offline.hidden) return;
    el.offline.textContent = "";
    var parts = t("my.offline").split("{why}"), why = a.offline_because;
    var reason = why && A.MSG["my.offline." + why] ? t("my.offline." + why) : "";
    if (!reason) { el.offline.appendChild(make("span", "off-word", parts[0].replace(/[:：]\s*$/, ""))); return; }
    el.offline.append(make("span", "off-word", parts[0]), make("span", "off-why", reason));
    if (why && A.MSG["offline." + why]) el.offline.title = t("offline." + why);
  }

  // The status, a disclosure: its title line is the button, "更新於…" and the overdue mark always under it; opened,
  // the facts of the bar (below 900 px), the body, and how often its person asks for an update.
  function statusOpen() {
    var kept = A.store.get(STATUS_KEY, null);
    return kept === "open" ? true : kept === "closed" ? false : !narrow.matches;
  }
  function writingStatus() {
    var x = document.activeElement;
    return !!(x && el.status.contains(x) && x.tagName === "INPUT");
  }
  function drawStatus() {
    var a = find(chosen), st = a && St ? St.agent(a.name) : null;
    el.status.hidden = !st;
    if (!st || writingStatus()) return;
    A.keepFocus(el.status, function () {
      el.status.textContent = "";
      var open = statusOpen(), quota = quotaText(a, false);
      var behind = !!st.body || isMine(a) || !!st.update_every_h || narrow.matches;
      var title = make(behind ? "button" : "div", "status-line" + (st.title ? "" : " dim"));
      title.appendChild(make("span", "status-title", st.title || t("db.no_status")));
      if (behind) {
        title.type = "button";
        title.setAttribute("aria-expanded", String(open));
        title.setAttribute("aria-controls", "agent-status-more");
        title.dataset.key = "status-toggle";
        var chev = A.glyph("chevron");
        chev.classList.add("status-chev");
        title.appendChild(chev);
        title.addEventListener("click", function () {
          A.store.set(STATUS_KEY, statusOpen() ? "closed" : "open");
          drawStatus();
        });
      }
      el.status.classList.toggle("open", behind && open);
      el.status.appendChild(title);
      var upd = St.updated(st);
      if (upd) {
        var track = make("div", "agent-status-track");
        track.appendChild(upd);
        el.status.appendChild(track);
      }
      if (!behind || !open) return;
      var more = make("div", "agent-status-more");
      more.id = "agent-status-more";
      if (narrow.matches) more.appendChild(make("p", "agent-status-facts", facts(a) + (quota ? " · " + quota : "")));
      if (st.body) more.appendChild(St.body(st.body, "agp:" + a.name));
      if (isMine(a)) more.appendChild(St.everyControl(st, function () { St.load(true); }));
      else if (st.update_every_h) more.appendChild(make("p", "agent-status-every", t("st.every", {n: st.update_every_h})));
      el.status.appendChild(more);
    });
  }

  // ------------------------------------------------------------------ the views

  // The tab line: 對話 and 動態 for my agent, 動態 alone (current, not a link) for anybody else's.
  function drawTabs() {
    var a = find(chosen), have = a ? viewsOf(a) : [];
    Array.prototype.forEach.call(el.views.querySelectorAll("[data-view]"), function (tab) {
      var v = tab.dataset.view, here = v === view;
      tab.hidden = have.indexOf(v) < 0;
      tab.setAttribute("aria-selected", String(here));
      if (here) tab.setAttribute("aria-current", "page"); else tab.removeAttribute("aria-current");
      if (have.length > 1) tab.href = hrefOf(chosen, v); else tab.removeAttribute("href");
      tab.setAttribute("aria-controls", v === "chat" ? "agent-conversation" : "agent-timeline");
    });
    drawTabCount();
  }
  // The 對話 tab carries the conversation's count only while the list is out of sight and 動態 is shown.
  function listHidden() {
    return narrow.matches || (document.documentElement.getAttribute("data-folded") || "").split(/\s+/).indexOf("agent") >= 0;
  }
  function drawTabCount() {
    var tab = el.views.querySelector('[data-view="chat"]'), box = tab && tab.querySelector(".tab-count");
    if (!box) return;
    var n = unreadOf(chosen), show = view === "activity" && listHidden() && !!n.unread && isMine(find(chosen));
    box.hidden = !show;
    box.textContent = "";
    if (show && S.counts) S.counts(box, n.unread, n.important, false);
  }
  el.views.addEventListener("click", function (ev) {
    var tab = ev.target.closest && ev.target.closest("[data-view]");
    if (!tab || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
    ev.preventDefault();
    if (!tab.getAttribute("href") || tab.dataset.view === view) return;
    A.store.set(VIEW_KEY, tab.dataset.view);
    choose(chosen, tab.dataset.view, true);
    tab.focus();
  });

  function showView(v) {
    var was = view;
    view = v;
    if (was === "chat" && v !== "chat" && A.chat) A.chat.hide();
    el.convo.hidden = v !== "chat";
    el.log.hidden = v !== "activity";
    if (v === "chat" && was !== "chat" && A.chat) A.chat.reveal();
    drawTabs();
  }

  // ------------------------------------------------------------------ choosing

  function remember() {
    if (A.rail && A.rail.agentKey) A.store.set(A.rail.agentKey, window.location.pathname + window.location.search);
  }

  // Show `name` in the view `v` (one it has), at the message `at` of 對話 when given; the address follows.
  function choose(name, v, push, at) {
    var a = find(name);
    if (!a) return;
    if (viewsOf(a).indexOf(v) < 0) v = defaultView(a);
    if (at) v = "chat";
    var url = hrefOf(name, v);
    if (url !== window.location.pathname + window.location.search) {
      window.history[push ? "pushState" : "replaceState"](null, "", url);
    }
    remember();
    var fresh = name !== chosen;
    chosen = name;
    if (fresh) {
      if (isMine(a) && A.chat) {
        A.chat.show(name, at);
      }
      startLog();
      el.other.hidden = isMine(a);
      if (!isMine(a)) el.other.textContent = t("dm.refused_agent", {owner: a.owner || "?", name: a.name});
    } else if (at && A.chat) {
      A.chat.show(name, at);
    }
    drawList();
    drawHead();
    drawOffline();
    drawStatus();
    showView(v);
  }

  // The agent and the view the address names; a view the reader does not have, an unknown value or an unknown name
  // is dropped (the address is replaced).
  function fromAddress() {
    var p = new URLSearchParams(window.location.search), name = p.get("name") || "", m = p.get("m");
    var a = find(name);
    if (!a) {
      var shown = [];
      sections().forEach(function (s) { shown = shown.concat(s.agents); });
      var withUnread = shown.filter(function (x) { return isMine(x) && unreadOf(x.name).unread; })[0];
      a = withUnread || shown.filter(isMine)[0] || shown[0] || null;
      if (!a) return;
      choose(a.name, defaultView(a), false);
      return;
    }
    var asked = p.get("view"), v = asked === "activity" || asked === "chat" ? asked : null;
    if (!v || viewsOf(a).indexOf(v) < 0) v = defaultView(a);
    var at = m && /^\d{1,18}$/.test(m) && isMine(a) ? Number(m) : null;
    choose(a.name, v, false, at);
  }
  window.addEventListener("popstate", function () { if (S.members) fromAddress(); });

  // ------------------------------------------------------------------ 動態: the log

  var log = {entries: [], more: false, loaded: false, loading: false, failed: false, gen: 0, news: 0};
  var openRows = new Set(), openRuns = new Set(), all = false;

  function keyOf(x) { return x.kind === "message" ? "m" + x.message.id : x.id; }
  function cursorOf(x) { return x.kind === "message" ? String(x.message.id) : x.id; }
  function whenOf(x) { return x.kind === "message" ? x.message.sent_at : x.at; }

  function ask(params) {
    params.limit = PAGE;
    if (filter === "concerns") params.only = "concerns";
    return A.request(API + "agents/" + encodeURIComponent(chosen) + "/timeline", params);
  }

  function startLog() {
    log = {entries: [], more: false, loaded: false, loading: false, failed: false, gen: log.gen + 1, news: 0};
    el.items.textContent = "";
    el.scroll.scrollTop = 0;
    drawNews();
    drawFoot();
    if (chosen) loadFirst();
  }

  async function loadFirst() {
    var mine = log.gen;
    log.loading = true;
    drawFoot();
    var r = await ask({});
    if (mine !== log.gen) return;
    log.loading = false;
    if (!r.ok) { log.failed = true; drawFoot(); return; }
    log.failed = false;
    log.entries = (r.data.items || []).slice().reverse();
    log.more = !!r.data.more;
    log.loaded = true;
    drawLog();
    fill();
  }

  async function loadOlder() {
    if (log.loading || !log.more || !log.entries.length || !chosen) return;
    var mine = log.gen;
    log.loading = true;
    drawFoot();
    var r = await ask({before: cursorOf(log.entries[log.entries.length - 1])});
    log.loading = false;
    if (mine !== log.gen) return;
    if (!r.ok) { drawFoot(); return; }
    var seen = new Set(log.entries.map(keyOf));
    log.entries = log.entries.concat((r.data.items || []).slice().reverse().filter(function (x) { return !seen.has(keyOf(x)); }));
    log.more = !!r.data.more;
    drawLog();
    fill();
  }
  // While the log does not fill its box there is nothing to scroll: load further back at once.
  function fill() {
    requestAnimationFrame(function () {
      if (!el.log.hidden && log.more && el.scroll.scrollHeight <= el.scroll.clientHeight + 120) loadOlder();
    });
  }
  el.scroll.addEventListener("scroll", function () {
    if (el.scroll.scrollHeight - el.scroll.scrollTop - el.scroll.clientHeight < 120) loadOlder();
    if (el.scroll.scrollTop < 8 && log.news) { log.news = 0; drawNews(); }
  }, {passive: true});
  el.older.addEventListener("click", loadOlder);

  // New entries at the top; an entry that changed (handed over, deleted, edited) drawn again in place. Scrolled down,
  // what the reader looks at does not move, and the pill says new entries are above.
  var polling = false;
  async function news() {
    if (!chosen || polling || log.loading) return;
    if (!log.loaded) { if (log.failed) loadFirst(); return; }
    var mine = log.gen;
    polling = true;
    try {
      var r = await ask({});
      if (mine !== log.gen || !r.ok) return;
      var got = (r.data.items || []).slice().reverse();
      if (!got.length) return;
      var index = new Map(log.entries.map(function (x, i) { return [keyOf(x), i]; }));
      var changed = false;
      got.forEach(function (x) {
        var i = index.get(keyOf(x));
        if (i !== undefined && JSON.stringify(log.entries[i]) !== JSON.stringify(x)) { log.entries[i] = x; changed = true; }
      });
      var newest = log.entries.length ? keyOf(log.entries[0]) : null;
      var at = got.findIndex(function (x) { return keyOf(x) === newest; });
      if (newest !== null && at < 0) { startLog(); return; }          // more arrived than one page: read it all again
      var add = newest === null ? got : got.slice(0, at);
      if (!add.length && !changed) return;
      var before = el.scroll.scrollHeight, top = el.scroll.scrollTop;
      log.entries = add.concat(log.entries);
      if (newest === null) log.more = !!r.data.more;
      drawLog();
      if (top > 8 && add.length) {                                     // keep what is looked at where it was
        el.scroll.scrollTop = top + el.scroll.scrollHeight - before;
        log.news += add.length;
        drawNews();
      }
    } finally {
      polling = false;
    }
  }
  function drawNews() {
    el.news.hidden = !log.news;
    if (!log.news) return;
    el.news.textContent = t("agp.news");
    el.news.setAttribute("aria-label", t("agp.news_label", {n: log.news}));
    el.news.title = el.news.getAttribute("aria-label");
  }
  el.news.addEventListener("click", function () {
    el.scroll.scrollTop = 0;
    log.news = 0;
    drawNews();
  });

  function drawFoot() {
    var text = "";
    if (log.failed) text = t("agp.failed");
    else if (log.loading) text = log.loaded ? t("agp.older") : "";
    else if (log.loaded && !log.entries.length) text = t("agp.empty");
    else if (log.loaded && !log.more) text = t("agp.start");
    el.foot.textContent = text;
    el.foot.hidden = !text;
    el.older.hidden = !log.loaded || !log.more || log.loading;
  }

  // ---- what an entry says

  function clock(iso) {
    var d = new Date(iso);
    return isNaN(d.getTime()) ? "" : d.toLocaleTimeString(LANG, {hour: "2-digit", minute: "2-digit", hour12: false});
  }
  function dayKey(iso) { var d = new Date(iso); return isNaN(d.getTime()) ? "" : d.toDateString(); }
  function dayTitle(iso) {
    var d = new Date(iso), now = new Date();
    if (isNaN(d.getTime())) return "";
    var opts = {month: "long", day: "numeric", weekday: "short"};
    if (d.getFullYear() !== now.getFullYear()) opts.year = "numeric";
    var text = d.toLocaleDateString(LANG, opts), yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
    if (d.toDateString() === now.toDateString()) return t("agp.today") + " · " + text;
    if (d.toDateString() === yesterday.toDateString()) return t("agp.yesterday") + " · " + text;
    return text;
  }
  function excerpt(text) { return String(text || "").replace(/\s+/g, " ").trim(); }

  // A message entry: {dir, place (with its #) or name (the other member of a private conversation, from the agent's
  // side), from, waiting for the agent, important for it}.
  function shapeOf(x) {
    var m = x.message, sent = x.dir === "sent", priv = !!m["private"];
    var name = priv ? (m["with"] || ME) : "", place = priv ? "" : m["in"];
    var waits = !sent && (m.waiting || []).indexOf(chosen) >= 0;
    return {m: m, sent: sent, priv: priv, name: name, place: place, waits: waits,
            important: !sent && x.message.agent_level === "important",
            group: (sent ? "s" : "g") + (priv ? "p:" + name : "c:" + place)};
  }
  function sentence(s) {
    var m = s.m;
    if (s.sent) return s.priv ? t("act.sent.private", {name: s.name}) : t(m.reply_to ? "act.sent.reply" : "act.sent.channel", {place: s.place});
    if (s.waits) return s.priv ? t("act.wait.private", {name: s.name}) : t("act.wait.channel", {from: m.from, place: s.place});
    if (s.priv) return t("act.got.private", {name: s.name});
    if (m.from_kind === "system") return t("act.got.system", {place: s.place});
    return t("act.got.channel", {from: m.from, place: s.place});
  }
  function runSentence(s, n) {
    if (s.sent) return s.priv ? t("act.run.sent.private", {name: s.name, n: n}) : t("act.run.sent.channel", {place: s.place, n: n});
    return s.priv ? t("act.run.got.private", {name: s.name, n: n}) : t("act.run.got.channel", {place: s.place, n: n});
  }
  function mark(kind) {
    var span = make("span", "act-mark");
    span.setAttribute("aria-hidden", "true");
    if (kind === "online" || kind === "offline") span.appendChild(S.presence({kind: "agent", online: kind === "online"}));
    else span.appendChild(A.glyph(kind));
    return span;
  }
  function tag(text, title) {
    var s = make("span", "tag", text);
    if (title) s.title = title;
    return s;
  }

  // ---- a row

  var seq = 0;
  // `parts`: {key, when, mark, ink, sentence (text or nodes), tags, excerpt, deleted, body (a function, or null)}.
  function rowOf(parts) {
    var li = make("li", "act " + (parts.ink ? "ink" : "dim") + (parts.wrap ? " wrap" : "")), open = isOpen(parts.key);
    li.dataset.key = parts.key;
    var line = make(parts.body ? "button" : "div", "act-line");
    var time = make("time", "act-time", clock(parts.when));
    time.dateTime = parts.when;
    time.title = new Date(parts.when).toLocaleString(LANG);
    var text = make("span", "act-text"), what = make("span", "act-sentence");
    what.append.apply(what, [].concat(parts.sentence));
    text.appendChild(what);
    (parts.tags || []).forEach(function (x) { text.appendChild(x); });
    if (parts.excerpt !== undefined) {
      text.appendChild(make("span", "act-excerpt" + (parts.deleted ? " deleted" : ""), parts.excerpt));
    }
    line.append(time, parts.mark, text);
    li.appendChild(line);
    if (parts.body) {
      var id = "act-body-" + (++seq);
      line.type = "button";
      line.dataset.key = "act:" + parts.key;
      line.setAttribute("aria-expanded", String(open));
      line.setAttribute("aria-controls", id);
      var chev = A.glyph("chevron");
      chev.classList.add("act-chev");
      line.appendChild(chev);
      line.addEventListener("click", function () { toggle(li, parts.key); });
      if (open) {
        var body = parts.body();
        body.id = id;
        li.appendChild(body);
        li.classList.add("open");
      }
    }
    return li;
  }

  // Opening and closing keep the row's top where it was.
  function toggle(li, key) {
    var before = li.getBoundingClientRect().top;
    if (openRows.has(key) || (all && !openRows.has("!" + key))) {
      openRows.delete(key);
      if (all) openRows.add("!" + key);
    } else {
      openRows.add(key);
      openRows.delete("!" + key);
    }
    drawLog();
    var again = el.items.querySelector('li[data-key="' + key.replace(/["\\]/g, "\\$&") + '"]');
    if (again) {
      el.scroll.scrollTop += again.getBoundingClientRect().top - before;
      var b = again.querySelector(".act-line");
      if (b) b.focus({preventScroll: true});
    }
  }
  function isOpen(key) { return (all && !openRows.has("!" + key)) || openRows.has(key); }

  // The whole message: the reply line, the text rendered as a message is, 已編輯, the waiting line, and a foot with the
  // time, the model it was sent with and the link to where it is.
  function messageBody(s) {
    var m = s.m, body = make("div", "act-body");
    if (m.reply_to) {
      var orig = log.entries.filter(function (y) { return y.kind === "message" && y.message.id === m.reply_to; })[0];
      body.appendChild(make("p", "act-reply", orig
        ? t("msg.reply_line", {name: orig.message.from_kind === "system" ? t("msg.system") : orig.message.from,
                               text: orig.message.deleted ? t("msg.deleted") : excerpt(orig.message.text).slice(0, 140)})
        : t("msg.reply_to_link", {id: m.reply_to})));
    }
    var box = A.renderText(m.text, {mentions: m.mentions});
    if (A.paths) A.paths.scan(box);
    body.appendChild(box);
    if (m.edited_at) body.appendChild(A.editedMark(m.edited_at));
    if (m.waiting && m.waiting.length) {
      body.appendChild(make("p", "msg-waiting", t("msg.waiting", {names: m.waiting.join(t("msg.names_sep"))})));
    }
    var foot = make("p", "act-foot");
    foot.appendChild(document.createTextNode(new Date(m.sent_at).toLocaleString(LANG)));
    var model = s.sent ? A.modelTag(m.model) : null;
    if (model) foot.append(" · ", model);
    foot.append(" · ", whereLink(s));
    body.appendChild(foot);
    return body;
  }
  // Where the message is: a channel's in chat; the reader's own conversation with the agent in 對話 (in place); a
  // conversation between two agents of the reader's has no place the reader opens (1v): the other agent's 動態.
  function whereLink(s) {
    var m = s.m, base = "/" + encodeURIComponent(SLUG), a;
    if (!s.priv) {
      a = make("a", "act-open", t("act.open.channel", {place: m["in"]}));
      a.href = base + "?m=" + encodeURIComponent(m.id) + "#" + encodeURIComponent(m["in"]);
      return a;
    }
    if (!m["with"]) {
      a = make("a", "act-open", t("act.open.chat"));
      a.href = hrefOf(chosen, "chat") + "&m=" + encodeURIComponent(m.id);
      a.addEventListener("click", function (ev) {
        if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
        ev.preventDefault();
        choose(chosen, "chat", true, m.id);
      });
      return a;
    }
    a = make("a", "act-open", t("act.open.agent", {name: m["with"]}));
    a.href = HOME + "?name=" + encodeURIComponent(m["with"]) + "&view=activity";
    a.addEventListener("click", function (ev) {
      if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
      ev.preventDefault();
      choose(m["with"], "activity", true);
    });
    return a;
  }

  function messageRow(x) {
    var s = shapeOf(x), m = s.m, tags = [];
    if (s.important) tags.push(tag(t("msg.important"), t("act.important_hint")));
    if (m.scheduled) tags.push(tag(t("msg.scheduled")));
    if (s.sent && m.waiting && m.waiting.length) {
      tags.push(make("span", "act-undelivered", t("act.undelivered", {names: m.waiting.join(t("msg.names_sep"))})));
    }
    return rowOf({key: keyOf(x), when: m.sent_at, mark: mark(s.sent ? "sent" : "got"),
                  ink: s.sent || s.important || s.waits, sentence: sentence(s), tags: tags,
                  excerpt: m.deleted ? t("msg.deleted") : excerpt(m.text), deleted: !!m.deleted,
                  body: m.deleted ? null : function () { return messageBody(s); }});
  }
  function stateRow(x) {
    if (x.state === "online") {
      return rowOf({key: keyOf(x), when: x.at, mark: mark("online"), ink: false, sentence: t("agp.state.online")});
    }
    if (x.state === "offline") {
      var reason = x.reason && A.MSG["my.offline." + x.reason] ? t("my.offline." + x.reason) : "";
      var words = [make("span", "", t("agp.state.offline"))];
      if (reason) words.push(make("span", "act-why", " · " + reason));
      var full = x.reason && A.MSG["offline." + x.reason] ? t("offline." + x.reason) : "";
      return rowOf({key: keyOf(x), when: x.at, mark: mark("offline"), ink: true, sentence: words,
                    body: full ? function () { return make("div", "act-body", full); } : null});
    }
    if (x.state === "status") {
      return rowOf({key: keyOf(x), when: x.at, mark: mark("lines"), ink: true, wrap: true,
                    sentence: x.title ? t("agp.state.status", {title: x.title}) : t("agp.state.status_cleared")});
    }
    return rowOf({key: keyOf(x), when: x.at, mark: mark("lines"), ink: false, sentence: x.state});
  }

  // A run: three or more message entries next to each other in one day with the same sentence, none important for
  // the agent and none waiting. One row (the newest time, the count, the span of times), opening to its entries.
  function runRow(group) {
    var s = shapeOf(group[0]), key = "run:" + keyOf(group[group.length - 1]);
    var first = group[group.length - 1].message.sent_at, last = group[0].message.sent_at;
    var li = rowOf({key: key, when: last, mark: mark(s.sent ? "sent" : "got"), ink: s.sent,
                    sentence: [runSentence(s, group.length), make("span", "act-span", " · " + clock(first) + "–" + clock(last))],
                    body: function () {
                      var ul = make("ul", "act-run");
                      group.forEach(function (x) { ul.appendChild(messageRow(x)); });
                      return ul;
                    }});
    li.classList.add("run");
    return li;
  }

  function drawLog() {
    A.keepFocus(el.items, function () {
      el.items.textContent = "";
      var day = "", i = 0, list = log.entries, prev = null;
      while (i < list.length) {
        var x = list[i], d = dayKey(whenOf(x));
        if (d !== day) {
          day = d;
          el.items.appendChild(make("li", "act-day", dayTitle(whenOf(x))));
          prev = null;
        }
        var row = null;
        if (x.kind === "message") {
          var s = shapeOf(x), j = i;
          if (!s.important && !s.waits) {
            while (j + 1 < list.length && list[j + 1].kind === "message" && dayKey(whenOf(list[j + 1])) === day) {
              var n = shapeOf(list[j + 1]);
              if (n.group !== s.group || n.important || n.waits) break;
              j += 1;
            }
          }
          if (j - i + 1 >= RUN_MIN) {
            row = runRow(list.slice(i, j + 1));
            i = j + 1;
          } else {
            row = messageRow(x);
            i += 1;
          }
        } else {
          row = stateRow(x);
          i += 1;
        }
        if (!prev) row.classList.add("first");
        el.items.appendChild(row);
        prev = row;
        var next = list[i];
        if (!next || dayKey(whenOf(next)) !== day) row.classList.add("last");
      }
    });
    drawFoot();
  }

  // ---- the view's own line: the filter (remembered) and "expand all" (for this visit)

  function drawFilter() {
    Array.prototype.forEach.call(el.filter.querySelectorAll("[data-filter]"), function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.filter === filter));
    });
  }
  drawFilter();
  el.filter.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("[data-filter]");
    if (!b || b.dataset.filter === filter) return;
    filter = b.dataset.filter === "all" ? "all" : "concerns";
    A.store.set(FILTER_KEY, filter);
    drawFilter();
    if (chosen) startLog();
  });
  el.expand.addEventListener("click", function () {
    all = !all;
    openRows.clear();
    el.expand.setAttribute("aria-pressed", String(all));
    el.expand.textContent = t(all ? "agp.collapse_all" : "agp.expand_all");
    drawLog();
  });

  // ------------------------------------------------------------------ keeping it current

  S.onMembers(function () {
    if (!chosen || !find(chosen)) { fromAddress(); return; }
    drawList();
    drawHead();
    drawOffline();
    drawStatus();
    drawTabs();
  });
  S.onChange(function () {
    drawList();
    drawTabCount();
  });
  if (St) {
    St.onChange(function () { drawStatus(); });
    St.follow();
  }
  narrow.addEventListener("change", function () { drawStatus(); drawTabCount(); });
  new MutationObserver(drawTabCount).observe(document.documentElement, {attributes: true, attributeFilter: ["data-folded"]});
  S.loadMembers();
  setInterval(news, EVERY_MS);
  loadMine();
  setInterval(loadMine, 30000);
})();
