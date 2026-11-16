// The agent page (#agent-timeline; m1f6_contract.md section 10), from the members (frame.js) and one agent's timeline
// (/api/agents/{name}/timeline). All texts come from the page's message catalogue.
// - The second column (#agent-list): every agent of the project, under a switch at its top (#agent-sort, remembered):
//   by group (sections by the groups in their order; an agent under the first group it is in that is not a default
//   group, else under AI) or by owner (sections by person, mine first). A row: presence, name, model, busy.
// - The chosen agent is the address's query (?name=), changed in place with history.pushState; without one, the
//   first of my agents, else the first listed. The rail's agent button returns to it. Top right (#agent-head): its
//   presence, name, model, kind and owner; at the right its acts where the reader may (its groups as check boxes, and
//   removing it from the project, floating), and "invite agent".
// - The page: its timeline, as a conversation: every message it sent or was handed that the reader may read, with
//   where it was and whether it was sent or received, and its changes of state (online, offline with the reason, a
//   task given, taken, released or removed) as quiet lines between them; newest at the bottom, older ones loaded on
//   scrolling up, new ones asked for every few seconds (the reader's place is kept: new things arrive at the end).
// - Its own person talks to it here: the composer (#tl-composer) sends a private message to it. Anybody else sees the
//   timeline with one quiet line instead (only its person and that person's agents write to an agent privately).
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("agent-timeline");
  if (!A || !root || !A.side || !A.renderText) return;
  var t = A.t, make = A.make, S = A.side, P = A.people;
  var SLUG = root.dataset.slug, ME = root.dataset.me, API = "/" + encodeURIComponent(SLUG) + "/api/";
  var HOME = "/" + encodeURIComponent(SLUG) + "/agent";
  var PAGE = 50, EVERY_MS = 4000, LANG = document.documentElement.lang || undefined;
  var SORT_KEY = "asterism-agent-sort:" + SLUG;

  var el = {
    list: document.getElementById("agent-list"), sort: document.getElementById("agent-sort"),
    head: document.getElementById("agent-head"), acts: document.getElementById("agent-acts"),
    scroll: document.getElementById("tl-scroller"), items: document.getElementById("tl-list"),
    older: document.getElementById("tl-older"), form: document.getElementById("tl-composer"),
    text: document.getElementById("tl-text"), out: document.getElementById("tl-out")
  };
  var owner = make("p", "tl-owner");
  owner.hidden = true;
  root.appendChild(owner);

  var sort = A.store.get(SORT_KEY, "group") === "owner" ? "owner" : "group";
  var chosen = "";                 // the agent shown
  var gen = 0;                     // a new choice makes the answers for the earlier one stale
  var entries = [];                // the timeline's items shown, oldest first
  var nodes = new Map();           // an item's key -> its row
  var more = false, loading = false, polling = false, loaded = false;

  function agents() { return S.members ? S.members.agents || [] : []; }
  function find(name) { return agents().filter(function (a) { return a.name === name; })[0] || null; }
  function rules() { return S.members && P ? P.rules(S.members) : null; }
  function href(name) { return HOME + "?name=" + encodeURIComponent(name); }
  function ownerWord(a) { return a.owner === ME ? t("nav.my_agent") : t("mem.agent_of", {owner: a.owner || "?"}); }

  // ------------------------------------------------------------------ the list

  // [{title, agents}] in the order shown.
  function sections() {
    var v = S.members, R = rules();
    if (!v || !R) return [];
    var list = agents(), out = [];
    if (sort === "owner") {
      var owners = [];
      list.forEach(function (a) { if (owners.indexOf(a.owner) < 0) owners.push(a.owner); });
      var people = (v.people || []).map(function (p) { return p.name; });
      owners.sort(function (x, y) {
        if (x === ME || y === ME) return x === ME ? -1 : 1;
        var i = people.indexOf(x), j = people.indexOf(y);
        return (i < 0 ? 1e9 : i) - (j < 0 ? 1e9 : j);
      });
      owners.forEach(function (o) {
        out.push({title: o === ME ? t("ag.mine") : t("group.ownership", {owner: o || "?"}),
                  agents: list.filter(function (a) { return a.owner === o; })});
      });
      return out;
    }
    var placed = {};
    v.groups.forEach(function (g) {
      if (R.isDefault(g)) return;
      var here = list.filter(function (a) {
        if (placed[a.name]) return false;
        var first = R.plainOf(a)[0];
        return !!first && first.name === g.name;
      });
      here.forEach(function (a) { placed[a.name] = true; });
      if (here.length) out.push({title: R.label(g), agents: here});
    });
    var rest = list.filter(function (a) { return !placed[a.name]; });
    if (rest.length) out.push({title: R.label(R.group("ai")) || "AI", agents: rest});
    return out;
  }

  function row(a) {
    var li = make("li", "place-row"), link = make("a", "place");
    link.href = href(a.name);
    link.dataset.name = a.name;
    link.dataset.key = "agent:" + a.name;
    if (a.name === chosen) link.setAttribute("aria-current", "page");
    link.append(S.presence({kind: "agent", online: !!a.online}), make("span", "place-name", a.name));
    var model = A.modelTag(a.model);
    if (model) link.appendChild(model);
    if (a.busy) link.appendChild(make("span", "busy", t("nav.busy")));
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
    Array.prototype.forEach.call(el.sort.querySelectorAll("[data-sort]"), function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.sort === sort));
    });
  }

  el.sort.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("[data-sort]");
    if (!b) return;
    sort = b.dataset.sort === "owner" ? "owner" : "group";
    A.store.set(SORT_KEY, sort);
    drawList();
  });
  el.list.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest("a[data-name]");
    if (!a || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
    ev.preventDefault();
    choose(a.dataset.name, true);
  });

  // ------------------------------------------------------------------ the chosen agent, top right

  function drawHead() {
    var a = find(chosen), R = rules();
    el.head.textContent = "";
    el.acts.textContent = "";
    if (!a) return;
    el.head.appendChild(S.presence({kind: "agent", online: !!a.online}));
    el.head.appendChild(make("span", "agent-name", a.name));
    var model = A.modelTag(a.model);
    if (model) el.head.appendChild(model);
    var kind = A.MSG["kind." + a.kind] ? t("kind." + a.kind) : a.kind;
    el.head.appendChild(make("span", "agent-facts", [kind, ownerWord(a), a.busy ? t("nav.busy") : ""]
      .filter(Boolean).join(" · ")));
    if (!R) return;
    var boxes = P.groupItems(R, a, true, function () {});
    if (boxes.length) {
      var groups = A.button("btn", t("people.groups"));
      groups.dataset.key = "groups";
      groups.setAttribute("aria-haspopup", "menu");
      groups.setAttribute("aria-expanded", "false");
      groups.addEventListener("click", function () {
        var now = rules(), who = find(chosen);
        if (!now || !who) return;
        A.menu({label: t("people.groups"), anchor: groups}, P.groupItems(now, who, true, function (r) {
          if (r && !r.ok) refused(r.data);
          S.loadMembers();
        }), groups);
      });
      el.acts.appendChild(groups);
    }
    if (R.mayRemove(a, true)) {
      var remove = A.button("btn", t("people.remove"));
      remove.dataset.key = "remove";
      remove.addEventListener("click", function () {
        P.remove(a, true, remove, null, function () { S.loadMembers(); });
      });
      el.acts.appendChild(remove);
    }
  }

  // A refusal of an act on the agent, said under the timeline (where the composer's outcome or the quiet line is).
  function refused(data) {
    var text = A.refusal("ag.refused", data);
    if (el.form.hidden) { owner.hidden = false; owner.textContent = text; } else el.out.textContent = text;
  }

  // Only its own person writes to it privately (the server's rule): the composer for them, one quiet line otherwise.
  function drawComposer() {
    var a = find(chosen), mine = !!a && a.owner === ME;
    el.form.hidden = !mine;
    owner.hidden = !a || mine;
    if (a && !mine) owner.textContent = t("agp.only_owner", {owner: a.owner || "?"});
    if (a) el.text.placeholder = t("agp.input_hint", {name: a.name});
  }

  // ------------------------------------------------------------------ the timeline

  function keyOf(x) { return x.kind === "message" ? "m" + x.message.id : x.id; }
  function cursorOf(x) { return x.kind === "message" ? String(x.message.id) : x.id; }
  function whenOf(x) { return x.kind === "message" ? x.message.sent_at : x.at; }

  function clock(iso) {
    var d = new Date(iso);
    return isNaN(d.getTime()) ? "" : d.toLocaleTimeString(LANG, {hour: "2-digit", minute: "2-digit", hour12: false});
  }
  function dayOf(iso) {
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    var opts = {month: "long", day: "numeric", weekday: "short"};
    if (d.getFullYear() !== new Date().getFullYear()) opts.year = "numeric";
    return d.toLocaleDateString(LANG, opts);
  }
  function stamp(iso) {
    var when = make("time", "", clock(iso));
    when.dateTime = iso;
    when.title = new Date(iso).toLocaleString(LANG);
    return when;
  }

  // Where a message was: a channel, or the private conversation with the reader; a link to it there.
  function placeLink(m) {
    var a = make("a", "tl-place", m["private"] ? t("agp.private") : m["in"]);
    var base = "/" + encodeURIComponent(SLUG), at = "?m=" + encodeURIComponent(m.id);
    a.href = m["private"] ? base + "/dm/" + encodeURIComponent(m["in"]) + at : base + at + "#" + encodeURIComponent(m["in"]);
    return a;
  }

  function messageRow(x) {
    var m = x.message;
    var li = make("li", "msg head" + (m.from_kind === "system" ? " system" : ""));
    var gutter = make("div", "gutter"), body = make("div", "body"), meta = make("div", "meta");
    gutter.appendChild(stamp(m.sent_at));
    meta.appendChild(make("span", "from", m.from_kind === "system" ? t("msg.system") : m.from));
    if (m.from_kind === "agent") {
      var model = A.modelTag(m.model);
      if (model) meta.appendChild(model);
    }
    meta.append(placeLink(m), make("span", "tl-dir", t(x.dir === "sent" ? "agp.sent" : "agp.received")));
    body.appendChild(meta);
    var box = A.renderText(m.text);
    if (A.paths) A.paths.scan(box);
    body.appendChild(box);
    li.append(gutter, body);
    return li;
  }

  function stateText(x) {
    if (x.state === "online" || x.state === "offline") return t("agp.state." + x.state);
    var self = x.by === chosen, key = "agp.state." + x.state + (self && A.MSG["agp.state." + x.state + "_self"] ? "_self" : "");
    if (!A.MSG[key]) return x.state;
    return t(key, {task: x.task, by: x.by || t("agp.someone")});
  }

  function stateRow(x) {
    var li = make("li", "tl-state");
    li.append(stamp(x.at), make("span", "", stateText(x)));
    if (x.state === "offline" && x.reason && A.MSG["offline." + x.reason]) {
      li.appendChild(make("div", "tl-why", t("offline." + x.reason)));
    }
    return li;
  }

  function nodeOf(x) {
    var key = keyOf(x);
    if (!nodes.has(key)) nodes.set(key, x.kind === "message" ? messageRow(x) : stateRow(x));
    return nodes.get(key);
  }

  // The rows in order, with a line for each new day; the rows themselves are kept, so this costs little.
  function draw() {
    var frag = document.createDocumentFragment(), day = "";
    if (loaded && !more) frag.appendChild(make("li", "day", entries.length ? t("agp.start") : t("agp.empty")));
    entries.forEach(function (x) {
      var d = dayOf(whenOf(x));
      if (d && d !== day) { frag.appendChild(make("li", "day", d)); day = d; }
      frag.appendChild(nodeOf(x));
    });
    el.items.textContent = "";
    el.items.appendChild(frag);
    el.older.hidden = !loading || !entries.length;
    if (!el.older.hidden) el.older.textContent = t("agp.older");
  }

  function atBottom() { return el.scroll.scrollHeight - el.scroll.scrollTop - el.scroll.clientHeight < 40; }
  function toBottom() { el.scroll.scrollTop = el.scroll.scrollHeight; }

  function ask(params) {
    params.limit = PAGE;
    return A.request(API + "agents/" + encodeURIComponent(chosen) + "/timeline", params);
  }

  async function loadFirst() {
    var mine = gen;
    loading = true;
    var r = await ask({});
    if (mine !== gen) return;
    loading = false;
    if (!r.ok) { loaded = true; entries = []; more = false; draw(); return; }
    entries = r.data.items || [];
    more = !!r.data.more;
    loaded = true;
    draw();
    toBottom();
    fill();
  }

  // Older items, kept in place: what the reader looks at does not move.
  async function loadOlder() {
    if (loading || !more || !entries.length || !chosen) return;
    var mine = gen;
    loading = true;
    draw();
    var r = await ask({before: cursorOf(entries[0])});
    loading = false;
    if (mine !== gen) return;
    if (!r.ok) { draw(); return; }
    var fromBottom = el.scroll.scrollHeight - el.scroll.scrollTop;
    var seen = new Set(entries.map(keyOf));
    entries = (r.data.items || []).filter(function (x) { return !seen.has(keyOf(x)); }).concat(entries);
    more = !!r.data.more;
    draw();
    el.scroll.scrollTop = el.scroll.scrollHeight - fromBottom;
    fill();
  }
  // While the list does not fill its box there is nothing to scroll: load further back at once.
  function fill() {
    requestAnimationFrame(function () {
      if (more && el.scroll.scrollHeight <= el.scroll.clientHeight + 40) loadOlder();
    });
  }
  el.scroll.addEventListener("scroll", function () { if (el.scroll.scrollTop < 120) loadOlder(); });

  // New items arrive at the end; the bottom stays the bottom when the reader was there.
  async function news() {
    if (!chosen || !loaded || polling || loading) return;
    var mine = gen;
    polling = true;
    try {
      var r = await ask({});
      if (mine !== gen || !r.ok) return;
      var got = r.data.items || [];
      if (!got.length) return;
      var last = entries.length ? keyOf(entries[entries.length - 1]) : null, at = -1;
      for (var i = got.length - 1; i >= 0; i--) { if (keyOf(got[i]) === last) { at = i; break; } }
      var add;
      if (last === null) add = got;
      else if (at >= 0) add = got.slice(at + 1);
      else { gen++; polling = false; start(chosen); return; }   // more arrived than one page: read it all again
      if (!add.length) return;
      var bottom = atBottom();
      if (last === null) more = !!r.data.more;
      entries = entries.concat(add);
      draw();
      if (bottom) toBottom();
    } finally {
      polling = false;
    }
  }

  // ------------------------------------------------------------------ choosing

  function start(name) {
    gen++;
    chosen = name;
    entries = [];
    nodes = new Map();
    more = false;
    loaded = false;
    loading = false;
    el.out.textContent = "";
    draw();
    drawList();
    drawHead();
    drawComposer();
    if (name) loadFirst();
  }

  // The agent to show: the address's, else the first of mine, else the first listed.
  function fallback() {
    var shown = [];
    sections().forEach(function (s) { shown = shown.concat(s.agents); });
    var mine = shown.filter(function (a) { return a.owner === ME; })[0];
    return (mine || shown[0] || {name: ""}).name;
  }

  function choose(name, push) {
    var url = name ? href(name) : HOME;
    if (url !== window.location.pathname + window.location.search) {
      window.history[push ? "pushState" : "replaceState"](null, "", url);
    }
    if (name && A.rail && A.rail.agentKey) A.store.set(A.rail.agentKey, url);
    if (name === chosen) { drawList(); drawHead(); drawComposer(); return; }
    start(name);
    if (A.rail) A.rail.closeDrawer(false);
  }

  function fromAddress() {
    var name = new URLSearchParams(window.location.search).get("name") || "";
    return find(name) ? name : fallback();
  }
  window.addEventListener("popstate", function () { if (S.members) choose(fromAddress(), false); });

  S.onMembers(function () {
    if (!chosen || !find(chosen)) { choose(fromAddress(), false); return; }
    drawList();
    drawHead();
    drawComposer();
  });
  S.loadMembers();
  setInterval(news, EVERY_MS);

  // ------------------------------------------------------------------ the composer

  function grow() {
    el.text.style.height = "auto";
    if (!el.text.value) { el.text.style.height = ""; el.text.style.overflowY = "hidden"; return; }
    var max = parseFloat(getComputedStyle(el.text).maxHeight) || Infinity;
    el.text.style.height = Math.min(el.text.scrollHeight + 2, max) + "px";
    el.text.style.overflowY = el.text.scrollHeight + 2 > max ? "auto" : "hidden";
  }
  async function send() {
    var text = el.text.value;
    if (!text.trim() || !chosen) return;
    var r = await A.request(API + "messages", null, {to: chosen, text: text});
    if (!r.ok) { el.out.textContent = A.refusal("ag.refused", r.data); return; }
    el.text.value = "";
    el.out.textContent = "";
    grow();
    await news();
    toBottom();
  }
  el.text.addEventListener("keydown", function (ev) {
    // Enter sends; Shift+Enter is a new line; Enter that ends an input-method composition does neither.
    if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing && ev.keyCode !== 229) {
      ev.preventDefault();
      send();
    }
  });
  el.text.addEventListener("input", grow);
  el.form.addEventListener("submit", function (ev) { ev.preventDefault(); send(); });
})();
