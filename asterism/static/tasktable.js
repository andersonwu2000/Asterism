// The work page's tasks tab (#task-table): the task table as a bounty board (m1f7_contract.md section 2), from
// /api/tasks (tasks.js) and the members (frame.js). A task is an agent's or nobody's; whoever needs something posts it,
// an idle agent of its group takes it.
// - Two sections in this order: 待接 (nobody holds it; oldest first) and 進行中 (an agent holds it). A card: its
//   number, its whole text (four lines, then "顯示全部"), its menu (T.menuItems, shared with chat), and one quiet line:
//   who posted it and when, and "open to {group}" as a quiet tag (the group decides which agents may take it); a task
//   held also has the holder (presence, name, model), since when it holds it, and the lock's quiet tag.
// - Scopes: all; waiting (nobody holds it); posted by me; my agents' (an agent of mine holds it); assigned by me (I
//   locked it); one group. Any of them with ?agent={name} (a chip over the list, removable) and ?new=1 (the form open).
// - Posting ("發布任務"): a form in place at the top of the list: the text first, then "open to" (default AI, all
//   agents; in a group's scope that group), then, optionally, an agent of that group to give it to directly (with the
//   lock, checked). Escape closes it and the focus goes back to what opened it; Ctrl/Cmd+Enter posts.
"use strict";
(function () {
  var A = window.Asterism, G = A && A.workPage, view = document.getElementById("task-table");
  var T = A && A.tasks, S = A && A.side;
  if (!G || !view || !T || !S) return;
  var t = A.t, make = A.make;
  var ME = G.me, LANG = document.documentElement.lang || undefined;
  var opened = {};               // task id -> its whole text shown
  var adding = null;             // {form, opener} while a new task is being written
  var action = document.getElementById("task-new");

  function groups() { return (T.data && T.data.groups) || []; }
  function group(name) { return groups().filter(function (g) { return g.name === name; })[0] || null; }
  function all() {
    var out = [];
    groups().forEach(function (g) { g.tasks.forEach(function (x) { out.push(x); }); });
    return out.sort(function (a, b) { return a.id - b.id; });
  }
  function owner(name) { var w = S.directory[name]; return w && w.kind === "agent" ? w.owner : null; }
  function agentOf(name) {
    return ((S.members && S.members.agents) || []).filter(function (a) { return a.name === name; })[0] || null;
  }
  // The groups in the order a task is posted to: AI (every agent) first, then the custom groups in their order, then
  // each person's agent group; owner and human hold no agents, so no task is posted to them.
  function audiences() {
    var gs = groups(), rank = {ai: 0, custom: 1, ownership: 2};
    return gs.filter(function (g) { return g.kind !== "default" || g.name === "ai"; }).map(function (g, i) {
      return {g: g, i: i, r: g.kind === "default" ? rank.ai : rank[g.kind] === undefined ? 1 : rank[g.kind]};
    }).sort(function (a, b) { return a.r - b.r || a.i - b.i; }).map(function (x) { return x.g; });
  }

  // ------------------------------------------------------------------ the scope

  var SHOWS = {
    unheld: function (x) { return !x.responsible; },
    posted: function (x) { return x.posted_by === ME; },
    mine: function (x) { return x.responsible_kind === "agent" && owner(x.responsible) === ME; },
    assigned: function (x) { return x.assigned_by === ME; }
  };
  function scope() {
    var p = G.params(), show = p.get("show"), grp = p.get("group"), agent = p.get("agent");
    var out = {show: SHOWS[show] ? show : "", group: "", agent: ""};
    if (!out.show && grp && group(grp)) out.group = grp;
    if (agent && S.directory[agent] && S.directory[agent].kind === "agent") out.agent = agent;
    out.adding = p.get("new") === "1";
    return out;
  }
  function query(show, grp, agent) {
    var p = new URLSearchParams();
    if (show) p.set("show", show);
    if (grp) p.set("group", grp);
    if (agent) p.set("agent", agent);
    return p.toString();
  }
  function shown(x, sc) {
    if (sc.show && !SHOWS[sc.show](x)) return false;
    if (sc.group && x.group !== sc.group) return false;
    return !sc.agent || x.responsible === sc.agent;
  }

  // ------------------------------------------------------------------ times

  // How long ago, in the reader's words ("3 小時前"); a date beyond a week.
  var ago = (function () {
    var rtf = window.Intl && Intl.RelativeTimeFormat ? new Intl.RelativeTimeFormat(LANG, {numeric: "auto"}) : null;
    return function (iso) {
      var d = new Date(iso);
      if (!iso || isNaN(d.getTime())) return "";
      var s = (d.getTime() - Date.now()) / 1000, a = Math.abs(s);
      if (!rtf || a >= 7 * 86400) return G.time(iso);
      if (a < 60) return rtf.format(0, "second");
      if (a < 3600) return rtf.format(Math.round(s / 60), "minute");
      if (a < 86400) return rtf.format(Math.round(s / 3600), "hour");
      return rtf.format(Math.round(s / 86400), "day");
    };
  })();
  function time(iso) {
    var el = make("time", "", ago(iso));
    el.dateTime = iso;
    el.title = new Date(iso).toLocaleString(LANG);
    return el;
  }

  // ------------------------------------------------------------------ a card

  function card(task) {
    var li = make("li", "tt-task" + (task.responsible ? " held" : "") + (task.assigned_by ? " locked" : ""));
    li.dataset.task = String(task.id);
    li.appendChild(make("span", "tt-id mono", String(task.id)));
    if (T.editing === task.id && T.canEdit) {
      var body = make("div", "tt-body");
      body.appendChild(T.editForm(task, li));
      li.appendChild(body);
    } else {
      li.appendChild(G.clamp(task.text, task.id, opened));
      if (T.mayAct(task)) {
        var open = function (where, opener) { T.openMenu(task, li, where, opener); };
        var acts = G.acts(t("task.task_acts", {text: task.text}), "tacts:" + task.id, open);
        li.appendChild(acts);
        G.menuOn(li, acts, open);
      }
      // Who posted it and when; the group it is open to.
      var by = task.posted_by ? t("tt.posted_by", {name: task.posted_by}) : t("tt.posted");
      var meta = G.facts("tt-meta", task.posted_at ? [by, time(task.posted_at)] : task.posted_by ? [by] : []);
      var g = group(task.group), tag = make("span", "tag tt-open", t("tt.open_to", {group: g ? T.groupLabel(g) : task.group}));
      tag.title = t("tt.open_to_hint");
      meta.appendChild(tag);
      li.appendChild(meta);
      if (task.responsible) li.appendChild(holder(task));
    }
    var out = make("div", "out");
    out.setAttribute("aria-live", "polite");
    li.appendChild(out);
    return li;
  }

  // The agent holding a task: presence, name, model, since when; the lock, a quiet tag saying who locked it.
  function holder(task) {
    var line = make("div", "tt-holder"), a = agentOf(task.responsible), who = owner(task.responsible);
    var online = a ? !!a.online : !!task.online;
    line.appendChild(S.presence({kind: "agent", online: online}));
    var name = make("span", "tt-agent mono", task.responsible);
    name.title = who === ME ? t("nav.my_agent") : t("mem.agent_of", {owner: who || "?"});
    line.appendChild(name);
    var model = a ? A.modelTag(a.model) : null;
    if (model) line.appendChild(model);
    var since = make("span", "tt-since");
    if (task.taken_at) since.append(t("tt.taken") + " · ", time(task.taken_at));
    if (!online) since.append((task.taken_at ? " · " : "") + t("presence.offline"));
    if (since.childNodes.length) line.appendChild(since);
    if (task.assigned_by) {
      var lock = make("span", "tag", t("tt.assigned_by", {name: task.assigned_by}));
      lock.title = t("task.locked", {name: task.assigned_by});
      line.appendChild(lock);
    }
    return line;
  }

  // ------------------------------------------------------------------ posting a task

  function agentsOf(gname) {
    var g = group(gname);
    return g ? g.members.filter(function (m) { return m.kind === "agent"; }) : [];
  }
  function directOptions(gname) {
    return [{value: "", label: t("tt.wait_taken")}].concat(agentsOf(gname).map(function (m) {
      var who = owner(m.name), closed = T.closedBy(m.name);
      var label = who === ME ? t("tt.mine_agent", {name: m.name}) : t("tt.their_agent", {name: m.name, owner: who || "?"});
      if (closed === "closed") label += t("tt.closed", {owner: who});
      return {value: m.name, label: label, disabled: !!closed};
    }));
  }

  function field(label, control, hint) {
    var f = make("label", "ag-field");
    f.append(make("span", "", label), control);
    if (hint) f.appendChild(make("small", "ag-hint", hint));
    return f;
  }

  // The form, made once per opening and kept across redraws, so what is typed survives them. `start`: the group it is
  // open to at first; `preset`: an agent to give it to.
  function newForm(start, preset) {
    var form = make("form", "ag-form tadd-form"), out = make("span", "out");
    form.noValidate = true;
    out.setAttribute("aria-live", "polite");
    var gs = audiences();
    if (!gs.some(function (g) { return g.name === start; })) start = (gs[0] && gs[0].name) || "";
    var text = make("textarea");
    text.rows = 3;
    text.maxLength = 2000;
    text.dataset.key = "tadd-text";
    text.placeholder = t("tt.text_hint");
    var textErr = make("small", "field-error");
    textErr.id = "tadd-text-error";
    textErr.setAttribute("aria-live", "polite");
    text.setAttribute("aria-describedby", textErr.id);
    text.addEventListener("input", function () { if (text.value.trim()) textErr.textContent = ""; });
    var pick = A.dropdown({label: t("tt.open_to_label"), value: start, options: gs.map(function (g) {
      return {value: g.name, label: g.name === "ai" ? t("tt.all_agents") : T.groupLabel(g)};
    }), onChange: function () { who.setOptions(directOptions(pick.value)); who.set(""); sync(); }});
    var who = A.dropdown({label: t("tt.direct"), value: "", options: directOptions(start), onChange: sync});
    if (preset && directOptions(start).some(function (o) { return o.value === preset && !o.disabled; })) who.set(preset);
    var lock = make("input");
    lock.type = "checkbox";
    lock.checked = true;
    lock.id = "tadd-lock";
    var lockRow = make("div", "ag-check"), lockText = make("label", "perm-text");
    lockText.htmlFor = lock.id;
    lockText.append(make("span", "perm-name", t("task.lock")), make("span", "perm-hint", t("task.lock_hint")));
    lockRow.append(lock, lockText);
    function sync() { lockRow.hidden = !who.value; }
    sync();
    var textField = field(t("task.text_label"), text);
    textField.appendChild(textErr);
    var two = make("div", "ag-two");
    two.append(field(t("tt.open_to_label"), pick.el, t("tt.open_to_hint")), field(t("tt.direct"), who.el));
    var row = make("div", "row form-acts");
    row.append(out, A.button("btn", t("task.cancel"), function () { close(true); }), make("button", "btn primary", t("tt.post")));
    form.append(textField, two, lockRow, row);
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      if (!text.value.trim()) { textErr.textContent = t("tt.text_needed"); text.focus(); return; }
      if (!pick.value) return;
      var body = {group: pick.value, text: text.value};
      if (who.value) { body.responsible = who.value; body.locked = lock.checked; }
      if (await T.call("tasks", body, out, {group: pick.value})) close(false);
    });
    form.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); close(true); }
      else if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); form.requestSubmit(); }
    });
    setTimeout(function () { text.focus(); }, 0);
    return form;
  }

  function startGroup(sc) {
    if (sc.group) return sc.group;
    var a = sc.agent && agentOf(sc.agent);
    return a && a.groups && a.groups.indexOf("ai") < 0 ? a.groups[0] : "ai";
  }

  function open(opener) {
    var sc = scope();
    adding = {opener: opener || null, form: newForm(startGroup(sc), sc.agent)};
    if (!sc.adding) {
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
  }
  if (action) action.addEventListener("click", function () { if (adding) close(true); else open(action); });

  // ------------------------------------------------------------------ drawing

  function section(key, title, list, empty) {
    var sec = make("section", "tt-group tt-" + key), head = make("div", "tt-ghead");
    head.append(make("h2", "tt-gname", title), make("span", "tt-n", list.length ? t("tt.count", {n: list.length}) : ""));
    sec.appendChild(head);
    if (!list.length) { sec.appendChild(make("p", "tt-empty", empty)); return sec; }
    var ul = make("ul", "tt-list");
    list.forEach(function (x) { ul.appendChild(card(x)); });
    sec.appendChild(ul);
    return sec;
  }

  function draw() {
    var sc = scope();
    view.textContent = "";
    if (!T.data) return;
    if (sc.adding && !adding && T.canEdit) adding = {opener: action, form: newForm(startGroup(sc), sc.agent)};
    if (!sc.adding && adding) adding = null;
    if (action) action.setAttribute("aria-expanded", String(!!adding));
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
    if (adding) view.appendChild(adding.form);
    var list = all().filter(function (x) { return shown(x, sc); });
    var waiting = list.filter(function (x) { return !x.responsible; });
    var held = list.filter(function (x) { return !!x.responsible; });
    view.appendChild(section("waiting", t("tt.waiting"), waiting, t("tt.none_waiting")));
    if (sc.show !== "unheld") view.appendChild(section("held", t("tt.held"), held, t("tt.none_held")));
  }

  function count(f) { return all().filter(f).length; }

  G.register({
    scopes: function () {
      var sc = scope(), out = [{heading: t("tt.tasks")}];
      [["", "tt.all"], ["unheld", "tt.waiting"], ["posted", "tt.posted_mine"], ["mine", "tt.mine"],
       ["assigned", "tt.assigned"]].forEach(function (x) {
        out.push({query: query(x[0], "", sc.agent), label: t(x[1]),
                  count: count(function (y) { return shown(y, {show: x[0], agent: sc.agent}); })});
      });
      out.push({heading: t("tt.groups")});
      audiences().forEach(function (g) {
        out.push({query: query("", g.name, sc.agent), label: T.groupLabel(g), mono: g.kind === "custom",
                  count: count(function (y) { return shown(y, {group: g.name, agent: sc.agent}); })});
      });
      return out;
    },
    current: function () { var sc = scope(); return query(sc.show, sc.group, sc.agent); },
    title: function () {
      var sc = scope(), n = count(function (y) { return shown(y, sc); });
      var name = sc.group ? T.groupLabel(group(sc.group)) : sc.show ? t(sc.show === "unheld" ? "tt.waiting"
               : sc.show === "posted" ? "tt.posted_mine" : "tt." + sc.show) : t("tt.scope_all");
      return t("ag.count", {name: name, n: n});
    },
    draw: draw,
    busy: function () { return T.editing !== null; }
  });
  // The table changes on the reader's own acts (tasks.js does not read it again while one is being written).
  T.onChange(function () { G.redraw(false, true); });
  S.onMembers(function () { G.redraw(false); });
})();
