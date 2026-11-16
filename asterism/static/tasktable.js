// The work page's tasks tab (#task-table; m1f5_agent_page_design.md section 3): the task table by group, from
// /api/tasks (tasks.js) and the members (frame.js). A task is an agent's or nobody's.
// - Scopes: all; my agents' (an agent of mine is responsible); assigned by me (I locked it); nobody's; one group. Any
//   of them with ?agent={name} (a chip over the list, removable) and ?new=1 (the form for a new task open).
// - One section per group with a task in the scope, in the groups' order (a group chosen in the column even when
//   empty): its name, its count and "+ new task"; in it one sub-head per agent that holds a task there (in the
//   members' order), then "nobody". A task row: its number, its whole text (four lines, then "顯示全部"), the quiet tag
//   of who locked it, and its menu (T.menuItems, shared with chat), only where the page cannot tell the answer is no.
// - A new task: a form in place (at the top of the list, or of a section with its group fixed): group, responsible
//   (nobody first; the group's agents, another person's disabled when they keep it closed), lock (only with an agent,
//   checked), text. Escape closes it and the focus goes back to what opened it; Ctrl/Cmd+Enter adds.
"use strict";
(function () {
  var A = window.Asterism, G = A && A.workPage, view = document.getElementById("task-table");
  var T = A && A.tasks, S = A && A.side;
  if (!G || !view || !T || !S) return;
  var t = A.t, make = A.make;
  var ME = G.me;
  var opened = {};               // task id -> its whole text shown
  var adding = null;             // {group: fixed group or "", form, opener} while a new task is being written
  var action = document.getElementById("task-new");

  function groups() { return (T.data && T.data.groups) || []; }
  function all() {
    var out = [];
    groups().forEach(function (g) { g.tasks.forEach(function (x) { out.push(x); }); });
    return out;
  }
  function owner(name) { var w = S.directory[name]; return w && w.kind === "agent" ? w.owner : null; }

  // ------------------------------------------------------------------ the scope

  var SHOWS = {
    mine: function (x) { return x.responsible_kind === "agent" && owner(x.responsible) === ME; },
    assigned: function (x) { return x.assigned_by === ME; },
    unheld: function (x) { return !x.responsible; }
  };
  function scope() {
    var p = G.params(), show = p.get("show"), group = p.get("group"), agent = p.get("agent");
    var out = {show: SHOWS[show] ? show : "", group: "", agent: ""};
    if (!out.show && group && groups().some(function (g) { return g.name === group; })) out.group = group;
    if (agent && S.directory[agent] && S.directory[agent].kind === "agent") out.agent = agent;
    out.adding = p.get("new") === "1";
    return out;
  }
  function query(show, group, agent) {
    var p = new URLSearchParams();
    if (show) p.set("show", show);
    if (group) p.set("group", group);
    if (agent) p.set("agent", agent);
    return p.toString();
  }
  function shown(x, sc) {
    if (sc.show && !SHOWS[sc.show](x)) return false;
    return !sc.agent || x.responsible === sc.agent;
  }

  // ------------------------------------------------------------------ a task

  function row(task) {
    var li = make("li", "tt-task" + (task.assigned_by ? " locked" : ""));
    li.dataset.task = String(task.id);
    li.appendChild(make("span", "tt-id mono", String(task.id)));
    if (T.editing === task.id && T.canEdit) {
      var body = make("div", "tt-body");
      body.appendChild(T.editForm(task, li));
      li.appendChild(body);
    } else {
      li.appendChild(G.clamp(task.text, task.id, opened));
      if (task.assigned_by) {
        var tag = make("span", "tag", t("tt.assigned_by", {name: task.assigned_by}));
        tag.title = t("task.locked", {name: task.assigned_by});
        li.appendChild(tag);
      }
      if (T.mayAct(task)) {
        var open = function (where, opener) { T.openMenu(task, li, where, opener); };
        var acts = G.acts(t("task.task_acts", {text: task.text}), "tacts:" + task.id, open);
        li.appendChild(acts);
        G.menuOn(li, acts, open);
      }
    }
    var out = make("div", "out");
    out.setAttribute("aria-live", "polite");
    li.appendChild(out);
    return li;
  }

  function agentHead(name, online) {
    var head = make("div", "tt-ahead"), who = owner(name);
    head.append(S.presence({kind: "agent", online: online}), make("span", "mono", name),
                make("span", "", (who === ME ? t("nav.my_agent") : t("mem.agent_of", {owner: who || "?"})) +
                                 (online ? "" : " " + t("tt.offline"))));
    return head;
  }

  // ------------------------------------------------------------------ a new task

  function agentsOf(gname) {
    var g = groups().filter(function (x) { return x.name === gname; })[0];
    return g ? g.members.filter(function (m) { return m.kind === "agent"; }) : [];
  }
  function responsibleOptions(gname) {
    return [{value: "", label: t("tt.nobody")}].concat(agentsOf(gname).map(function (m) {
      var who = owner(m.name), closed = T.closedBy(m.name);
      var label = who === ME ? t("tt.mine_agent", {name: m.name}) : t("tt.their_agent", {name: m.name, owner: who || "?"});
      if (closed === "closed") label += t("tt.closed", {owner: who});
      return {value: m.name, label: label, disabled: !!closed};
    }));
  }

  function field(label, control) {
    var f = make("label", "ag-field");
    f.append(make("span", "", label), control);
    return f;
  }

  // The form, made once per opening and kept across redraws, so what is typed survives them.
  function newForm(fixed, preset) {
    var form = make("form", "ag-form tadd-form"), out = make("span", "out");
    out.setAttribute("aria-live", "polite");
    var gs = groups(), start = fixed || (gs[0] && gs[0].name) || "";
    var pick = A.dropdown({label: t("task.group_for"), value: start, options: gs.map(function (g) {
      return {value: g.name, label: T.groupLabel(g)};
    }), onChange: function () { who.setOptions(responsibleOptions(pick.value)); who.set(""); sync(); }});
    var who = A.dropdown({label: t("tt.responsible"), value: "", options: responsibleOptions(start), onChange: sync});
    if (preset && responsibleOptions(start).some(function (o) { return o.value === preset && !o.disabled; })) who.set(preset);
    var lock = make("input");
    lock.type = "checkbox";
    lock.checked = true;
    lock.id = "tadd-lock-" + (fixed || "top");
    var lockRow = make("div", "ag-check"), lockText = make("label", "perm-text");
    lockText.htmlFor = lock.id;
    lockText.append(make("span", "perm-name", t("task.lock")), make("span", "perm-hint", t("task.lock_hint")));
    lockRow.append(lock, lockText);
    var text = make("textarea");
    text.rows = 3;
    text.maxLength = 2000;
    text.required = true;
    text.dataset.key = "tadd-text";
    function sync() { lockRow.hidden = !who.value; }
    sync();
    var two = make("div", "ag-two");
    if (!fixed) two.appendChild(field(t("task.group"), pick.el));
    two.appendChild(field(t("tt.responsible"), who.el));
    var row = make("div", "row");
    row.append(make("button", "btn primary", t("task.add")), A.button("btn", t("task.cancel"), function () { close(true); }), out);
    form.append(two, lockRow, field(t("task.text_label"), text), row);
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      if (!text.value.trim() || !pick.value) return;
      var body = {group: pick.value, text: text.value};
      if (who.value) { body.responsible = who.value; body.locked = lock.checked; }
      if (await T.call("tasks", body, out)) close(false);
    });
    form.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); close(true); }
      else if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); form.requestSubmit(); }
    });
    setTimeout(function () { text.focus(); }, 0);
    return form;
  }

  function open(fixed, opener) {
    var sc = scope();
    adding = {group: fixed || "", opener: opener || null, form: newForm(fixed, sc.agent)};
    if (!fixed && !sc.adding) {
      var q = query(sc.show, sc.group, sc.agent);
      G.go(q + (q ? "&" : "") + "new=1", true);
      return;
    }
    G.redraw(true);
  }
  function close(refocus) {
    var was = adding;
    adding = null;
    var sc = scope();
    if (sc.adding) G.go(query(sc.show, sc.group, sc.agent), true); else G.redraw(true);
    if (refocus && was && was.opener && was.opener.isConnected) was.opener.focus();
    else if (refocus && was && was.opener && was.opener.dataset.key) {
      var again = view.querySelector('[data-key="' + was.opener.dataset.key + '"]');
      if (again) again.focus();
    }
  }
  if (action) action.addEventListener("click", function () { open("", action); });

  // ------------------------------------------------------------------ drawing

  function draw() {
    var sc = scope();
    view.textContent = "";
    if (!T.data) return;
    if (sc.adding && !adding && T.canEdit) adding = {group: "", opener: action, form: newForm("", sc.agent)};
    if (!sc.adding && adding && !adding.group) adding = null;
    if (action) action.setAttribute("aria-expanded", String(!!(adding && !adding.group)));
    if (sc.agent) {
      var chip = make("div", "ag-chip");
      chip.appendChild(make("span", "", t("tt.chip", {name: sc.agent})));
      var x = A.button("chip-x");
      x.appendChild(make("span", "cross")).setAttribute("aria-hidden", "true");
      x.setAttribute("aria-label", t("tt.chip_remove", {name: sc.agent}));
      x.title = t("tt.chip_remove", {name: sc.agent});
      x.dataset.key = "chip-x";
      x.addEventListener("click", function () { G.go(query(sc.show, sc.group, "")); });
      chip.appendChild(x);
      view.appendChild(chip);
    }
    if (adding && !adding.group) view.appendChild(adding.form);
    var any = false;
    groups().forEach(function (g) {
      if (sc.group && g.name !== sc.group) return;
      var list = g.tasks.filter(function (x) { return shown(x, sc); });
      var here = adding && adding.group === g.name;
      if (!list.length && !here && sc.group !== g.name) return;
      any = true;
      var sec = make("section", "tt-group"), head = make("div", "tt-ghead");
      head.append(make("span", "tt-gname" + (g.kind === "custom" ? " mono" : ""), T.groupLabel(g)),
                  make("span", "tt-n", t("tt.count", {n: list.length})), make("span", "spacer"));
      if (T.canEdit && !here) {
        var plus = A.button("btn quiet", "+ " + t("task.add"));
        plus.setAttribute("aria-label", t("tt.add_in", {group: T.groupLabel(g)}));
        plus.dataset.key = "add:" + g.name;
        plus.addEventListener("click", function () { open(g.name, plus); });
        head.appendChild(plus);
      }
      sec.appendChild(head);
      if (here) sec.appendChild(adding.form);
      if (!list.length) sec.appendChild(make("p", "tt-empty", t("tt.empty_group")));
      // The agents holding a task here, in the members' order (then any other), and nobody's last.
      var order = g.members.filter(function (m) { return m.kind === "agent"; }).map(function (m) { return m.name; });
      list.forEach(function (x) { if (x.responsible && order.indexOf(x.responsible) < 0) order.push(x.responsible); });
      order.forEach(function (name) {
        var mine = list.filter(function (x) { return x.responsible === name; });
        if (!mine.length) return;
        var m = g.members.filter(function (y) { return y.name === name; })[0];
        sec.appendChild(agentHead(name, m ? !!m.online : !!mine[0].online));
        var ul = make("ul", "tt-list");
        mine.forEach(function (x) { ul.appendChild(row(x)); });
        sec.appendChild(ul);
      });
      var none = list.filter(function (x) { return !x.responsible; });
      if (none.length) {
        var h = make("div", "tt-ahead");
        h.appendChild(make("span", "", t("tt.nobody")));
        sec.appendChild(h);
        var ul = make("ul", "tt-list");
        none.forEach(function (x) { ul.appendChild(row(x)); });
        sec.appendChild(ul);
      }
      view.appendChild(sec);
    });
    if (!any) view.appendChild(make("p", "ag-empty", t("tt.empty")));
  }

  function count(f) { return all().filter(f).length; }

  G.register({
    scopes: function () {
      var sc = scope(), out = [{heading: t("tt.tasks")}];
      [["", "tt.all"], ["mine", "tt.mine"], ["assigned", "tt.assigned"], ["unheld", "tt.unheld"]].forEach(function (x) {
        out.push({query: query(x[0], "", sc.agent), label: t(x[1]),
                  count: count(function (y) { return shown(y, {show: x[0], agent: sc.agent}); })});
      });
      out.push({heading: t("tt.groups")});
      groups().forEach(function (g) {
        out.push({query: query("", g.name, sc.agent), label: T.groupLabel(g), mono: g.kind === "custom",
                  count: g.tasks.filter(function (y) { return shown(y, {show: "", agent: sc.agent}); }).length});
      });
      return out;
    },
    current: function () { var sc = scope(); return query(sc.show, sc.group, sc.agent); },
    title: function () {
      var sc = scope(), n = count(function (y) { return shown(y, sc) && (!sc.group || y.group === sc.group); });
      var name = sc.group ? T.groupLabel(groups().filter(function (g) { return g.name === sc.group; })[0])
               : sc.show ? t("tt." + sc.show) : t("tt.scope_all");
      return t("ag.count", {name: name, n: n});
    },
    draw: draw,
    busy: function () { return T.editing !== null; }
  });
  // The table changes on the reader's own acts (tasks.js does not read it again while one is being written).
  T.onChange(function () { G.redraw(false, true); });
  S.onMembers(function () { G.redraw(false); });
})();
