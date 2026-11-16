// The settings layer (#settings-layer): project settings or one channel's, one section at a time.
// - The list of sections (#settings-nav, the second column) switches the section in place and names it in the
//   top-right cell (#settings-title); each has its own address, so a reload or a shared link shows the same one, and
//   the browser's back goes back through them. The bare address is the first section. Below 900 px the list is in
//   the drawer, as every second column.
// - The close control (#settings-close) and Escape go back to the page the layer was opened from (project.js keeps
//   it), else to chat.
// - Project: overview (for who may change the project's settings: its name, repository and notice channel as forms,
//   and "delete project", floating with the address typed), members (one table of people and agents: the non-default
//   groups as chips, x to take one away; the default ones as a quiet line, never changed by hand; + gives or takes the
//   other groups as check boxes; removal from the project), groups (the groups people organise in their order, the
//   highest first, then each person's own agent group in a section of its own, in their order among themselves; with
//   a filter and "new group", a floating panel: who may manage groups drags a row to move it within its section, or
//   moves it with "move up" / "move down" in the row's menu; under them the three default groups, owner, human and
//   AI, each a row of its own marked "預設", not draggable; a chosen group, ?g= in the address, under "← 群組" on a
//   narrow screen, in two tabs: settings (its name, renamed in place for a custom group; "show separately in the
//   member list"; its permissions; for a person's own agent group also what others may do with those agents; removal
//   at the foot) and members (adding several at once from a list of check boxes with a filter; read only for a default
//   group)), invitations (a new one's link shown once with its copy control; the unused ones listed, each revoked in
//   two steps).
// - Channel: overview (rename; delete, floating, not for the notice channel), permissions (each group's read and post
//   in the channel as three-state controls: deny, inherit, allow; owner's row says it always can; a person's agent
//   group only once added; under the table who may read the channel now), notifications (my mute and my agents').
// - Me: me.js.
// The data is /api/members (embedded at first, then read again every 15 s while nobody is mid-act). Only what the
// reader may do is offered (Asterism.people's rules); a refusal shows the page's own sentence for its code where the
// act was (under the field for a name refused); "saved" is said in place, at the row's end, for a moment.
// Taking out of a group confirms in place; removing a group or a member floats.
"use strict";
(function () {
  var A = window.Asterism, layer = document.getElementById("settings-layer");
  if (!A || !layer || !A.people) return;
  var t = A.t, make = A.make, P = A.people;
  var SLUG = layer.dataset.slug, SCOPE = layer.dataset.scope, BASE = layer.dataset.base, CHANNEL = layer.dataset.channel;
  var API = "/" + encodeURIComponent(SLUG) + "/api/";
  var CATALOGUE = A.parseJSON(layer.dataset.catalogue, []), MANAGEMENT = A.parseJSON(layer.dataset.management, []);
  var SWITCHES = A.parseJSON(layer.dataset.switches, []);
  var EVERY_MS = 15000;
  var view = A.parseJSON(layer.dataset.view, null), last = JSON.stringify(view), rules = P.rules(view);
  var nav = document.getElementById("settings-nav"), heading = document.getElementById("settings-title");
  var sections = Array.prototype.slice.call(layer.querySelectorAll(".set-sec"));
  var names = sections.map(function (s) { return s.dataset.section; });
  var current = "";

  // ------------------------------------------------------------------ sections

  function sectionFromPath() {
    var path = window.location.pathname;
    if (path.indexOf(BASE + "/") === 0) return decodeURIComponent(path.slice(BASE.length + 1));
    if (/\/members$/.test(path)) return new URLSearchParams(window.location.search).get("g") ? "groups" : "members";
    if (/\/admin$/.test(path)) return "invites";
    return "";
  }

  function show(section, focus) {
    var cur = names.indexOf(section) >= 0 ? section : names[0];
    current = cur;
    sections.forEach(function (s) { s.hidden = s.dataset.section !== cur; });
    Array.prototype.forEach.call(nav.querySelectorAll("a[data-section]"), function (a) {
      if (a.dataset.section === cur) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    var title = layer.querySelector("#set-h-" + cur);
    if (title) heading.textContent = title.textContent;
    document.title = (title ? title.textContent + " · " : "") + document.title.split(" · ").slice(-1)[0];
    draw(cur);
    if (focus) heading.focus({preventScroll: true});
  }

  function go(section) {
    var url = BASE + (section ? "/" + section : "");
    if (url !== window.location.pathname + window.location.search) window.history.pushState(null, "", url);
    show(section, true);
  }

  nav.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest("a[data-section]");
    if (!a || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
    ev.preventDefault();
    if (A.rail) A.rail.closeDrawer(false);
    go(a.dataset.section);
  });
  window.addEventListener("popstate", function () { show(sectionFromPath(), false); });

  // ------------------------------------------------------------------ closing

  function leave() {
    var from = null;
    try { from = sessionStorage.getItem(A.project.fromKey); } catch (err) { from = null; }
    var mine = "/" + encodeURIComponent(SLUG);
    if (typeof from !== "string" || (from !== mine && from.indexOf(mine + "/") !== 0 && from.indexOf(mine + "#") !== 0)
        || A.project.isSettings(from.split(/[?#]/)[0])) {
      from = A.rail ? A.rail.chatHref() : mine;
    }
    window.location.href = from;
  }
  document.getElementById("settings-close").addEventListener("click", leave);
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape" || ev.defaultPrevented || document.querySelector("dialog[open]") || A.popup.isOpen()) return;
    var a = document.activeElement;
    if (a && a.tagName === "INPUT" && a.type === "search" && a.value) return;     // Escape clears the field first
    if (A.rail && A.rail.isDrawer()) return;
    leave();
  });

  // ------------------------------------------------------------------ the data

  function busy() {
    var a = document.activeElement;
    return A.isArmed(layer) || !!dragging || !!document.querySelector("dialog.gone[open]") || A.popup.isOpen() ||
           !!document.querySelector(".menu.shown") ||
           !!(a && layer.contains(a) && /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName) && a.type !== "checkbox" && a.type !== "search");
  }

  async function load(force) {
    if (!force && busy()) return;
    var r = await A.request(API + "members");
    if (!r.ok) return;
    var raw = JSON.stringify(r.data);
    if (raw === last && !force) return;
    if (!force && busy()) return;
    last = raw;
    view = r.data;
    rules = P.rules(view);
    draw(current);
  }

  function draw(section) {
    if (section === "members") drawMembers();
    else if (section === "groups") drawGroups();
  }

  function outOf(box) {
    var out = make("div", "out");
    out.setAttribute("aria-live", "polite");
    box.appendChild(out);
    return out;
  }

  // After an act on who is in which group: its refusal where it was (in the page's words), else the data again.
  function done(out) {
    return function (r) {
      if (r && !r.ok) { out.textContent = A.refusal("mem.regroup", r.data); return; }
      load(true);
    };
  }

  // ------------------------------------------------------------------ members

  var table = document.getElementById("members-table"), memberFilter = document.getElementById("members-filter");

  function matches(text, q) { return !q || text.toLowerCase().indexOf(q) >= 0; }

  function memberRow(who, isAgent) {
    var tr = make("tr"), out;
    tr.dataset.member = who.name;
    var name = make("td", "mcell-name"), line = make("div", "mline");
    line.append(A.side ? A.side.presence(isAgent ? {kind: "agent", online: who.online} : {kind: "person"}) : make("span"),
                make("span", "mname" + (isAgent ? " mono" : ""), who.name));
    if (isAgent && who.busy) line.appendChild(make("span", "word", t("mem.busy")));
    name.appendChild(line);
    var kind = make("td", "dim", isAgent ? t("mem.agent_of", {owner: who.owner}) + " · " +
                                          t(who.online ? "presence.online" : "presence.offline") : t("mem.kind_person"));
    var groups = make("td"), chips = make("div", "mtags");
    var after = function (r) { done(out)(r); };
    var plain = rules.plainOf(who), defaults = rules.defaultsOf(who);
    if (!plain.length) chips.appendChild(make("span", "dim small", t("mem.no_groups")));
    plain.forEach(function (g) { chips.appendChild(P.chip(rules, who, isAgent, g.name, after)); });
    var plus = P.plus(function () { return rules; }, who, isAgent, after, true);
    if (plus) chips.appendChild(plus);
    groups.appendChild(chips);
    if (defaults.length) {
      groups.appendChild(make("p", "mdefaults", t("mem.default_line", {names: defaults.map(rules.label).join("・")})));
    }
    var acts = make("td", "mcell-acts");
    if (rules.mayRemove(who, isAgent)) {
      var b = A.button("btn", t("mem.remove_member"));
      b.dataset.key = "rm:" + who.name;
      b.addEventListener("click", function () {
        P.remove(who, isAgent, b, memberFilter, function () { load(true); });
      });
      acts.appendChild(b);
    }
    out = outOf(groups);
    tr.append(name, kind, groups, acts);
    return tr;
  }

  function drawMembers() {
    if (!table) return;
    var q = (memberFilter.value || "").trim().toLowerCase();
    A.keepFocus(table, function () {
      table.textContent = "";
      var wrap = make("div", "table-wrap"), tbl = make("table", "members-table"), head = make("thead"), hr = make("tr");
      [t("col.name"), t("set.kind"), t("col.groups"), ""].forEach(function (h) { hr.appendChild(make("th", "", h)); });
      head.appendChild(hr);
      var tb = make("tbody");
      view.people.forEach(function (who) { if (matches(who.name, q)) tb.appendChild(memberRow(who, false)); });
      view.agents.forEach(function (who) {
        if (matches(who.name, q) || matches(who.owner, q)) tb.appendChild(memberRow(who, true));
      });
      if (!tb.children.length) {
        var none = make("tr"), td = make("td", "dim", t("mem.no_match"));
        td.colSpan = 4;
        none.appendChild(td);
        tb.appendChild(none);
      }
      tbl.append(head, tb);
      wrap.appendChild(tbl);
      table.appendChild(wrap);
    });
  }
  if (memberFilter) memberFilter.addEventListener("input", drawMembers);

  // A member named in the address (?m=, the profile card's "open in settings"): scrolled to and marked.
  function markMember() {
    var name = new URLSearchParams(window.location.search).get("m");
    if (!name || current !== "members") return;
    var row = Array.prototype.filter.call(table.querySelectorAll("tr[data-member]"), function (r) {
      return r.dataset.member === name;
    })[0];
    if (!row) return;
    row.scrollIntoView({block: "center"});
    row.classList.add("flash");
    setTimeout(function () { row.classList.remove("flash"); }, 1500);
  }

  // ------------------------------------------------------------------ groups

  var groupsRoot = document.getElementById("groups-root"), list = document.getElementById("groups-body");
  var detail = document.getElementById("group-detail"), groupFilter = document.getElementById("groups-filter");
  var tabs = {};                                    // group -> the tab chosen

  function chosen() { return current === "groups" ? new URLSearchParams(window.location.search).get("g") || "" : ""; }

  function goGroup(name, focusDetail) {
    var url = BASE + "/groups" + (name ? "?g=" + encodeURIComponent(name) : "");
    if (url !== window.location.pathname + window.location.search) window.history.pushState(null, "", url);
    current = "groups";
    drawGroups();
    if (focusDetail) detail.focus({preventScroll: false});
    else if (!name) { var row = list.querySelector("a.place"); if (row) row.focus(); }
  }

  function plainGroups() { return view.groups.filter(function (g) { return !rules.isDefault(g); }); }
  // The groups people organise, and each person's own agent group: two lists, each in its order; the person's agent
  // groups come after the others (they say whose an agent is, one per person, and would otherwise fill the top).
  function customGroups() { return plainGroups().filter(function (g) { return g.kind !== "ownership"; }); }
  function agentGroups() { return plainGroups().filter(function (g) { return g.kind === "ownership"; }); }
  function sameList(g) { return g.kind === "ownership" ? agentGroups() : customGroups(); }
  function mayOrder() { return rules.mine("manage_groups"); }

  // A new order of the non-default groups: `name` moved to `to` (an index in its own list); the other list keeps its
  // order, after the custom groups.
  async function reorder(name, to, out) {
    var g = rules.group(name);
    if (!g) return;
    var names = sameList(g).map(function (x) { return x.name; }), from = names.indexOf(name);
    if (from < 0 || to < 0 || to >= names.length || to === from) return;
    names.splice(from, 1);
    names.splice(to, 0, name);
    var rest = (g.kind === "ownership" ? customGroups() : agentGroups()).map(function (x) { return x.name; });
    names = g.kind === "ownership" ? rest.concat(names) : names.concat(rest);
    var r = await A.request(API + "groups/order", null, {names: names});
    if (!r.ok) { if (out) out.textContent = A.refusal("mem.order", r.data); return; }
    if (out) out.textContent = t("mem.moved");
    await load(true);
    var again = list.querySelector('[data-key="gm:' + name.replace(/["\\]/g, "\\$&") + '"]');
    if (again) again.focus();
  }

  function groupMenu(g, b) {
    var items = [{label: t("mem.open_group"), run: function () { goGroup(g.name, true); }}];
    if (!rules.isDefault(g) && mayOrder() && !(groupFilter.value || "").trim()) {
      var names = sameList(g).map(function (x) { return x.name; }), i = names.indexOf(g.name), out = orderOut;
      items.push({separator: true},
                 {label: t("mem.move_up"), disabled: i <= 0, run: function () { reorder(g.name, i - 1, out); }},
                 {label: t("mem.move_down"), disabled: i >= names.length - 1, run: function () { reorder(g.name, i + 1, out); }});
    }
    if (g.kind === "custom" && rules.mine("manage_groups") && rules.holdsAll(g.permissions)) {
      items.push({separator: true}, {label: t("mem.remove_group"), run: function () { removeGroup(g, b); }});
    }
    A.menu({label: t("mem.group_acts", {name: rules.label(g)}), anchor: b}, items, b);
  }

  var dragging = null, orderOut = null;

  // Dragging a row (who may manage groups, with no filter): it goes before or after the row it is dropped on.
  function draggable(li, g) {
    li.draggable = true;
    li.classList.add("draggable");
    li.addEventListener("dragstart", function (ev) {
      dragging = g.name;
      li.classList.add("dragging");
      ev.dataTransfer.effectAllowed = "move";
      try { ev.dataTransfer.setData("text/plain", g.name); } catch (err) { /* the name is kept above */ }
    });
    li.addEventListener("dragend", function () {
      dragging = null;
      li.classList.remove("dragging");
      Array.prototype.forEach.call(list.querySelectorAll(".drop-before, .drop-after"), function (x) {
        x.classList.remove("drop-before", "drop-after");
      });
    });
    li.addEventListener("dragover", function (ev) {
      var from = dragging && rules.group(dragging);
      if (!from || dragging === g.name || (from.kind === "ownership") !== (g.kind === "ownership")) return;
      ev.preventDefault();
      var r = li.getBoundingClientRect(), before = ev.clientY < r.top + r.height / 2;
      li.classList.toggle("drop-before", before);
      li.classList.toggle("drop-after", !before);
    });
    li.addEventListener("dragleave", function () { li.classList.remove("drop-before", "drop-after"); });
    li.addEventListener("drop", function (ev) {
      ev.preventDefault();
      var name = dragging || ev.dataTransfer.getData("text/plain");
      var before = li.classList.contains("drop-before");
      li.classList.remove("drop-before", "drop-after");
      if (!name || name === g.name) return;
      var names = sameList(g).map(function (x) { return x.name; });
      if (names.indexOf(name) < 0) return;
      var to = names.indexOf(g.name) + (before ? 0 : 1);
      if (names.indexOf(name) < to) to -= 1;
      reorder(name, to, orderOut);
    });
  }

  function entry(g, compact, order) {
    var li = make("li", "grow"), a = make("a", "place");
    a.href = BASE + "/groups?g=" + encodeURIComponent(g.name);
    a.dataset.key = "g:" + g.name;
    a.dataset.group = g.name;
    if (chosen() === g.name) a.setAttribute("aria-current", "true");
    var n = rules.count(g.name), c = make("span", "count", t("mem.count", {n: n}));
    c.setAttribute("aria-hidden", "true");
    a.appendChild(make("span", "place-name" + (g.kind === "custom" ? " mono" : ""), rules.label(g)));
    if (rules.isDefault(g)) a.appendChild(make("span", "default-mark", t("mem.default")));
    a.append(c, make("span", "vh", t("mem.count_label", {n: n})));
    if (order) {
      var grip = make("span", "grip");
      grip.title = t("mem.order_drag");
      grip.setAttribute("aria-hidden", "true");
      grip.appendChild(A.glyph("grip"));
      li.appendChild(grip);
      draggable(li, g);
    }
    li.appendChild(a);
    if (!compact) {
      var b = A.button("row-acts shown");
      b.appendChild(make("span", "dots"));
      b.firstChild.setAttribute("aria-hidden", "true");
      b.setAttribute("aria-label", t("mem.group_acts", {name: rules.label(g)}));
      b.title = t("mem.group_acts", {name: rules.label(g)});
      b.setAttribute("aria-haspopup", "menu");
      b.setAttribute("aria-expanded", "false");
      b.dataset.key = "gm:" + g.name;
      b.addEventListener("click", function () { groupMenu(g, b); });
      li.appendChild(b);
    }
    return li;
  }

  function drawList(compact) {
    var q = (groupFilter.value || "").trim().toLowerCase();
    list.textContent = "";
    if (compact) {
      var back = make("a", "place groups-back", t("mem.back_list"));
      back.href = BASE + "/groups";
      back.dataset.key = "g-back";
      list.appendChild(back);
    }
    function found(g) { return matches(rules.label(g), q) || matches(g.name, q); }
    var gs = customGroups().filter(found), own = agentGroups().filter(found);
    var defaults = view.groups.filter(rules.isDefault).filter(function (g) {
      return found(g) || matches(t("mem.default"), q);
    });
    if (!gs.length && !own.length && !defaults.length) { if (q) list.appendChild(make("p", "dim", t("mem.no_match"))); return; }
    var order = mayOrder() && !q && !compact;
    orderOut = make("p", "out");
    orderOut.setAttribute("aria-live", "polite");
    if (gs.length) {
      var sec = make("section", "groups-sec"), ul = make("ul", "side-list groups-order");
      if (!compact) sec.appendChild(make("p", "groups-hint", t("mem.order_hint")));
      gs.forEach(function (g) { ul.appendChild(entry(g, compact, order)); });
      sec.appendChild(ul);
      list.appendChild(sec);
    }
    // Each person's own agent group: a section of their own, still in their order among themselves.
    if (own.length) {
      var osec = make("section", "groups-sec groups-own"), oul = make("ul", "side-list groups-order");
      osec.appendChild(make("h3", "groups-sub", t("mem.agent_groups")));
      own.forEach(function (g) { oul.appendChild(entry(g, compact, order)); });
      osec.appendChild(oul);
      list.appendChild(osec);
    }
    list.appendChild(orderOut);
    // The default groups: each its own row under the ordered ones, never dragged.
    if (defaults.length) {
      var dl = make("ul", "side-list groups-defaults-list");
      defaults.forEach(function (g) { dl.appendChild(entry(g, compact, false)); });
      list.appendChild(dl);
    }
  }

  if (list) {
    list.addEventListener("click", function (ev) {
      var a = ev.target.closest && ev.target.closest("a.place");
      if (!a || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
      ev.preventDefault();
      goGroup(a.dataset.group || "", !!a.dataset.group);
    });
    list.addEventListener("contextmenu", function (ev) {
      var a = ev.target.closest && ev.target.closest("a.place[data-group]");
      var g = a && rules.group(a.dataset.group);
      if (!g) return;
      ev.preventDefault();
      groupMenu(g, a);
    });
    groupFilter.addEventListener("input", function () { drawList(!!chosen()); });
  }

  // ---- one group, in tabs

  function memberLine(who, isAgent) {
    var li = make("li", "mrow"), text = make("div", "mtext");
    text.appendChild(make("span", "mname" + (isAgent ? " mono" : ""), who.name));
    var sub = [];
    if (isAgent) sub.push(t("mem.agent_of", {owner: who.owner}), t(who.online ? "presence.online" : "presence.offline"));
    if (isAgent && who.busy) sub.push(t("mem.busy"));
    if (sub.length) text.appendChild(make("span", "msub", sub.join(" · ")));
    li.append(A.side ? A.side.presence(isAgent ? {kind: "agent", online: who.online} : {kind: "person"}) : make("span"), text);
    return li;
  }

  function filterField(key, label, onInput) {
    var input = make("input");
    input.type = "search";
    input.placeholder = label;
    input.setAttribute("aria-label", label);
    input.autocomplete = "off";
    input.dataset.key = key;
    input.addEventListener("input", onInput);
    return input;
  }

  // Who may switch "show separately": for a custom group who may manage groups; for a person's agents that person
  // or who may manage groups.
  function maySeparate(g) {
    if (rules.isDefault(g)) return false;
    return rules.mine("manage_groups") || (g.kind === "ownership" && g.owner === view.me.name);
  }

  function settingsTab(g) {
    var box = make("div", "gd-tab");
    box.appendChild(nameBlock(g));
    box.appendChild(make("p", "dim", g.kind === "ownership" ? t("mem.kind.ownership", {owner: g.owner})
                                                            : t("mem.kind." + g.kind, {name: g.name})));
    if (!rules.isDefault(g)) box.appendChild(separateRow(g));
    box.appendChild(make("h3", "gd-sub", t("mem.perms_heading")));
    box.appendChild(permsBlock(g));
    if (g.kind === "ownership") box.appendChild(agentPermsBlock(g));
    if (g.kind === "custom" && rules.mine("manage_groups") && rules.holdsAll(g.permissions)) {
      var sec = make("section", "gd-sec danger-zone");
      sec.appendChild(make("h3", "", t("mem.remove_group")));
      sec.appendChild(make("p", "", t("mem.remove_group_hint", {name: g.name})));
      var b = A.button("btn danger", t("mem.remove_group"));
      b.dataset.key = "grm:" + g.name;
      b.addEventListener("click", function () { removeGroup(g, b); });
      sec.appendChild(b);
      box.appendChild(sec);
    }
    return box;
  }

  // The group's name: a custom group's renamed in place by who may manage groups; the others' fixed.
  function nameBlock(g) {
    if (g.kind !== "custom" || !rules.mine("manage_groups")) {
      var facts = make("dl", "set-facts");
      facts.append(make("dt", "", t("set.name")), make("dd", "set-name mono", g.name));
      if (rules.label(g) !== g.name) facts.append(make("dt", "", t("mem.list_label")), make("dd", "", rules.label(g)));
      facts.append(make("dt", "", t("mem.members")), make("dd", "", t("mem.count_label", {n: rules.count(g.name)})));
      return facts;
    }
    var form = make("form", "stack set-form"), label = make("label", "field"), input = make("input");
    input.name = "name";
    input.value = g.name;
    input.required = true;
    input.maxLength = 40;
    input.autocomplete = "off";
    input.spellcheck = false;
    input.setAttribute("autocapitalize", "off");
    input.dataset.key = "gname:" + g.name;
    label.append(make("span", "", t("set.name")), input);
    var row = make("div", "row"), go = make("button", "btn", t("mem.rename")), out = make("span", "out");
    out.setAttribute("aria-live", "polite");
    row.append(go, out);
    form.append(label, make("p", "dim", t("mem.rename_hint")), row);
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var name = input.value.trim();
      out.textContent = "";
      if (name === g.name) return;
      var r = await A.request(API + "groups/" + encodeURIComponent(g.name), null, {name: name});
      if (!r.ok) {
        if (/^(invalid_name|conflict)$/.test(r.data.error)) A.fieldError(input, A.refusal("grp.name", r.data));
        else out.textContent = A.refusal("grp.change", r.data);
        return;
      }
      tabs[name] = tabs[g.name];
      window.history.replaceState(null, "", BASE + "/groups?g=" + encodeURIComponent(name));
      await load(true);
      var again = detail.querySelector('[data-key="gname:' + name.replace(/["\\]/g, "\\$&") + '"]');
      if (again) {
        again.focus();
        A.saved(again.form && again.form.querySelector(".out"));
      }
    });
    return form;
  }

  // Show separately: one switch, saved as it changes.
  function separateRow(g) {
    var rows = make("div", "perm-list"), row = make("div", "perm-row"), input = make("input");
    input.type = "checkbox";
    input.id = "sep-" + g.name;
    input.checked = !!g.separate;
    input.disabled = !maySeparate(g);
    input.dataset.key = "sep:" + g.name;
    var text = make("label", "perm-text"), out = make("span", "out");
    text.htmlFor = input.id;
    out.setAttribute("aria-live", "polite");
    text.append(make("span", "perm-name", t("mem.separate")), make("span", "perm-hint", t("mem.separate_hint")));
    if (input.disabled) text.appendChild(make("span", "perm-hint", t("mem.separate_readonly")));
    text.appendChild(out);
    row.append(input, text);
    rows.appendChild(row);
    input.addEventListener("change", async function () {
      out.textContent = "";
      var r = await A.request(API + "groups/" + encodeURIComponent(g.name), null, {separate: input.checked});
      if (!r.ok) { input.checked = !input.checked; out.textContent = A.refusal("grp.change", r.data); return; }
      g.separate = input.checked;
      A.saved(out);
    });
    return rows;
  }

  function removeGroup(g, opener) {
    A.gone({title: t("gone.group.title", {name: g.name}), text: t("gone.group.text", {name: g.name}), name: g.name,
            button: t("gone.group.button"), opener: opener, after: groupFilter, act: "grp.remove",
            run: function () { return A.request(API + "groups/" + encodeURIComponent(g.name) + "/remove", null, {}); },
            done: async function () {
              window.history.replaceState(null, "", BASE + "/groups");
              await load(true);
            }});
  }

  // Who may set a group's permissions: owner's never (it holds every one); a person's own agent group only that
  // person; any other group who may manage groups and holds what it carries.
  function permsEditable(g) {
    if (g.kind === "default" && g.name === "owner") return false;
    if (g.kind === "ownership") return g.owner === view.me.name;
    return rules.mine("manage_groups") && rules.holdsAll(g.permissions);
  }
  // Everything a group may carry, in the catalogue's order: a person's own agent group also the four of its own.
  function carried(g) { return g.kind === "ownership" ? CATALOGUE.concat(SWITCHES) : CATALOGUE; }

  function permRow(g, p, editable) {
    var row = make("div", "perm-row"), box = make("input"), id = "perm-" + p;
    var own = SWITCHES.indexOf(p) >= 0;          // one of the four only a person's own agent group carries
    box.type = "checkbox";
    box.id = id;
    box.checked = g.permissions.indexOf(p) >= 0;
    box.disabled = !editable || (!own && !rules.mine(p));
    box.dataset.key = "perm:" + g.name + ":" + p;
    var text = make("label", "perm-text");
    text.htmlFor = id;
    text.append(make("span", "perm-name", t("perm." + p)), make("span", "perm-hint", t("perm_hint." + p)));
    var out = make("span", "out");
    out.setAttribute("aria-live", "polite");
    if (editable && !own && !rules.mine(p)) {
      row.classList.add("unheld");
      text.appendChild(make("span", "perm-hint", t("mem.perm_unheld")));
    }
    text.appendChild(out);
    row.append(box, text);
    row.dataset.text = (t("perm." + p) + " " + t("perm_hint." + p) + " " + p).toLowerCase();
    box.addEventListener("change", async function () {
      var want = carried(g).filter(function (x) { return x === p ? box.checked : g.permissions.indexOf(x) >= 0; });
      out.textContent = "";
      var r = await A.request(API + "groups/" + encodeURIComponent(g.name), null, {permissions: want});
      if (!r.ok) {
        box.checked = !box.checked;
        out.textContent = A.refusal("grp.change", r.data);
        return;
      }
      g.permissions = r.data.permissions;      // the page's copy follows; the next reading redraws the rest
      A.saved(out);
    });
    return row;
  }

  function permsBlock(g) {
    var box = make("div", "gd-perms"), editable = permsEditable(g);
    box.appendChild(make("p", "dim", t("mem.perms_hint")));
    var why = g.kind === "default" && g.name === "owner" ? "mem.perms_fixed"
              : g.kind === "ownership" ? (editable ? null : "mem.perms_own_only")
              : !rules.mine("manage_groups") ? "mem.perms_readonly" : !rules.holdsAll(g.permissions) ? "mem.perms_not_mine" : null;
    if (why) box.appendChild(make("p", "dim", t(why, {owner: g.owner || ""})));
    var plain = make("div", "perm-list"), manage = make("div", "perm-list");
    var mgmt = [make("h3", "gd-sub", t("mem.management")), make("p", "dim", t("mem.management_hint")), manage];
    var filter = filterField("pfilter:" + g.name, t("mem.filter_perms"), function () {
      var q = filter.value.trim().toLowerCase();
      [plain, manage].forEach(function (l) {
        Array.prototype.forEach.call(l.children, function (r) { r.hidden = !matches(r.dataset.text, q); });
      });
      mgmt.forEach(function (n) {
        n.hidden = !Array.prototype.some.call(manage.children, function (r) { return !r.hidden; });
      });
    });
    box.appendChild(make("div", "set-filter")).appendChild(filter);
    CATALOGUE.forEach(function (p) {
      (MANAGEMENT.indexOf(p) >= 0 ? manage : plain).appendChild(permRow(g, p, editable));
    });
    box.appendChild(plain);
    mgmt.forEach(function (n) { box.appendChild(n); });
    return box;
  }

  // A person's own agent group: what others may do with that person's agents, set only by that person.
  function agentPermsBlock(g) {
    var box = make("div", "gd-perms"), editable = g.owner === view.me.name;
    box.append(make("h3", "gd-sub", t("mem.agent_perms")), make("p", "dim", t("mem.agent_perms_hint", {owner: g.owner})));
    var list = make("div", "perm-list");
    SWITCHES.forEach(function (p) { list.appendChild(permRow(g, p, editable)); });
    box.appendChild(list);
    return box;
  }

  // Adding members to a group, several in one go: everyone not in it yet as a list of check boxes (people, then
  // agents) with a filter, and one button that adds those checked. Another person's agent whose person keeps its groups
  // closed is listed disabled, with why. What is checked survives the list being drawn again.
  var picked = {};                                  // group -> {name: true}
  function addBlock(g) {
    var sec = make("section", "gd-adding"), mine = picked[g.name] = picked[g.name] || {};
    var people = view.people.filter(function (x) { return x.groups.indexOf(g.name) < 0; });
    var agents = view.agents.filter(function (x) { return x.groups.indexOf(g.name) < 0; });
    var cands = people.map(function (x) { return [x, false]; }).concat(agents.map(function (x) { return [x, true]; }))
      .filter(function (c) { return rules.mayAdd(c[0], c[1], g) || rules.closedToMe(c[0], c[1]); });
    sec.appendChild(make("h3", "gd-sub", t("mem.add_heading")));
    if (!cands.length) { sec.appendChild(make("p", "dim", t("mem.add_none"))); return sec; }
    Object.keys(mine).forEach(function (n) {
      if (!cands.some(function (c) { return c[0].name === n && rules.mayAdd(c[0], c[1], g); })) delete mine[n];
    });
    var list = make("div", "perm-list gd-pick"), out = make("span", "out");
    out.setAttribute("aria-live", "polite");
    var go = A.button("btn primary", "");
    go.dataset.key = "gadd-go:" + g.name;
    function count() {
      var n = Object.keys(mine).length;
      go.textContent = n ? t("mem.add_n", {n: n}) : t("mem.add");
      go.disabled = !n;
    }
    var filter = filterField("gaddf:" + g.name, t("mem.filter_add"), function () {
      var q = filter.value.trim().toLowerCase();
      Array.prototype.forEach.call(list.children, function (r) { r.hidden = !matches(r.dataset.name, q); });
    });
    cands.forEach(function (c, i) {
      var who = c[0], isAgent = c[1], ok = rules.mayAdd(who, isAgent, g);
      var row = make("div", "perm-row"), box = make("input"), text = make("label", "perm-text");
      box.type = "checkbox";
      box.id = "gadd-" + i;
      box.checked = !!mine[who.name];
      box.disabled = !ok;
      box.dataset.key = "gadd:" + g.name + ":" + who.name;
      text.htmlFor = box.id;
      text.append(make("span", "perm-name" + (isAgent ? " mono" : ""), who.name),
                  make("span", "perm-hint", isAgent ? (ok ? t("mem.agent_of", {owner: who.owner})
                                                          : t("mem.closed_add", {owner: who.owner}))
                                                    : t("mem.kind_person")));
      row.dataset.name = (who.name + " " + (who.owner || "")).toLowerCase();
      row.append(box, text);
      box.addEventListener("change", function () {
        if (box.checked) mine[who.name] = true; else delete mine[who.name];
        count();
      });
      list.appendChild(row);
    });
    go.addEventListener("click", async function () {
      var names = Object.keys(mine);
      go.disabled = true;
      out.textContent = "";
      for (var i = 0; i < names.length; i++) {
        var r = await P.regroup(names[i], [g.name], []);
        if (!r.ok) { out.textContent = names[i] + ": " + A.refusal("mem.regroup", r.data); break; }
        delete mine[names[i]];
      }
      await load(true);
      var again = detail.querySelector('[data-key="gadd-go:' + g.name.replace(/["\\]/g, "\\$&") + '"]');
      if (again) {
        var said = again.parentNode.querySelector(".out");
        if (out.textContent && said) said.textContent = out.textContent; else A.saved(said);
      }
    });
    count();
    var row = make("div", "row form-acts");
    row.append(out, go);
    var top = make("div", "set-filter");
    top.appendChild(filter);
    sec.append(top, list, row);
    return sec;
  }

  function membersTab(g) {
    var box = make("div", "gd-tab"), m = rules.inGroup(g.name);
    var ul = make("ul", "mlist");
    var filter = filterField("mfilter:" + g.name, t("mem.filter_members"), function () {
      var q = filter.value.trim().toLowerCase();
      Array.prototype.forEach.call(ul.children, function (li) { if (li.dataset.name) li.hidden = !matches(li.dataset.name, q); });
    });
    if (g.kind !== "ownership" && !rules.isDefault(g)) box.appendChild(addBlock(g));
    var top = make("div", "gd-add");
    top.appendChild(filter);
    box.appendChild(top);
    if (rules.isDefault(g)) box.appendChild(make("p", "dim", t("mem.members_readonly")));
    m.people.map(function (x) { return [x, false]; }).concat(m.agents.map(function (x) { return [x, true]; }))
      .forEach(function (c) {
        var who = c[0], isAgent = c[1], li = memberLine(who, isAgent), out;
        li.dataset.name = who.name.toLowerCase();
        if (g.kind !== "ownership" && rules.mayRegroup(who, isAgent, g)) {
          var acts = make("div", "macts");
          var b = A.button("btn", t("mem.take_out"));
          b.dataset.key = "gout:" + who.name;
          b.setAttribute("aria-label", t("mem.take_out_label", {group: rules.label(g), name: who.name}));
          b.addEventListener("click", async function () {
            if (!A.twoStep(b, t("mem.confirm_take_out", {group: rules.label(g), name: who.name}))) return;
            done(out)(await P.regroup(who.name, [], [g.name]));
          });
          acts.appendChild(b);
          li.appendChild(acts);
        } else if (g.kind !== "ownership" && rules.closedToMe(who, isAgent)) {
          li.appendChild(make("p", "mnote", t("mem.closed_regroup", {owner: who.owner})));
        }
        out = outOf(li);
        ul.appendChild(li);
      });
    if (!ul.childNodes.length) {
      ul.appendChild(make("li", "mempty", g.kind === "ownership" ? t("mem.no_agents", {owner: g.owner}) : t("mem.empty")));
    }
    box.appendChild(ul);
    return box;
  }

  // "← 群組" over an opened group, for a narrow screen, where the list is not beside it.
  function backLink() {
    var back = make("a", "gd-back", t("mem.back_groups"));
    back.href = BASE + "/groups";
    back.dataset.key = "gd-back";
    back.addEventListener("click", function (ev) {
      if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey || ev.button !== 0) return;
      ev.preventDefault();
      goGroup("", false);
    });
    return back;
  }

  function drawGroup(g) {
    detail.appendChild(backLink());
    var head = make("header", "gd-head"), h = make("h2", "gd-title", rules.label(g));
    h.id = "gd-title";
    if (rules.label(g) !== g.name) h.appendChild(make("small", "", g.name));
    head.appendChild(h);
    if (rules.isDefault(g)) head.appendChild(make("p", "", t("mem.default_hint")));
    detail.appendChild(head);
    // Two tabs for every group: its settings (name, display, permissions, removal) and its members.
    var kinds = [["settings", settingsTab], ["members", membersTab]];
    tabsOf(g.name, kinds.map(function (k) { return [k[0], function () { return k[1](g); }, t("mem.tab." + k[0])]; }));
  }

  // Tabs over one pane: kinds are [key, draw(), label]; the choice is kept per group (`id`).
  function tabsOf(id, kinds) {
    var label = rules.labelOf(id);
    var want = tabs[id] && kinds.some(function (k) { return k[0] === tabs[id]; }) ? tabs[id] : kinds[0][0];
    var bar = make("div", "tabs");
    bar.setAttribute("role", "tablist");
    bar.setAttribute("aria-label", t("mem.tabs", {name: label}));
    var pane = make("div", "tab-pane");
    pane.setAttribute("role", "tabpanel");
    pane.id = "gd-pane";
    kinds.forEach(function (k) {
      var b = A.button("tab-btn-plain", k[2]);
      b.setAttribute("role", "tab");
      b.id = "gd-tab-" + k[0].replace(/[^A-Za-z0-9_-]/g, "_");
      b.dataset.key = "tab:" + k[0];
      b.setAttribute("aria-controls", pane.id);
      b.setAttribute("aria-selected", String(k[0] === want));
      b.tabIndex = k[0] === want ? 0 : -1;
      b.addEventListener("click", function () {
        tabs[id] = k[0];
        drawGroups();
        var again = detail.querySelector('[data-key="tab:' + k[0] + '"]');
        if (again) again.focus();
      });
      bar.appendChild(b);
    });
    bar.addEventListener("keydown", function (ev) {
      var all = Array.prototype.slice.call(bar.children), i = all.indexOf(document.activeElement);
      if (i < 0) return;
      var n = all.length, j = ev.key === "ArrowRight" ? (i + 1) % n : ev.key === "ArrowLeft" ? (i + n - 1) % n :
                                ev.key === "Home" ? 0 : ev.key === "End" ? n - 1 : -1;
      if (j < 0) return;
      ev.preventDefault();
      all[j].click();
    });
    pane.setAttribute("aria-labelledby", "gd-tab-" + want.replace(/[^A-Za-z0-9_-]/g, "_"));
    pane.appendChild(kinds.filter(function (k) { return k[0] === want; })[0][1]());
    detail.append(bar, pane);
  }

  function drawMissing(name) {
    var head = make("header", "gd-head"), h = make("h2", "gd-title", name);
    h.id = "gd-title";
    var back = make("a", "", t("mem.back_list"));
    back.href = BASE + "/groups";
    back.dataset.key = "back-all";
    back.addEventListener("click", function (ev) { ev.preventDefault(); goGroup("", false); });
    var p = make("p", "", t("mem.no_group") + " ");
    p.appendChild(back);
    head.append(h, p);
    detail.appendChild(head);
  }

  function drawGroups() {
    if (!groupsRoot) return;
    var name = chosen(), g = name ? rules.group(name) : null;
    groupsRoot.classList.toggle("has-detail", !!name);
    A.keepFocus(groupsRoot, function () {
      drawList(!!name);
      detail.textContent = "";
      if (name && g) drawGroup(g); else if (name) drawMissing(name);
      detail.hidden = !name;
      if (name) detail.setAttribute("aria-labelledby", "gd-title");
    });
  }

  // ---- making a group

  // The form floats over the page (a modal panel), so neither the list nor the group shown moves.
  var form = document.getElementById("group-create"), opener = document.getElementById("group-create-open");
  var panel = document.getElementById("group-create-panel");
  function reveal(show) {
    if (show) { panel.showModal(); form.elements.name.focus(); } else if (panel.open) panel.close();
    opener.setAttribute("aria-expanded", String(show));
  }
  if (form && opener && panel) {
    opener.addEventListener("click", function () { reveal(!panel.open); });
    form.querySelector("[data-dismiss]").addEventListener("click", function () { reveal(false); });
    panel.querySelector("[data-close]").addEventListener("click", function () { reveal(false); });
    panel.addEventListener("close", function () { opener.setAttribute("aria-expanded", "false"); opener.focus(); });
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var out = form.querySelector("[data-out]"), name = form.elements.name.value.trim();
      var perms = Array.prototype.filter.call(form.querySelectorAll('input[name="perm"]'), function (b) { return b.checked; })
        .map(function (b) { return b.value; });
      var r = await A.request(API + "groups", null, {name: name, permissions: perms});
      if (!r.ok) {
        if (/^(invalid_name|conflict)$/.test(r.data.error)) A.fieldError(form.elements.name, A.refusal("grp.name", r.data));
        else out.textContent = A.refusal("grp.create", r.data);
        return;
      }
      out.textContent = "";
      form.reset();
      reveal(false);
      window.history.pushState(null, "", BASE + "/groups?g=" + encodeURIComponent(r.data.name));
      await load(true);
      detail.focus();
    });
  }

  // ------------------------------------------------------------------ the project: overview

  Array.prototype.forEach.call(layer.querySelectorAll("form[data-project-field]"), function (f) {
    var field = f.dataset.projectField, out = f.querySelector(".out");
    f.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var body = {};
      body[field] = (f.elements[field].value || "").trim();
      out.textContent = "";
      var r = await A.request(API + "project", null, body);
      if (!r.ok) {
        var input = f.elements[field];
        if (input && input.type !== "hidden" && /^invalid_/.test(r.data.error)) A.fieldError(input, A.refusal("set.project", r.data));
        else out.textContent = A.refusal("set.project", r.data);
        return;
      }
      if (field === "name") { window.location.reload(); return; }       // the name is in the frame too
      A.saved(out);
    });
  });
  var dropProject = document.getElementById("project-delete");
  if (dropProject) {
    dropProject.addEventListener("click", function () {
      var slug = dropProject.dataset.slug;
      A.gone({title: t("gone.project.title", {name: slug}), text: t("gone.project.text"), name: slug,
              button: t("gone.project.button"), opener: dropProject,
              run: function () { return A.request(API + "project/delete", null, {confirm: slug}); },
              done: function () { window.location.href = "/"; }});
    });
  }

  // ------------------------------------------------------------------ a channel: overview

  var renameForm = document.getElementById("channel-rename");
  if (renameForm) {
    renameForm.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var out = renameForm.querySelector(".out"), name = renameForm.elements.name.value.trim().replace(/^#/, "");
      out.textContent = "";
      if (name === CHANNEL) return;
      var r = await A.request(API + "channels/" + encodeURIComponent(CHANNEL), null, {name: name});
      if (!r.ok) {
        if (/^(bad_request|conflict)$/.test(r.data.error)) {
          A.fieldError(renameForm.elements.name, A.refusal("chan.rename", r.data, {name: name}));
        } else out.textContent = A.refusal("chan.rename", r.data, {name: name});
        return;
      }
      window.location.replace("/" + encodeURIComponent(SLUG) + "/channels/" + encodeURIComponent(r.data.name) + "/settings");
    });
  }
  var dropChannel = document.getElementById("channel-delete");
  if (dropChannel) {
    dropChannel.addEventListener("click", function () {
      A.gone({title: t("gone.channel.title", {name: CHANNEL}), text: t("gone.channel.text", {name: CHANNEL}), name: null,
              button: t("gone.channel.button"), opener: dropChannel,
              run: function () { return A.request(API + "channels/" + encodeURIComponent(CHANNEL) + "/delete", null, {}); },
              done: function () { window.location.href = "/" + encodeURIComponent(SLUG); }});
    });
  }

  // ------------------------------------------------------------------ a channel: permissions
  //
  // One row per group (the groups' order, the default ones last), and for read and for post a control of three:
  // deny (✕), inherit (/), allow (✓). Each press is saved at once, "saved" said at the row's end; a refusal shows
  // there and the control stays as it was. The owner group takes no override: its row says it always can. Each
  // person's own agent group has a row only once it has an override or was added here ("加入群組…"). Under the table,
  // the outcome: who may read the channel now, people and agents.

  var permBox = document.getElementById("channel-perms");
  var STATES = [["deny", "✕"], ["inherit", "/"], ["allow", "✓"]];
  var overrides = null, readers = null, shownGroups = {}, savedKey = null;

  function tri(group, perm, value, can, out) {
    var seg = make("div", "tri");
    seg.setAttribute("role", "radiogroup");
    seg.setAttribute("aria-label", t("chan.perm.label", {group: rules.labelOf(group), perm: t("chan.perm." + perm)}));
    STATES.forEach(function (st) {
      var b = A.button("tri-btn tri-" + st[0], st[1]);
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", String(st[0] === value));
      b.setAttribute("aria-label", t("chan.perm." + st[0]));
      b.title = t("chan.perm." + st[0]);
      b.tabIndex = st[0] === value ? 0 : -1;
      b.disabled = !can;
      b.dataset.key = "tri:" + group + ":" + perm + ":" + st[0];
      b.addEventListener("click", async function () {
        if (b.getAttribute("aria-checked") === "true") return;
        var body = {}, one = {};
        one[perm] = st[0];
        body[group] = one;
        out.textContent = "";
        var r = await A.request(API + "channels/" + encodeURIComponent(CHANNEL) + "/permissions", null, {overrides: body});
        if (!r.ok) { out.textContent = A.refusal("chan.perms", r.data, {channel: CHANNEL}); return; }
        overrides = r.data.overrides;
        readers = r.data.readers || readers;
        shownGroups[group] = true;
        savedKey = group;
        drawPerms();
        var again = permBox.querySelector('[data-key="' + b.dataset.key.replace(/["\\]/g, "\\$&") + '"]');
        if (again) again.focus();
      });
      seg.appendChild(b);
    });
    seg.addEventListener("keydown", function (ev) {
      var all = Array.prototype.slice.call(seg.children), i = all.indexOf(document.activeElement);
      var j = ev.key === "ArrowRight" ? i + 1 : ev.key === "ArrowLeft" ? i - 1 : -9;
      if (i < 0 || j === -9 || j < 0 || j >= all.length) return;
      ev.preventDefault();
      all[j].click();
    });
    return seg;
  }

  function overridden(name) {
    var o = overrides[name];
    return !!o && (o.read !== "inherit" || o.post !== "inherit");
  }
  // The rows shown: every group but a person's own agent group, which only once it has an override or was added.
  function rowGroups() {
    return view.groups.filter(function (g) { return g.kind !== "ownership" || overridden(g.name) || shownGroups[g.name]; });
  }

  function addGroupControl(can) {
    var hidden = view.groups.filter(function (g) { return rowGroups().indexOf(g) < 0; });
    if (!can || !hidden.length) return null;
    var b = A.button("btn quiet chan-perm-add", t("chan.perm.add"));
    b.dataset.key = "chan-perm-add";
    b.setAttribute("aria-haspopup", "menu");
    b.setAttribute("aria-expanded", "false");
    b.addEventListener("click", function () {
      A.menu({label: t("chan.perm.add"), anchor: b}, hidden.map(function (g) {
        return {label: rules.label(g), run: function () {
          shownGroups[g.name] = true;
          drawPerms();
          var first = permBox.querySelector('[data-key="tri:' + g.name.replace(/["\\]/g, "\\$&") + ':read:inherit"]');
          if (first) first.focus();
        }};
      }), b);
    });
    return b;
  }

  // Who may read the channel now, as the server says after the last change.
  function outcome() {
    var p = make("p", "chan-readers");
    p.setAttribute("aria-live", "polite");
    if (!readers) return p;
    var names = readers.people.concat(readers.agents);
    p.appendChild(make("span", "chan-readers-head", t("chan.perm.readers", {n: names.length})));
    readers.people.forEach(function (n) { p.appendChild(make("span", "chan-reader", n)); });
    readers.agents.forEach(function (n) { p.appendChild(make("span", "chan-reader mono", n)); });
    if (!names.length) p.appendChild(make("span", "dim", t("chan.perm.nobody")));
    return p;
  }

  function drawPerms() {
    if (!permBox || !overrides) return;
    var can = permBox.dataset.can === "1";
    A.keepFocus(permBox, function () {
      permBox.textContent = "";
      if (!can) permBox.appendChild(make("p", "dim", t("chan.perm.readonly")));
      var wrap = make("div", "table-wrap"), tbl = make("table", "chan-perm-table"), head = make("thead"), hr = make("tr");
      [t("chan.perm.group"), t("chan.perm.read"), t("chan.perm.post"), ""].forEach(function (h) { hr.appendChild(make("th", "", h)); });
      head.appendChild(hr);
      var tb = make("tbody");
      rowGroups().forEach(function (g) {
        var o = overrides[g.name] || {read: "inherit", post: "inherit"}, tr = make("tr"), out = make("span", "out");
        out.setAttribute("aria-live", "polite");
        var name = make("td", "chan-perm-group");
        name.appendChild(make("span", g.kind === "custom" ? "mono" : "", rules.label(g)));
        if (rules.isDefault(g)) name.appendChild(make("span", "default-mark", t("mem.default")));
        var note = make("td", "chan-perm-out");
        note.appendChild(out);
        if (g.kind === "default" && g.name === "owner") {
          var always = make("td", "chan-perm-always", t("chan.perm.always"));
          always.colSpan = 2;
          tr.className = "chan-perm-owner";
          tr.append(name, always, note);
        } else {
          var read = make("td", "chan-perm-cell"), post = make("td", "chan-perm-cell");
          read.dataset.label = t("chan.perm.read");
          post.dataset.label = t("chan.perm.post");
          read.appendChild(tri(g.name, "read", o.read, can, out));
          post.appendChild(tri(g.name, "post", o.post, can, out));
          tr.append(name, read, post, note);
        }
        if (savedKey === g.name) A.saved(out);
        tb.appendChild(tr);
      });
      savedKey = null;
      tbl.append(head, tb);
      wrap.appendChild(tbl);
      permBox.appendChild(wrap);
      var add = addGroupControl(can);
      if (add) permBox.appendChild(add);
      permBox.appendChild(outcome());
    });
  }
  async function loadPerms() {
    if (!permBox) return;
    var r = await A.request(API + "channels/" + encodeURIComponent(CHANNEL) + "/permissions");
    if (!r.ok) { permBox.textContent = A.refusal("chan.perms", r.data, {channel: CHANNEL}); return; }
    overrides = r.data.overrides;
    readers = r.data.readers || null;
    drawPerms();
  }

  // ------------------------------------------------------------------ the project: invitations
  //
  // A new invitation shows its link once, with its copy control (the server keeps only its digest); the unused ones
  // are listed under it: who it is for, made when, until when, and "revoke" (two steps, in place). A link made here
  // keeps its copy control on its row while the page is open; after a reload it is listed without it (to share it
  // again, revoke it and make a new one).

  var inviteForm = document.getElementById("invite-form"), invitesBox = document.getElementById("invites-list");
  var madeLinks = {};                                // invitation id -> its link, made on this page
  var LANG = document.documentElement.lang || undefined;

  function when(iso) {
    var d = new Date(iso);
    return isNaN(d.getTime()) ? "" : d.toLocaleString(LANG, {month: "short", day: "numeric", hour: "2-digit",
                                                            minute: "2-digit", hour12: false});
  }

  async function loadInvites() {
    if (!invitesBox) return;
    var r = await A.request(API + "invites");
    if (!r.ok) { invitesBox.textContent = A.refusal("admin.invites", r.data); return; }
    A.keepFocus(invitesBox, function () { drawInvites(r.data.invites || []); });
  }

  function drawInvites(list) {
    invitesBox.textContent = "";
    if (!list.length) { invitesBox.appendChild(make("p", "dim", t("admin.no_unused"))); return; }
    var ul = make("ul", "ag-list");
    list.forEach(function (inv) {
      var li = make("li", "ag-item invite-item"), line = make("div", "ag-line");
      line.appendChild(make("span", "ag-name" + (inv.github_login ? " mono" : ""),
                            inv.github_login ? inv.github_login : t("admin.for_anyone")));
      li.appendChild(line);
      li.appendChild(make("div", "ag-meta", t("admin.invite_times", {created: when(inv.created), expires: when(inv.expires)})));
      var acts = make("div", "invite-acts");
      if (madeLinks[inv.id]) {
        var copy = A.button("btn", t("invite.copy"), async function () {
          var ok = await A.copy(madeLinks[inv.id]);
          copy.textContent = t(ok ? "invite.copied" : "invite.copy_failed");
          setTimeout(function () { copy.textContent = t("invite.copy"); }, 2000);
        });
        copy.dataset.key = "icopy:" + inv.id;
        acts.appendChild(copy);
      }
      var out = make("span", "out");
      out.setAttribute("aria-live", "polite");
      var revoke = A.button("btn", t("admin.revoke"));
      revoke.dataset.key = "irevoke:" + inv.id;
      revoke.addEventListener("click", async function () {
        if (!A.twoStep(revoke, t("admin.confirm_revoke"))) return;
        var r = await A.request(API + "invites/" + encodeURIComponent(inv.id) + "/revoke", null, {});
        if (!r.ok) { out.textContent = A.refusal("admin.revoke", r.data); return; }
        delete madeLinks[inv.id];
        loadInvites();
      });
      acts.append(out, revoke);
      li.appendChild(acts);
      ul.appendChild(li);
    });
    invitesBox.appendChild(ul);
  }

  if (inviteForm) {
    inviteForm.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var out = inviteForm.querySelector(".out"), made = document.getElementById("invite-made");
      var go = inviteForm.querySelector("button:not([type=button])"), input = inviteForm.elements.github_login;
      var login = input.value.trim();
      out.textContent = "";
      go.disabled = true;
      try {
        var r = await A.request(API + "invites", null, login ? {github_login: login} : {});
        if (!r.ok) {
          if (r.data.error === "invalid_login") A.fieldError(input, A.refusal("admin.invite", r.data));
          else out.textContent = A.refusal("admin.invite", r.data);
          return;
        }
        if (r.data.id) madeLinks[r.data.id] = r.data.url;
        made.textContent = "";
        made.append(make("p", "", t("admin.invite_made")), A.copyLine(r.data.url));
        made.hidden = false;
        input.value = "";
        loadInvites();
      } finally {
        go.disabled = false;
      }
    });
  }

  // ------------------------------------------------------------------ a channel: notifications

  Array.prototype.forEach.call(layer.querySelectorAll("input[data-mute]"), function (box) {
    var out = box.parentElement.querySelector(".out");
    box.addEventListener("change", async function () {
      var body = {muted: box.checked};
      if (box.dataset.mute) body.agent = box.dataset.mute;
      out.textContent = "";
      var r = await A.request(API + "channels/" + encodeURIComponent(CHANNEL) + "/mute", null, body);
      if (!r.ok) { box.checked = !box.checked; out.textContent = A.refusal("chan.mute", r.data); return; }
      A.saved(out);
    });
  });

  // ------------------------------------------------------------------ start

  show(sectionFromPath(), false);
  markMember();
  loadPerms();
  loadInvites();
  if (SCOPE === "project") setInterval(function () { load(false); }, EVERY_MS);
})();
