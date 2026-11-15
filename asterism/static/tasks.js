// The task table on the right of the messages page (#task-panel): per group its members (presence mark, the word
// for busy) with the tasks each is responsible for, then the tasks nobody is responsible for; groups without tasks
// take one quiet line. Read from /api/tasks on the messages' rhythm; a refresh waits while the person is editing in
// the panel or has an act armed. A person who may edit tasks (data-can-edit) adds, rewrites, reassigns, locks and
// removes them with the acts on each task; a refusal shows the server's sentence at that task.
// #task-toggle folds the panel away and brings it back, remembered per project; below 900 px it opens over the
// messages and starts folded.
"use strict";
(function () {
  var A = window.Asterism;
  var panel = document.getElementById("task-panel"), root = document.getElementById("chat");
  if (!A || !panel || !root) return;
  var t = A.t, make = A.make;

  var SLUG = root.dataset.slug, API = "/" + encodeURIComponent(SLUG) + "/api/";
  var EVERY_MS = 4000, OWN_SUFFIX = "-agents", FOLD_KEY = "asterism-tasks-folded:" + SLUG;
  var body = document.getElementById("task-body"), summary = document.getElementById("task-summary");
  var toggle = document.getElementById("task-toggle"), closer = document.getElementById("task-close");
  var tasks = {canEdit: !!panel.dataset.canEdit, last: "", data: null, adding: null, n: 0, open: 0};
  var narrow = window.matchMedia("(max-width: 899.98px)");

  function groupLabel(g) {
    if (g.kind === "default" && A.MSG["group." + g.name]) return t("group." + g.name);
    if (g.kind === "ownership" && g.name.slice(-OWN_SUFFIX.length) === OWN_SUFFIX) {
      return t("group.ownership", {owner: g.name.slice(0, -OWN_SUFFIX.length)});
    }
    return g.name;
  }

  async function taskCall(path, payload, out) {
    var r = await A.request(API + path, null, payload);
    if (!r.ok) { out.textContent = A.refusal("task.refused", r.data); return false; }
    tasks.last = "";
    await load(true);
    return true;
  }

  function memberLine(m) {
    var line = make("div", "tmember");
    line.appendChild(A.side ? A.side.presence(m) : make("span"));
    line.appendChild(make("span", "", m.name));
    if (m.kind === "agent" && m.busy) line.appendChild(make("span", "word", t("task.busy")));
    return line;
  }

  function act(label, key, onClick) {
    var b = A.button("", label, onClick);
    b.dataset.key = key;
    return b;
  }

  function taskRow(task, group) {
    var li = make("li", "task" + (task.assigned_by ? " locked" : ""));
    var line = make("div", "tline");
    line.appendChild(make("span", "tid", "#" + task.id));
    line.appendChild(make("span", "ttext", task.text));
    if (task.assigned_by) line.appendChild(make("span", "pill", t("task.locked", {name: task.assigned_by})));
    li.appendChild(line);
    var out = make("div", "out");
    out.setAttribute("aria-live", "polite");
    if (!tasks.canEdit) { li.appendChild(out); return li; }

    var acts = make("div", "tacts");
    acts.setAttribute("role", "group");
    acts.setAttribute("aria-label", t("task.acts", {id: task.id}));

    acts.appendChild(act(t("task.edit"), "edit:" + task.id, function () {
      var form = make("form", "tedit"), area = make("textarea");
      area.value = task.text;
      area.rows = 2;
      area.maxLength = 2000;
      area.setAttribute("aria-label", t("task.text_label"));
      var row = make("div", "row");
      var cancel = A.button("btn", t("task.cancel"), function () { tasks.last = ""; load(true); });
      row.append(make("button", "btn primary", t("task.save")), cancel);
      form.append(area, row);
      form.addEventListener("submit", async function (ev) {
        ev.preventDefault();
        await taskCall("tasks/" + task.id, {text: area.value}, out);
      });
      form.addEventListener("keydown", function (ev) { if (ev.key === "Escape") cancel.click(); });
      line.replaceWith(form);
      area.focus();
    }));

    var who = make("select");
    who.dataset.key = "who:" + task.id;
    who.setAttribute("aria-label", t("task.responsible"));
    var none = make("option", "", t("task.nobody"));
    none.value = "";
    who.appendChild(none);
    group.members.forEach(function (m) {
      var o = make("option", "", m.name);
      o.value = m.name;
      who.appendChild(o);
    });
    who.value = task.responsible || "";
    who.addEventListener("change", async function () {
      if (!(await taskCall("tasks/" + task.id, {responsible: who.value}, out))) who.value = task.responsible || "";
    });
    acts.appendChild(who);

    if (task.responsible_kind === "agent") {
      var lock = act(t(task.assigned_by ? "task.unlock" : "task.lock"), "lock:" + task.id, function () {
        taskCall("tasks/" + task.id, {locked: !task.assigned_by}, out);
      });
      lock.title = t("task.lock_hint");
      acts.appendChild(lock);
    }

    acts.appendChild(act(t("task.remove"), "rm:" + task.id, function () {
      if (!A.twoStep(this, t("task.confirm_remove", {id: task.id}))) return;
      taskCall("tasks/" + task.id + "/remove", {}, out);
    }));
    li.append(acts, out);
    return li;
  }

  function addForm(g) {
    var form = make("form", "tadd"), input = make("input"), out = make("span", "out");
    input.name = "text";
    input.maxLength = 2000;
    input.required = true;
    input.dataset.key = "add-text:" + g.name;
    input.placeholder = t("task.text_label");
    input.setAttribute("aria-label", t("task.add_to", {group: groupLabel(g)}));
    var cancel = A.button("btn", t("task.cancel"), function () { tasks.adding = null; draw(tasks.data, "add:" + g.name); });
    form.append(input, make("button", "btn primary", t("task.add")), cancel, out);
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      if (!input.value.trim()) return;
      if (await taskCall("tasks", {group: g.name, text: input.value}, out)) tasks.adding = null;
    });
    form.addEventListener("keydown", function (ev) { if (ev.key === "Escape") { ev.stopPropagation(); cancel.click(); } });
    return form;
  }

  function addButton(g) {
    var plus = A.button("btn quiet tadd-btn", "+ " + t("task.add"), function () {
      tasks.adding = g.name;
      draw(tasks.data, null);
      var input = body.querySelector('[data-key="add-text:' + g.name.replace(/["\\]/g, "\\$&") + '"]');
      if (input) input.focus();
    });
    plus.dataset.key = "add:" + g.name;
    plus.setAttribute("aria-label", t("task.add_to", {group: groupLabel(g)}));
    return plus;
  }

  function groupHead(g) {
    var head = make("div", "tghead"), name = make("h3", "", groupLabel(g));
    if (groupLabel(g) !== g.name) name.appendChild(make("small", "", " " + g.name));
    head.appendChild(name);
    return head;
  }

  // A group with tasks: each member with the tasks they are responsible for, then those of nobody.
  function groupBlock(g) {
    var box = make("section", "tgroup"), head = groupHead(g);
    if (tasks.canEdit && tasks.adding !== g.name) head.appendChild(addButton(g));
    box.appendChild(head);
    g.members.forEach(function (m) {
      box.appendChild(memberLine(m));
      var mine = g.tasks.filter(function (x) { return x.responsible === m.name; });
      if (!mine.length) return;
      var ul = make("ul", "tlist");
      mine.forEach(function (x) { ul.appendChild(taskRow(x, g)); });
      box.appendChild(ul);
    });
    var open = g.tasks.filter(function (x) {
      return !x.responsible || !g.members.some(function (m) { return m.name === x.responsible; });
    });
    if (open.length) {
      box.appendChild(make("div", "tmember nobody", t("task.nobody")));
      var ul = make("ul", "tlist");
      open.forEach(function (x) { ul.appendChild(taskRow(x, g)); });
      box.appendChild(ul);
    }
    if (tasks.canEdit && tasks.adding === g.name) box.appendChild(addForm(g));
    return box;
  }

  // A group without tasks: one quiet line, its members as marks.
  function quietLine(g) {
    var box = make("section", "tgroup"), head = groupHead(g), marks = make("span", "tmarks");
    if (!g.members.length) marks.appendChild(make("span", "dim small", t("task.no_members")));
    g.members.forEach(function (m) {
      var mark = A.side ? A.side.presence(m) : make("span");
      mark.title = m.name;
      mark.setAttribute("aria-label", m.name + " " + (mark.getAttribute("aria-label") || ""));
      marks.appendChild(mark);
    });
    head.appendChild(marks);
    if (tasks.canEdit && tasks.adding !== g.name) head.appendChild(addButton(g));
    box.appendChild(head);
    if (tasks.canEdit && tasks.adding === g.name) box.appendChild(addForm(g));
    return box;
  }

  function draw(data, focusKey) {
    tasks.data = data;
    var groups = data.groups || [];
    tasks.n = 0;
    tasks.open = 0;
    groups.forEach(function (g) {
      tasks.n += g.tasks.length;
      tasks.open += g.tasks.filter(function (x) { return !x.responsible; }).length;
    });
    summary.textContent = t("task.summary", {n: tasks.n, open: tasks.open});
    label();
    A.keepFocus(body, function () {
      body.textContent = "";
      groups.filter(function (g) { return g.tasks.length; }).forEach(function (g) { body.appendChild(groupBlock(g)); });
      var quiet = groups.filter(function (g) { return !g.tasks.length; });
      if (quiet.length) {
        var rest = make("div", "tquiet");
        quiet.forEach(function (g) { rest.appendChild(quietLine(g)); });
        body.appendChild(rest);
      }
    });
    if (focusKey) {
      var again = body.querySelector('[data-key="' + focusKey.replace(/["\\]/g, "\\$&") + '"]');
      if (again) again.focus();
    }
  }

  // Someone is typing in the panel, has an editor open or an act armed: a redraw would throw that away.
  function editing() {
    var a = document.activeElement;
    return !!body.querySelector("form.tedit") || A.isArmed(body) ||
           !!(a && body.contains(a) && /^(INPUT|TEXTAREA)$/.test(a.tagName) && a.value) ||
           !!(a && body.contains(a) && a.tagName === "SELECT");
  }

  async function load(force) {
    if (!force && editing()) return;
    var r = await A.request(API + "tasks");
    if (!r.ok) return;
    var raw = JSON.stringify(r.data);
    if (raw === tasks.last && !force) return;
    if (!force && editing()) return;
    tasks.last = raw;
    draw(r.data, null);
  }

  // ------------------------------------------------------------------ folding the panel

  function stored() {
    try { return localStorage.getItem(FOLD_KEY) === "1"; } catch (err) { return false; }
  }
  function label() {
    var open = !panel.hidden;
    toggle.setAttribute("aria-expanded", String(open));
    toggle.textContent = open ? t("task.toggle_hide") : t("task.toggle_show", {n: tasks.n, open: tasks.open});
  }
  function setOpen(open, remember) {
    panel.hidden = !open;
    label();
    if (remember && !narrow.matches) {
      try { localStorage.setItem(FOLD_KEY, open ? "0" : "1"); } catch (err) { /* this page only */ }
    }
    if (open && narrow.matches) (closer || panel).focus();
  }

  toggle.addEventListener("click", function () { setOpen(panel.hidden, true); });
  if (closer) closer.addEventListener("click", function () { setOpen(false, false); toggle.focus(); });
  panel.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && narrow.matches && !ev.defaultPrevented) { setOpen(false, false); toggle.focus(); }
  });
  function fit() { setOpen(narrow.matches ? false : !stored(), false); }
  if (narrow.addEventListener) narrow.addEventListener("change", fit);
  fit();

  setInterval(function () { load(false); }, EVERY_MS);
  load(true);
})();
