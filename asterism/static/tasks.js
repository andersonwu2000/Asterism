// Tasks (Asterism.tasks), on the messages pages and the work page. The task table is read from /api/tasks every few
// seconds. A task has a title and a body; it is given to an agent or to nobody, never to a person, and an agent holds
// one task that is not done at a time (m1t_contract.md). In chat it is shown in the member list (people.js), under each
// agent as its status: its task's title on one line, cut with an ellipsis, and when its body was last updated ("更新於
// 3 小時前"), with the overdue mark (a shape and a word) when an update is due; a long title folds, opened in place. A
// locked task carries the quiet tag. The work page's tasks tab (tasktable.js) shows the same table as a bounty board,
// with the same acts and the same menu (T.menuItems), offered to a person who may edit tasks (data-can-edit-tasks on
// #chat or #work-page; the server decides each one): add a task (to an agent, or to nobody in a chosen group, AI unless
// chosen otherwise), rewrite its title and body in place, hand it to another agent of its group, lock or unlock it,
// release it, mark it done (its poster too), remove it (in two steps). A done task is only removed. Each task has its
// own small menu (its "..." control, right click, the context-menu key or Shift+F10), offered only where the page
// cannot already tell the answer is no; a refusal shows the page's own sentence for its code at the task. A refresh
// waits while the reader is writing a task or has an act armed.
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("chat") || document.getElementById("work-page");
  if (!A || !root) return;
  var t = A.t, make = A.make;
  var SLUG = root.dataset.slug, ME = root.dataset.me, API = "/" + encodeURIComponent(SLUG) + "/api/";
  var EVERY_MS = 4000, LONG = 40, LANG = document.documentElement.lang || undefined;
  var T = A.tasks = {canEdit: !!root.dataset.canEditTasks, data: null, last: "", listeners: [],
                     open: {},              // fold key -> opened by the reader
                     adding: null,          // {key, member, groups} while a new task is being written
                     editing: null};        // the id of the task being rewritten
  T.onChange = function (fn) { T.listeners.push(fn); };
  function changed() { T.listeners.forEach(function (fn) { fn(T.data); }); }

  // ------------------------------------------------------------------ the data

  function all() {
    var seen = {}, out = [];
    ((T.data && T.data.groups) || []).forEach(function (g) {
      g.tasks.forEach(function (x) { if (!seen[x.id]) { seen[x.id] = true; out.push(x); } });
    });
    return out;
  }
  T.all = all;
  // The task `name` holds (one at most; a done task holds nobody), and the open ones (nobody holds them, not done).
  T.of = function (name) { return all().filter(function (x) { return !x.done && x.responsible === name; }); };
  T.unheld = function () { return all().filter(function (x) { return !x.done && !x.responsible; }); };
  function group(name) {
    return ((T.data && T.data.groups) || []).filter(function (g) { return g.name === name; })[0] || null;
  }
  // The groups a new task for `member` can be in: those it is in (all of them for a task of nobody).
  T.groupsFor = function (member) {
    return ((T.data && T.data.groups) || []).filter(function (g) {
      return !member || g.members.some(function (m) { return m.name === member; });
    });
  };
  T.groupLabel = function (g) {
    var OWN = "-agents";
    if (g.kind === "default" && A.MSG["group." + g.name]) return t("group." + g.name);
    if (g.kind === "ownership" && g.name.slice(-OWN.length) === OWN) return t("group.ownership", {owner: g.name.slice(0, -OWN.length)});
    return g.name;
  };

  // The reader is writing a task, rewriting one or has an act armed: a redraw would throw that away.
  T.busy = function () {
    var box = document.getElementById("member-body") || document.getElementById("task-table"), a = document.activeElement;
    if (!box) return false;
    return T.editing !== null || T.adding !== null || A.isArmed(box) ||
           !!(a && box.contains(a) && /^(INPUT|TEXTAREA)$/.test(a.tagName) && a.value);
  };

  // ------------------------------------------------------------------ what the page can tell before the server
  //
  // From the members (frame.js): whose an agent is and whether its person lets others give it tasks. Where nothing
  // is known yet, the act is offered and the server decides.

  function ownerOf(name) {
    var who = A.side && A.side.directory[name];
    return who && who.kind === "agent" ? who.owner : null;
  }
  // Another person's agent: may tasks be given to it by the reader? Null when the members are not read yet.
  T.closedBy = function (name) {
    var owner = ownerOf(name), v = A.side && A.side.members;
    if (!owner || owner === ME || !v) return null;
    var own = (v.groups || []).filter(function (g) { return g.kind === "ownership" && g.owner === owner; })[0];
    if (!(own && own.switches && own.switches.others_assign)) return "closed";
    return A.can("assign_tasks") ? null : "permission";
  };
  // May the reader give a task to this agent (and lock it)?
  T.mayGive = function (name) { return !T.closedBy(name); };
  // May the reader act on this task at all? Nobody's: who may edit tasks. An agent's: its person; a locked one only
  // who locked it besides; another's otherwise only where its person lets them.
  T.mayAct = function (task) {
    if (!T.canEdit) return false;
    if (!task.responsible || task.responsible_kind !== "agent") return true;
    var owner = ownerOf(task.responsible);
    if (!owner || owner === ME) return true;
    if (task.assigned_by) return task.assigned_by === ME;
    return T.mayGive(task.responsible);
  };
  // May the reader mark it done: whoever may change it, and its poster.
  T.mayDone = function (task) { return T.canEdit && !task.done && (task.posted_by === ME || T.mayAct(task)); };
  // The task an agent holds besides `except` (an id), for the form's warning in place.
  T.heldBy = function (name, except) {
    return all().filter(function (x) { return !x.done && x.responsible === name && x.id !== except; })[0] || null;
  };

  // ------------------------------------------------------------------ times

  // How long ago, in the reader's words ("3 小時前"); a date beyond a week.
  var rtf = window.Intl && Intl.RelativeTimeFormat ? new Intl.RelativeTimeFormat(LANG, {numeric: "auto"}) : null;
  T.ago = function (iso) {
    var d = new Date(iso);
    if (!iso || isNaN(d.getTime())) return "";
    var s = (d.getTime() - Date.now()) / 1000, a = Math.abs(s);
    if (!rtf || a >= 7 * 86400) return d.toLocaleDateString(LANG, {month: "long", day: "numeric"});
    if (a < 60) return rtf.format(0, "second");
    if (a < 3600) return rtf.format(Math.round(s / 60), "minute");
    if (a < 86400) return rtf.format(Math.round(s / 3600), "hour");
    return rtf.format(Math.round(s / 86400), "day");
  };
  T.timeEl = function (iso, text) {
    var el = make("time", "", text === undefined ? T.ago(iso) : text);
    el.dateTime = iso;
    el.title = new Date(iso).toLocaleString(LANG);
    return el;
  };
  // The overdue mark: a shape (app.css: .overdue) and a word, never a colour alone.
  T.overdueMark = function () {
    var m = make("span", "tag overdue", t("tt.overdue"));
    m.title = t("tt.overdue_hint");
    return m;
  };
  // "更新於 3 小時前" (when its body last changed) and the overdue mark; null when there is neither.
  T.updated = function (task, cls) {
    var box = make("span", "t-updated" + (cls ? " " + cls : ""));
    if (task.body_at) box.append(t("tt.updated") + " ", T.timeEl(task.body_at));
    if (task.overdue) box.appendChild(T.overdueMark());
    return box.childNodes.length ? box : null;
  };

  async function load(force) {
    if (!force && T.busy()) return;
    var r = await A.request(API + "tasks");
    if (!r.ok) return;
    var raw = JSON.stringify(r.data);
    if (raw === T.last && !force) return;
    if (!force && T.busy()) return;
    T.last = raw;
    T.data = r.data;
    changed();
  }
  T.load = load;

  // An act on the table: its refusal at `out` (the catalogue's sentence for its code, filled with `vars`), else the
  // table again.
  async function call(path, payload, out, vars) {
    var r = await A.request(API + path, null, payload);
    if (!r.ok) { if (out) out.textContent = A.refusal("task.refused", r.data, vars); return false; }
    T.last = "";
    await load(true);
    return true;
  }
  T.call = call;

  // ------------------------------------------------------------------ one task, and a member's tasks

  function outOf(li) { return li.querySelector(":scope > .out"); }

  // Rewriting a task in place: its title and body, saved or given up (Escape); Ctrl/Cmd+Enter saves. Only what changed
  // is sent (the body is its holder's to keep current).
  function editForm(task, li) {
    var form = make("form", "tedit"), title = make("input"), area = make("textarea");
    form.noValidate = true;
    title.value = task.title;
    title.maxLength = 200;
    title.setAttribute("aria-label", t("task.title_label"));
    area.value = task.body || "";
    area.rows = 4;
    area.maxLength = 10000;
    area.placeholder = t("task.body_label");
    area.setAttribute("aria-label", t("task.body_label"));
    var row = make("div", "row");
    function done() { T.editing = null; changed(); focusTask(task.id); }
    var cancel = A.button("btn", t("task.cancel"), done);
    row.append(make("button", "btn primary", t("task.save")), cancel);
    form.append(title, area, row);
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      if (!title.value.trim()) { outOf(li).textContent = t("tt.title_needed"); title.focus(); return; }
      var payload = {};
      if (title.value !== task.title) payload.title = title.value;
      if (area.value !== (task.body || "")) payload.body = area.value;
      if (!Object.keys(payload).length) { done(); return; }
      if (await call("tasks/" + task.id, payload, outOf(li))) done();
    });
    form.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); cancel.click(); }
      else if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); form.requestSubmit(); }
    });
    setTimeout(function () { title.focus(); }, 0);
    return form;
  }
  T.editForm = editForm;

  function focusTask(id) {
    var b = document.querySelector('[data-key="tacts:' + id + '"]');
    if (b) b.focus();
  }

  // Removing asks in place: a button armed at the task, a second press removes it.
  function armRemove(task, li) {
    var rm = A.button("btn tremove", t("task.remove"));
    li.appendChild(rm);
    rm.addEventListener("click", function () {
      if (!A.twoStep(rm, t("task.confirm_remove", {id: task.id}))) return;
      call("tasks/" + task.id + "/remove", {}, outOf(li));
    });
    function drop() { setTimeout(function () { if (!rm._armed) rm.remove(); }, 0); }
    rm.addEventListener("blur", drop);
    setTimeout(drop, 5200);
    A.twoStep(rm, t("task.confirm_remove", {id: task.id}));
  }

  T.menuItems = function (task, li) {
    var out = outOf(li);
    function markDone() { call("tasks/" + task.id, {done: true}, out); }
    if (task.done) return [{label: t("task.remove"), run: function () { armRemove(task, li); }}];
    if (!T.mayAct(task)) return [{label: t("task.mark_done"), run: markDone}];      // its poster
    var items = [{label: t("task.edit"), run: function () { T.editing = task.id; changed(); }}];
    var g = group(task.group), others = g ? g.members.filter(function (m) {
      return m.kind === "agent" && m.name !== task.responsible && T.mayGive(m.name);
    }) : [];
    if (others.length) {
      items.push({label: t("task.hand"), items: others.map(function (m) {
        return {label: t("task.hand_to", {name: m.name}), run: function () { call("tasks/" + task.id, {responsible: m.name}, out); }};
      })});
    }
    if (task.responsible_kind === "agent") {
      items.push({label: t(task.assigned_by ? "task.unlock" : "task.lock"), run: function () {
        call("tasks/" + task.id, {locked: !task.assigned_by}, out);
      }});
    }
    if (task.responsible) {
      items.push({label: t("task.release"), run: function () { call("tasks/" + task.id, {responsible: ""}, out); }});
    }
    items.push({label: t("task.mark_done"), run: markDone});
    items.push({separator: true}, {label: t("task.remove"), run: function () { armRemove(task, li); }});
    return items;
  };

  function openMenu(task, li, where, opener) {
    A.menu(Object.assign({label: t("task.task_acts", {text: task.title})}, where), T.menuItems(task, li), opener);
  }
  T.openMenu = openMenu;

  // The tasks tab of the work page at a scope: `query` like "agent=a1" or "show=unheld".
  T.tableHref = function (query) {
    return "/" + encodeURIComponent(SLUG) + "/work" + (query ? "?" + query : "");
  };

  T.row = function (task) {
    var li = make("li", "ptask" + (task.assigned_by ? " locked" : ""));
    li.dataset.task = String(task.id);
    if (T.editing === task.id && T.canEdit) {
      li.appendChild(editForm(task, li));
    } else {
      var text = make("span", "ptask-text", task.title);
      text.title = task.title;
      li.appendChild(text);
      if (task.assigned_by) {
        var tag = make("span", "tag", t("tt.assigned_by", {name: task.assigned_by}));
        tag.title = t("task.locked", {name: task.assigned_by});
        li.appendChild(tag);
      }
      if (T.mayAct(task) || T.mayDone(task)) {
        var acts = A.button("row-acts shown");
        acts.appendChild(A.glyph("dots"));
        acts.setAttribute("aria-label", t("task.task_acts", {text: task.title}));
        acts.title = t("task.task_acts", {text: task.title});
        acts.setAttribute("aria-haspopup", "menu");
        acts.setAttribute("aria-expanded", "false");
        acts.dataset.key = "tacts:" + task.id;
        acts.addEventListener("click", function () { openMenu(task, li, {anchor: acts}, acts); });
        li.appendChild(acts);
        li.addEventListener("contextmenu", function (ev) {
          ev.preventDefault();
          ev.stopPropagation();
          openMenu(task, li, {x: ev.clientX, y: ev.clientY}, acts);
        });
        li.addEventListener("keydown", function (ev) {
          if (!(ev.key === "ContextMenu" || (ev.key === "F10" && ev.shiftKey)) || ev.target.closest("form")) return;
          ev.preventDefault();
          ev.stopPropagation();
          openMenu(task, li, {anchor: acts}, acts);
        });
      }
      var upd = T.updated(task, "ptask-updated");
      if (upd) li.appendChild(upd);
    }
    var out = make("div", "out");
    out.setAttribute("aria-live", "polite");
    li.appendChild(out);
    return li;
  };

  // A member's task as its status, on one line; a long title (or, from before 1t, more than one task) folded under
  // "n 項任務".
  T.block = function (tasks, key) {
    var box = make("div", "ptasks");
    if (!tasks.length) return box;
    var long = tasks.length > 1 || tasks[0].title.length > LONG || T.editing === tasks[0].id;
    var ul = make("ul", "ptask-list");
    tasks.forEach(function (x) { ul.appendChild(T.row(x)); });
    if (!long) { box.appendChild(ul); return box; }
    var open = !!T.open[key] || tasks.some(function (x) { return x.id === T.editing; });
    ul.id = "tl-" + key.replace(/[^A-Za-z0-9_-]/g, "_");
    ul.hidden = !open;
    var b = A.button("ptask-fold", t("task.n", {n: tasks.length}), function () {
      T.open[key] = ul.hidden;
      ul.hidden = !ul.hidden;
      b.setAttribute("aria-expanded", String(!ul.hidden));
    });
    b.setAttribute("aria-expanded", String(open));
    b.setAttribute("aria-controls", ul.id);
    b.dataset.key = "fold:" + key;
    box.append(b, ul);
    return box;
  };

  // ------------------------------------------------------------------ a new task

  // The form for a new task: for an agent `member` (in one of its groups), or for nobody (the group chosen).
  T.addForm = function (member) {
    var groups = T.groupsFor(member), form = make("form", "tadd"), input = make("input"), out = make("span", "out");
    out.setAttribute("aria-live", "polite");
    input.name = "title";
    input.maxLength = 200;
    input.required = true;
    input.placeholder = t("task.title_label");
    input.dataset.key = "add-text:" + (member || "");
    input.setAttribute("aria-label", member ? t("task.add_for", {name: member}) : t("task.add"));
    // Open to AI (every agent) unless chosen otherwise: a person's own agent group is never the silent default.
    var start = (T.adding && T.adding.group) ||
                (groups.some(function (g) { return g.name === "ai" && g.kind === "default"; }) ? "ai" : undefined);
    var pick = A.dropdown({label: t("tt.open_to_label"), options: groups.map(function (g) {
      return {value: g.name, label: g.name === "ai" && g.kind === "default" ? t("tt.all_agents") : T.groupLabel(g)};
    }), value: start});
    var cancel = A.button("btn", t("task.cancel"), function () { T.adding = null; changed(); });
    var row = make("div", "row");
    row.append(make("button", "btn primary", t("task.add")), cancel);
    if (groups.length > 1) form.appendChild(pick.el);
    form.append(input, row, out);
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      if (!input.value.trim() || !pick.value) return;
      var body = {group: pick.value, title: input.value};
      if (member) body.responsible = member;
      if (await call("tasks", body, out)) { T.adding = null; changed(); }
    });
    form.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); cancel.click(); }
    });
    setTimeout(function () { input.focus(); }, 0);
    return form;
  };
  // Start writing a new task for `member` ("" for nobody); the member list draws the form.
  T.startAdding = function (member) {
    T.adding = {member: member || ""};
    changed();
  };

  setInterval(function () { load(false); }, EVERY_MS);
  load(true);
})();
