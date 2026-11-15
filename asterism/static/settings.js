// The settings layer (#settings-layer): project settings or one channel's, one section at a time.
// - The list of sections (#settings-nav) switches the section in place; each has its own address, so a reload or a
//   shared link shows the same one, and the browser's back goes back through them. Below 900 px the bare address
//   is the list itself, and a section has a way back to it.
// - The close control (#settings-close) and Escape go back to the page the layer was opened from (project.js keeps
//   it), else to chat.
// - Project: members (one table of people and agents: groups as chips, x to take one away and + to give one, removal
//   from the project), groups (a list with a filter and "new group"; a chosen group, ?g= in the address, in tabs:
//   name, permissions, members; a person's agents: members and that person's switches), invitations (app.js).
// - Channel: notifications (my mute and my agents'), pins (the list; files pinned and pins removed by who may pin).
// The data is /api/members (embedded at first, then read again every 15 s while nobody is mid-act) and
// /api/channels. Only what the reader may do is offered (Asterism.people's rules); a refusal shows the server's
// sentence where the act was. Taking out of a group confirms in place; removing a group or a member floats.
"use strict";
(function () {
  var A = window.Asterism, layer = document.getElementById("settings-layer");
  if (!A || !layer || !A.people) return;
  var t = A.t, make = A.make, P = A.people;
  var SLUG = layer.dataset.slug, SCOPE = layer.dataset.scope, BASE = layer.dataset.base, CHANNEL = layer.dataset.channel;
  var API = "/" + encodeURIComponent(SLUG) + "/api/";
  var CATALOGUE = A.parseJSON(layer.dataset.catalogue, []), MANAGEMENT = A.parseJSON(layer.dataset.management, []);
  var SWITCHES = ["others_mention", "others_channel", "others_assign", "others_regroup"];
  var EVERY_MS = 15000;
  var view = A.parseJSON(layer.dataset.view, null), last = JSON.stringify(view), rules = P.rules(view);
  var nav = document.getElementById("settings-nav");
  var sections = Array.prototype.slice.call(layer.querySelectorAll(".set-sec"));
  var names = sections.map(function (s) { return s.dataset.section; });
  var narrow = window.matchMedia("(max-width: 899.98px)");
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
      if (a.dataset.section === cur && (section || !narrow.matches)) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    layer.classList.toggle("at-list", !section);
    var title = layer.querySelector("#set-h-" + cur);
    document.title = (title ? title.textContent + " · " : "") + document.title.split(" · ").slice(-1)[0];
    draw(cur);
    if (focus && title) {
      title.tabIndex = -1;
      title.focus({preventScroll: true});
    }
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
    go(a.dataset.section);
  });
  document.getElementById("settings-back").addEventListener("click", function (ev) {
    ev.preventDefault();
    go("");
    var first = nav.querySelector("a[data-section]");
    if (first) first.focus();
  });
  window.addEventListener("popstate", function () { show(sectionFromPath(), false); });
  if (narrow.addEventListener) narrow.addEventListener("change", function () { show(sectionFromPath(), false); });

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
    return A.isArmed(layer) || !!document.querySelector("dialog.gone[open]") || A.popup.isOpen() ||
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
    else if (section === "pins") loadPins();
  }

  function outOf(box) {
    var out = make("div", "out");
    out.setAttribute("aria-live", "polite");
    box.appendChild(out);
    return out;
  }

  // After an act: its refusal where it was, else the data again.
  function done(out) {
    return function (r) {
      if (r && !r.ok) { out.textContent = A.refusal("mem.refused", r.data); return; }
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
    if (!who.groups.length) chips.appendChild(make("span", "dim small", t("mem.no_groups")));
    who.groups.forEach(function (n) { chips.appendChild(P.chip(rules, who, isAgent, n, after)); });
    var plus = P.plus(function () { return rules; }, who, isAgent, after);
    if (plus) chips.appendChild(plus);
    groups.appendChild(chips);
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

  function groupMenu(g, b) {
    var items = [{label: t("mem.open_group"), run: function () { goGroup(g.name, true); }}];
    if (g.kind === "custom" && rules.mine("manage_groups") && rules.holdsAll(g.permissions)) {
      items.push({separator: true}, {label: t("mem.remove_group"), run: function () { removeGroup(g, b); }});
    }
    A.menu({label: t("mem.group_acts", {name: rules.label(g)}), anchor: b}, items, b);
  }

  function entry(g, compact) {
    var li = make("li", "grow"), a = make("a", "place");
    a.href = BASE + "/groups?g=" + encodeURIComponent(g.name);
    a.dataset.key = "g:" + g.name;
    a.dataset.group = g.name;
    if (chosen() === g.name) a.setAttribute("aria-current", "true");
    var n = rules.count(g.name), c = make("span", "count", t("mem.count", {n: n}));
    c.setAttribute("aria-hidden", "true");
    a.append(make("span", "place-name" + (g.kind === "custom" ? " mono" : ""), rules.label(g)), c,
             make("span", "vh", t("mem.count_label", {n: n})));
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
    var q = (groupFilter.value || "").trim().toLowerCase(), any = false;
    list.textContent = "";
    if (compact) {
      var back = make("a", "place groups-back", t("mem.back_list"));
      back.href = BASE + "/groups";
      back.dataset.key = "g-back";
      list.appendChild(back);
    }
    [["mem.custom", "custom"], ["mem.default", "default"], ["mem.ownership", "ownership"]].forEach(function (s) {
      var gs = view.groups.filter(function (g) {
        return g.kind === s[1] && (matches(rules.label(g), q) || matches(g.name, q));
      });
      if (!gs.length) return;
      any = true;
      var sec = make("section", "groups-sec"), ul = make("ul", "side-list");
      sec.appendChild(make("h3", "", t(s[0])));
      gs.forEach(function (g) { ul.appendChild(entry(g, compact)); });
      sec.appendChild(ul);
      list.appendChild(sec);
    });
    if (!any) list.appendChild(make("p", "dim", t("mem.no_match")));
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

  function nameTab(g) {
    var box = make("div", "gd-tab");
    var facts = make("dl", "set-facts");
    facts.append(make("dt", "", t("set.name")), make("dd", "set-name mono", g.name));
    if (rules.label(g) !== g.name) facts.append(make("dt", "", t("mem.list_label")), make("dd", "", rules.label(g)));
    facts.append(make("dt", "", t("mem.members")), make("dd", "", t("mem.count_label", {n: rules.count(g.name)})));
    box.appendChild(facts);
    box.appendChild(make("p", "dim", g.kind === "ownership" ? t("mem.kind.ownership", {owner: g.owner})
                                                            : t("mem.kind." + g.kind, {name: g.name})));
    box.appendChild(make("p", "dim", g.kind === "custom" ? t("mem.rename_none") : t("mem.name_fixed")));
    if (g.kind === "custom" && rules.mine("manage_groups") && rules.holdsAll(g.permissions)) {
      var sec = make("section", "gd-sec");
      sec.appendChild(make("h3", "", t("mem.remove_group")));
      sec.appendChild(make("p", "", t("mem.remove_group_hint", {name: g.name})));
      var b = A.button("btn", t("mem.remove_group"));
      b.dataset.key = "grm:" + g.name;
      b.addEventListener("click", function () { removeGroup(g, b); });
      sec.appendChild(b);
      box.appendChild(sec);
    }
    return box;
  }

  function removeGroup(g, opener) {
    A.gone({title: t("gone.group.title", {name: g.name}), text: t("gone.group.text", {name: g.name}), name: g.name,
            button: t("gone.group.button"), opener: opener, after: groupFilter,
            run: function () { return A.request(API + "groups/" + encodeURIComponent(g.name) + "/remove", null, {}); },
            done: async function () {
              window.history.replaceState(null, "", BASE + "/groups");
              await load(true);
            }});
  }

  function permRow(g, p, editable) {
    var row = make("div", "perm-row"), box = make("input"), id = "perm-" + p;
    box.type = "checkbox";
    box.id = id;
    box.checked = g.permissions.indexOf(p) >= 0;
    box.disabled = !editable || !rules.mine(p);
    box.dataset.key = "perm:" + g.name + ":" + p;
    var text = make("label", "perm-text");
    text.htmlFor = id;
    text.append(make("span", "perm-name", t("perm." + p)), make("span", "perm-hint", t("perm_hint." + p)));
    var out = make("span", "out");
    out.setAttribute("aria-live", "polite");
    if (editable && !rules.mine(p)) {
      row.classList.add("unheld");
      text.appendChild(make("span", "perm-hint", t("mem.perm_unheld")));
    }
    text.appendChild(out);
    row.append(box, text);
    row.dataset.text = (t("perm." + p) + " " + t("perm_hint." + p) + " " + p).toLowerCase();
    box.addEventListener("change", async function () {
      var want = CATALOGUE.filter(function (x) { return x === p ? box.checked : g.permissions.indexOf(x) >= 0; });
      out.textContent = "";
      var r = await A.request(API + "groups/" + encodeURIComponent(g.name), null, {permissions: want});
      if (!r.ok) {
        box.checked = !box.checked;
        out.textContent = A.refusal("mem.refused", r.data);
        return;
      }
      g.permissions = r.data.permissions;      // the page's copy follows; the next reading redraws the rest
      out.textContent = t("mem.saved");
    });
    return row;
  }

  function permsTab(g) {
    var box = make("div", "gd-tab"), editable = g.kind === "custom" && rules.mine("manage_groups") && rules.holdsAll(g.permissions);
    box.appendChild(make("p", "dim", t("mem.perms_hint")));
    var why = g.kind === "default" ? "mem.perms_fixed" : !rules.mine("manage_groups") ? "mem.perms_readonly" :
              !rules.holdsAll(g.permissions) ? "mem.perms_not_mine" : null;
    if (why) box.appendChild(make("p", "dim", t(why)));
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

  function membersTab(g) {
    var box = make("div", "gd-tab"), m = rules.inGroup(g.name);
    var ul = make("ul", "mlist");
    var filter = filterField("mfilter:" + g.name, t("mem.filter_members"), function () {
      var q = filter.value.trim().toLowerCase();
      Array.prototype.forEach.call(ul.children, function (li) { if (li.dataset.name) li.hidden = !matches(li.dataset.name, q); });
    });
    var top = make("div", "gd-add");
    top.appendChild(filter);
    if (g.kind !== "ownership") {
      var cands = view.people.filter(function (x) { return x.groups.indexOf(g.name) < 0 && rules.mayAdd(x, false, g); })
        .map(function (x) { return [x, false]; })
        .concat(view.agents.filter(function (x) { return x.groups.indexOf(g.name) < 0 && rules.mayAdd(x, true, g); })
          .map(function (x) { return [x, true]; }));
      if (cands.length) {
        var sel = make("select"), addOut = make("span", "out");
        addOut.setAttribute("aria-live", "polite");
        sel.dataset.key = "gadd:" + g.name;
        sel.setAttribute("aria-label", t("mem.add_label", {group: rules.label(g)}));
        cands.forEach(function (c) {
          var o = make("option", "", c[1] ? c[0].name + " (" + t("mem.agent_of", {owner: c[0].owner}) + ")" : c[0].name);
          o.value = c[0].name;
          sel.appendChild(o);
        });
        var add = A.button("btn", t("mem.add"), async function () {
          done(addOut)(await P.regroup(sel.value, [g.name], []));
        });
        add.dataset.key = "gadd-go:" + g.name;
        top.append(sel, add, addOut);
      }
    }
    box.appendChild(top);
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

  function switchesTab(g) {
    var box = make("div", "gd-tab"), self = g.owner === view.me.name;
    box.appendChild(make("p", "dim", self ? t("mem.switches_own") : t("mem.switches_other", {owner: g.owner})));
    var rows = make("div", "perm-list");
    SWITCHES.forEach(function (k) {
      var row = make("div", "perm-row"), input = make("input"), id = "sw-" + k;
      input.type = "checkbox";
      input.id = id;
      input.checked = !!(g.switches && g.switches[k]);
      input.disabled = !self;
      input.dataset.key = "sw:" + k;
      var text = make("label", "perm-text"), out = make("span", "out");
      text.htmlFor = id;
      out.setAttribute("aria-live", "polite");
      text.append(make("span", "perm-name", self ? t("switch." + k) : t("mem.sw." + k, {owner: g.owner})), out);
      row.append(input, text);
      input.addEventListener("change", async function () {
        var body = {};
        body[k] = input.checked;
        out.textContent = "";
        var r = await A.request(API + "my/switches", null, body);
        if (!r.ok) { input.checked = !input.checked; out.textContent = A.refusal("mem.refused", r.data); return; }
        g.switches = g.switches || {};
        g.switches[k] = input.checked;
        out.textContent = t("mem.saved");
      });
      rows.appendChild(row);
    });
    box.appendChild(rows);
    return box;
  }

  function drawGroup(g) {
    var head = make("header", "gd-head"), h = make("h2", "gd-title", rules.label(g));
    h.id = "gd-title";
    if (rules.label(g) !== g.name) h.appendChild(make("small", "", g.name));
    head.appendChild(h);
    detail.appendChild(head);
    var kinds = g.kind === "ownership" ? [["members", membersTab], ["switches", switchesTab]]
                                       : [["name", nameTab], ["perms", permsTab], ["members", membersTab]];
    var want = tabs[g.name] && kinds.some(function (k) { return k[0] === tabs[g.name]; }) ? tabs[g.name] : kinds[0][0];
    var bar = make("div", "tabs");
    bar.setAttribute("role", "tablist");
    bar.setAttribute("aria-label", t("mem.tabs", {name: rules.label(g)}));
    var pane = make("div", "tab-pane");
    pane.setAttribute("role", "tabpanel");
    pane.id = "gd-pane";
    kinds.forEach(function (k) {
      var b = A.button("tab-btn-plain", t("mem.tab." + k[0]));
      b.setAttribute("role", "tab");
      b.id = "gd-tab-" + k[0];
      b.dataset.key = "tab:" + k[0];
      b.setAttribute("aria-controls", pane.id);
      b.setAttribute("aria-selected", String(k[0] === want));
      b.tabIndex = k[0] === want ? 0 : -1;
      b.addEventListener("click", function () {
        tabs[g.name] = k[0];
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
    pane.setAttribute("aria-labelledby", "gd-tab-" + want);
    pane.appendChild(kinds.filter(function (k) { return k[0] === want; })[0][1](g));
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

  var form = document.getElementById("group-create"), opener = document.getElementById("group-create-open");
  function reveal(show) {
    form.hidden = !show;
    opener.setAttribute("aria-expanded", String(show));
    groupsRoot.classList.toggle("creating", show);
    if (show) form.elements.name.focus(); else opener.focus();
  }
  if (form && opener) {
    opener.addEventListener("click", function () { reveal(form.hidden); });
    form.querySelector("[data-dismiss]").addEventListener("click", function () { reveal(false); });
    form.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); reveal(false); }
    });
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var out = form.querySelector("[data-out]"), name = form.elements.name.value.trim();
      var perms = Array.prototype.filter.call(form.querySelectorAll('input[name="perm"]'), function (b) { return b.checked; })
        .map(function (b) { return b.value; });
      var r = await A.request(API + "groups", null, {name: name, permissions: perms});
      if (!r.ok) { out.textContent = A.refusal("mem.refused", r.data); return; }
      out.textContent = "";
      form.reset();
      form.hidden = true;
      groupsRoot.classList.remove("creating");
      opener.setAttribute("aria-expanded", "false");
      window.history.pushState(null, "", BASE + "/groups?g=" + encodeURIComponent(r.data.name));
      await load(true);
      detail.focus();
    });
  }

  // ------------------------------------------------------------------ a channel: notifications and pins

  Array.prototype.forEach.call(layer.querySelectorAll("input[data-mute]"), function (box) {
    var out = box.parentElement.querySelector(".out");
    box.addEventListener("change", async function () {
      var body = {muted: box.checked};
      if (box.dataset.mute) body.agent = box.dataset.mute;
      out.textContent = "";
      var r = await A.request(API + "channels/" + encodeURIComponent(CHANNEL) + "/mute", null, body);
      if (!r.ok) { box.checked = !box.checked; out.textContent = A.refusal("mem.refused", r.data); return; }
      out.textContent = t("msg.saved");
    });
  });

  var pinsBox = document.getElementById("set-pins"), CAN_PIN = !!(pinsBox && pinsBox.dataset.canPin);

  function pinText(p) { return p.kind === "file" ? p.path : "#" + p.message + " " + (p.from || "") + ": " + p.text; }

  async function loadPins() {
    if (!pinsBox || busy()) return;
    var r = await A.request(API + "channels");
    if (!r.ok) return;
    var ch = (r.data.channels || []).filter(function (c) { return c.name === CHANNEL; })[0];
    drawPins(ch ? ch.pins || [] : []);
  }

  function drawPins(list) {
    A.keepFocus(pinsBox, function () {
      pinsBox.textContent = "";
      var ul = make("ul", "mlist");
      list.forEach(function (p) {
        var li = make("li", "mrow"), text = make("div", "mtext"), link;
        if (p.kind === "file") {
          link = make("a", "mname mono", p.path);
          link.href = A.fileHref(SLUG, p.path);
          link.title = t("pin.file_hint");
        } else {
          link = make("a", "mname", pinText(p));
          link.href = "/" + encodeURIComponent(SLUG) + "#" + encodeURIComponent("#" + CHANNEL);
        }
        text.append(link, make("span", "msub", t("pin.by", {name: p.by})));
        li.appendChild(text);
        var out;
        if (CAN_PIN) {
          var x = A.button("btn", t("pin.remove"), async function () {
            var res = await A.request(API + "channels/" + encodeURIComponent(CHANNEL) + "/pins/" + p.id + "/remove", null, {});
            if (!res.ok) { out.textContent = A.refusal("pin.refused", res.data); return; }
            loadPins();
          });
          x.dataset.key = "unpin:" + p.id;
          x.setAttribute("aria-label", t("pin.remove_label", {what: p.kind === "file" ? p.path : "#" + p.message}));
          var acts = make("div", "macts");
          acts.appendChild(x);
          li.appendChild(acts);
        }
        out = outOf(li);
        ul.appendChild(li);
      });
      if (!list.length) ul.appendChild(make("li", "mempty", t("pin.none")));
      pinsBox.appendChild(ul);
      if (!CAN_PIN) return;
      var form = make("form", "pin-add"), path = make("input"), out = make("span", "out");
      path.name = "path";
      path.maxLength = 300;
      path.required = true;
      path.placeholder = t("pin.path");
      path.dataset.key = "pin-path";
      path.setAttribute("aria-label", t("pin.path"));
      form.append(path, make("button", "btn", t("pin.add_file")), out);
      form.addEventListener("submit", async function (ev) {
        ev.preventDefault();
        if (!path.value.trim()) return;
        var res = await A.request(API + "channels/" + encodeURIComponent(CHANNEL) + "/pins", null, {path: path.value});
        if (!res.ok) { out.textContent = A.refusal("pin.refused", res.data); return; }
        path.value = "";
        loadPins();
      });
      pinsBox.appendChild(form);
    });
  }

  // ------------------------------------------------------------------ start

  show(sectionFromPath(), false);
  markMember();
  if (SCOPE === "project") setInterval(function () { load(false); }, EVERY_MS);
})();
