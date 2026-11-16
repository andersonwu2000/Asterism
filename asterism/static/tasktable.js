// The work page's tasks tab (#task-table): the task table as a bounty board (m1f7_contract.md section 2, m1t_contract.md
// section 6), from /api/tasks (tasks.js) and the members (frame.js). A task is an agent's or nobody's; whoever needs
// something posts it, an idle agent of its group takes it and keeps its body current; an agent holds one task at a time.
// - Three sections in this order: 待接 (nobody holds it; oldest first), 進行中 (an agent holds it), 已完成 (done; kept
//   for a while by the server, newest first). A card: its number, its title, its body (rendered as Markdown with
//   mathematics, folded after a few lines, "顯示全部" opens it in place), its menu (T.menuItems, shared with chat), and
//   quiet lines: who posted it and when, "open to {group}" as a quiet tag (the group decides which agents may take it),
//   how often its body is to be updated, when it last was ("更新於 3 小時前") and the overdue mark; a task held also has
//   the holder (presence, name, model), since when it holds it, and the lock's quiet tag; a done one, who finished it
//   and when.
// - Scopes: all; waiting; in progress; done; posted by me; my agents' (an agent of mine holds it); assigned by me (I
//   locked it); one group. Any of them with ?agent={name} (a chip over the list, removable) and ?new=1 (the form open).
// - Posting ("發布任務"): a form in place at the top of the list: the title first, then the body (optional), "open to"
//   (default AI, all agents; in a group's scope that group), optionally an agent of that group to give it to directly
//   (with the lock, checked), and optionally how often its body is to be updated. Giving it to an agent that holds a
//   task says in place what happens: an unlocked one goes back to 待接; a locked one must first be released by who
//   locked it. Escape closes it and the focus goes back to what opened it; Ctrl/Cmd+Enter posts.
"use strict";
(function () {
  var A = window.Asterism, G = A && A.workPage, view = document.getElementById("task-table");
  var T = A && A.tasks, S = A && A.side;
  if (!G || !view || !T || !S) return;
  var t = A.t, make = A.make;
  var ME = G.me;
  var opened = {};               // task id -> its whole body shown
  var adding = null;             // {form, opener} while a new task is being written

  var action = document.getElementById("task-new");

  function groups() { return (T.data && T.data.groups) || []; }
  function group(name) { return groups().filter(function (g) { return g.name === name; })[0] || null; }
  function all() { return T.all().sort(function (a, b) { return a.id - b.id; }); }
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
    unheld: function (x) { return !x.done && !x.responsible; },
    held: function (x) { return !x.done && !!x.responsible; },
    done: function (x) { return !!x.done; },
    posted: function (x) { return x.posted_by === ME; },
    mine: function (x) { return !x.done && x.responsible_kind === "agent" && owner(x.responsible) === ME; },
    assigned: function (x) { return !x.done && x.assigned_by === ME; }
  };
  var SHOW_WORDS = {unheld: "tt.waiting", held: "tt.held", done: "tt.done", posted: "tt.posted_mine", mine: "tt.mine",
                    assigned: "tt.assigned"};
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

  // ------------------------------------------------------------------ a card

  // The body, rendered as Markdown with mathematics (render.js), folded after a few lines; "顯示全部" opens it in place.
  function bodyBox(task) {
    var box = make("div", "tt-bodytext");
    if (!task.body) return box;
    var text = A.renderText ? A.renderText(task.body) : make("div", "text", task.body);
    text.classList.add("tt-md");
    if (!opened[task.id]) text.classList.add("folded");
    box.appendChild(text);
    requestAnimationFrame(function () {
      if (opened[task.id] || !text.isConnected || text.scrollHeight <= text.clientHeight + 1) return;
      var more = A.button("btn tt-more", t("tt.more"), function () {
        opened[task.id] = true;
        text.classList.remove("folded");
        more.remove();
      });
      more.dataset.key = "more:" + task.id;
      box.appendChild(more);
    });
    return box;
  }

  function card(task) {
    var li = make("li", "tt-task" + (task.responsible && !task.done ? " held" : "") + (task.assigned_by ? " locked" : "") +
                       (task.done ? " done" : "") + (task.overdue ? " overdue" : ""));
    li.dataset.task = String(task.id);
    li.appendChild(make("span", "tt-id mono", String(task.id)));
    var main = make("div", "tt-body");
    li.appendChild(main);
    if (T.editing === task.id && T.canEdit && !task.done) {
      main.appendChild(T.editForm(task, li));
    } else {
      main.append(make("h3", "tt-title", task.title), bodyBox(task));
      if (T.mayAct(task) || T.mayDone(task) || (task.done && T.canEdit)) {
        var open = function (where, opener) { T.openMenu(task, li, where, opener); };
        var acts = G.acts(t("task.task_acts", {text: task.title}), "tacts:" + task.id, open);
        li.appendChild(acts);
        G.menuOn(li, acts, open);
      }
      // Who posted it and when; the group it is open to; how often its body is to be updated, and when it last was.
      var by = task.posted_by ? t("tt.posted_by", {name: task.posted_by}) : t("tt.posted");
      var meta = G.facts("tt-meta", task.posted_at ? [by, T.timeEl(task.posted_at)] : task.posted_by ? [by] : []);
      var g = group(task.group), tag = make("span", "tag tt-open", t("tt.open_to", {group: g ? T.groupLabel(g) : task.group}));
      tag.title = t("tt.open_to_hint");
      meta.appendChild(tag);
      li.appendChild(meta);
      if (!task.done) {
        var every = task.update_every_h ? t("tt.every", {n: task.update_every_h}) : "";
        var upd = T.updated(task);
        if (every || upd) li.appendChild(G.facts("tt-meta tt-track", [every, upd]));
      }
      if (task.done) li.appendChild(finished(task));
      else if (task.responsible) li.appendChild(holder(task));
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
    if (task.taken_at) since.append(t("tt.taken") + " · ", T.timeEl(task.taken_at));
    if (!online) since.append((task.taken_at ? " · " : "") + t("presence.offline"));
    if (since.childNodes.length) line.appendChild(since);
    if (task.assigned_by) {
      var lock = make("span", "tag", t("tt.assigned_by", {name: task.assigned_by}));
      lock.title = t("task.locked", {name: task.assigned_by});
      line.appendChild(lock);
    }
    return line;
  }

  // A done task: who held it when it was finished, and when.
  function finished(task) {
    var parts = [];
    if (task.responsible) parts.push(make("span", "tt-agent mono", task.responsible));
    if (task.done_at) parts.push(T.timeEl(task.done_at, t("tt.done_at", {time: G.time(task.done_at)})));
    return G.facts("tt-holder tt-finished", parts);
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

  // What giving the task to `name` does to the task it holds: nothing ("" when it holds none); an unlocked one goes
  // back to 待接; a locked one must first be released by who locked it.
  function heldWarning(name) {
    var x = name ? T.heldBy(name) : null;
    if (!x) return "";
    if (x.assigned_by) return t("tt.holds_locked", {agent: name, title: x.title, person: x.assigned_by});
    return t("tt.holds", {agent: name, title: x.title});
  }

  // The form, made once per opening and kept across redraws, so what is typed survives them. `start`: the group it is
  // open to at first; `preset`: an agent to give it to.
  function newForm(start, preset) {
    var form = make("form", "ag-form tadd-form"), out = make("span", "out");
    form.noValidate = true;
    out.setAttribute("aria-live", "polite");
    var gs = audiences();
    if (!gs.some(function (g) { return g.name === start; })) start = (gs[0] && gs[0].name) || "";
    var title = make("input");
    title.maxLength = 200;
    title.dataset.key = "tadd-title";
    title.placeholder = t("tt.title_hint");
    var titleErr = make("small", "field-error");
    titleErr.id = "tadd-title-error";
    titleErr.setAttribute("aria-live", "polite");
    title.setAttribute("aria-describedby", titleErr.id);
    title.addEventListener("input", function () { if (title.value.trim()) titleErr.textContent = ""; });
    var text = make("textarea");
    text.rows = 4;
    text.maxLength = 10000;
    text.dataset.key = "tadd-body";
    text.placeholder = t("tt.body_hint");
    var pick = A.dropdown({label: t("tt.open_to_label"), value: start, options: gs.map(function (g) {
      return {value: g.name, label: g.name === "ai" ? t("tt.all_agents") : T.groupLabel(g)};
    }), onChange: function () { who.setOptions(directOptions(pick.value)); who.set(""); sync(); }});
    var who = A.dropdown({label: t("tt.direct"), value: "", options: directOptions(start), onChange: sync});
    if (preset && directOptions(start).some(function (o) { return o.value === preset && !o.disabled; })) who.set(preset);
    var warn = make("small", "ag-hint tt-warn");
    warn.id = "tadd-held";
    warn.setAttribute("aria-live", "polite");
    var lock = make("input");
    lock.type = "checkbox";
    lock.checked = true;
    lock.id = "tadd-lock";
    var lockRow = make("div", "ag-check"), lockText = make("label", "perm-text");
    lockText.htmlFor = lock.id;
    lockText.append(make("span", "perm-name", t("task.lock")), make("span", "perm-hint", t("task.lock_hint")));
    lockRow.append(lock, lockText);
    // "要求每 __ 小時更新內容": a number of hours (1 to 168), or empty for never.
    var every = make("input");
    every.type = "number";
    every.min = "1";
    every.max = "168";
    every.step = "1";
    every.inputMode = "numeric";
    every.dataset.key = "tadd-every";
    every.className = "tt-every-n";
    every.setAttribute("aria-label", t("tt.every_label"));
    var everyErr = make("small", "field-error");
    everyErr.id = "tadd-every-error";
    everyErr.setAttribute("aria-live", "polite");
    every.setAttribute("aria-describedby", everyErr.id);
    every.addEventListener("input", function () { everyErr.textContent = ""; });
    var everyRow = make("label", "ag-field tt-every");
    var words = t("tt.every_form").split("{n}");
    var line = make("span", "tt-every-line");
    line.append(words[0] || "", every, words[1] || "");
    everyRow.append(line, make("small", "ag-hint", t("tt.every_hint")), everyErr);
    function sync() {
      lockRow.hidden = !who.value;
      warn.textContent = heldWarning(who.value);
    }
    sync();
    var titleField = field(t("task.title_label"), title);
    titleField.appendChild(titleErr);
    var two = make("div", "ag-two");
    var whoField = field(t("tt.direct"), who.el);
    whoField.appendChild(warn);
    two.append(field(t("tt.open_to_label"), pick.el, t("tt.open_to_hint")), whoField);
    var row = make("div", "row form-acts");
    row.append(out, A.button("btn", t("task.cancel"), function () { close(true); }), make("button", "btn primary", t("tt.post")));
    form.append(titleField, field(t("task.body_label"), text), two, lockRow, everyRow, row);
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      if (!title.value.trim()) { titleErr.textContent = t("tt.title_needed"); title.focus(); return; }
      var hours = every.value.trim();
      if (hours && !(/^\d+$/.test(hours) && +hours >= 1 && +hours <= 168)) {
        everyErr.textContent = t("tt.every_bad");
        every.focus();
        return;
      }
      if (!pick.value) return;
      var body = {group: pick.value, title: title.value};
      if (text.value.trim()) body.body = text.value;
      if (hours) body.update_every_h = +hours;
      if (who.value) { body.responsible = who.value; body.locked = lock.checked; }
      if (await T.call("tasks", body, out, {group: pick.value})) close(false);
    });
    form.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); close(true); }
      else if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); form.requestSubmit(); }
    });
    form._sync = sync;
    setTimeout(function () { title.focus(); }, 0);
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
    if (adding) {
      if (adding.form._sync) adding.form._sync();      // what the chosen agent holds may have changed
      view.appendChild(adding.form);
    }
    var list = all().filter(function (x) { return shown(x, sc); });
    var waiting = list.filter(SHOWS.unheld), held = list.filter(SHOWS.held);
    var done = list.filter(SHOWS.done).sort(function (a, b) { return (b.done_at || "").localeCompare(a.done_at || ""); });
    if (!sc.show || sc.show === "unheld" || waiting.length) {
      view.appendChild(section("waiting", t("tt.waiting"), waiting, t("tt.none_waiting")));
    }
    if (!sc.show || sc.show === "held" || held.length) view.appendChild(section("held", t("tt.held"), held, t("tt.none_held")));
    if (!sc.show || sc.show === "done" || done.length) view.appendChild(section("done", t("tt.done"), done, t("tt.none_done")));
  }

  function count(f) { return all().filter(f).length; }

  G.register({
    scopes: function () {
      var sc = scope(), out = [{heading: t("tt.tasks")}];
      [["", "tt.all"], ["unheld", "tt.waiting"], ["held", "tt.held"], ["done", "tt.done"], ["posted", "tt.posted_mine"],
       ["mine", "tt.mine"], ["assigned", "tt.assigned"]].forEach(function (x) {
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
      var name = sc.group ? T.groupLabel(group(sc.group)) : sc.show ? t(SHOW_WORDS[sc.show]) : t("tt.scope_all");
      return t("ag.count", {name: name, n: n});
    },
    draw: draw,
    busy: function () { return T.editing !== null; }
  });
  // The table changes on the reader's own acts (tasks.js does not read it again while one is being written).
  T.onChange(function () { G.redraw(false, true); });
  S.onMembers(function () { G.redraw(false); });
})();
