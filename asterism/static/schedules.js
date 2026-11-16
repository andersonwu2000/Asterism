// The agent page's scheduled messages tab (#schedules; m1f5_agent_page_design.md section 4), from /api/schedules,
// read again every few seconds (agentpage.js), never while one is being changed. Times are shown and entered in the
// browser's local time; the API gets ISO times. All texts come from the page's message catalogue.
// - Scopes: all; made by me; paused; and one per place a schedule posts to.
// - One block per schedule, by id (a list that re-sorted by the next run would move under the reader): where to (a
//   member with its presence mark), its level as a quiet tag when it is not the usual one, "paused", who made it when
//   not me; at the right when it runs next over how often; its text (four lines, then "顯示全部"); the last message it
//   posted, or why it is paused. Its menu: pause or resume (its creator; who may manage members), change (its creator:
//   the block becomes the form; a paused one can be saved and resumed at once), remove (in two steps, in place).
// - The form for a new one (#schedule-form, only for who may create) opens from the tab's action at the top of the
//   list; Escape closes it and the focus goes back to the action.
"use strict";
(function () {
  var A = window.Asterism, G = A && A.agentPage, root = document.getElementById("agent-page");
  var list = document.getElementById("schedules");
  if (!G || !list) return;
  var t = A.t, make = A.make, S = A.side;
  var ME = G.me, API = G.api;
  var PLACES = A.parseJSON(root.dataset.places, {channels: [], people: [], agents: []});
  var MIN_EVERY = Number(root.dataset.minEvery) || 300;
  var LEVELS = ["important", "normal", "muted"];
  var data = [], raw = "", loaded = false, opened = {};

  function call(path, body) { return A.request(API + path, null, body); }

  // ------------------------------------------------------------------ times

  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function localInput(d) {                 // a time as the value of a datetime-local input
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + "T" + pad(d.getHours()) + ":" +
           pad(d.getMinutes());
  }
  function fromInput(value) {              // the input's local time as an ISO time (UTC, with Z)
    var d = new Date(value);
    return isNaN(d.getTime()) ? null : d.toISOString();
  }
  function nextHour() {
    var d = new Date();
    d.setMinutes(0, 0, 0);
    d.setHours(d.getHours() + 1);
    return d;
  }
  function everyText(s) {
    if (s % 3600 === 0) return t("sch.every_h", {n: s / 3600});
    if (s % 60 === 0) return t("sch.every_m", {n: s / 60});
    return t("sch.every_s", {n: s});
  }

  // ------------------------------------------------------------------ the fields (new schedule and changing one)

  function field(label, input, wide) {
    var lab = make("label", "sch-field" + (wide ? " wide" : ""));
    lab.appendChild(make("span", "sch-label", label));
    lab.appendChild(input);
    return lab;
  }

  // Where a schedule posts: the one dropdown, the channels, people and my agents under their headings.
  function placeSelect(value) {
    var options = [];
    PLACES.channels.forEach(function (n) { options.push({value: "#" + n, label: "#" + n, group: t("sch.channels")}); });
    PLACES.people.forEach(function (n) { options.push({value: n, label: n, group: t("sch.people")}); });
    PLACES.agents.forEach(function (n) { options.push({value: n, label: t("msg.my_agent", {name: n}), group: t("sch.agents")}); });
    if (value && !options.some(function (o) { return o.value === value; })) {
      options.unshift({value: value, label: value});       // a place no longer offered: kept so it shows
    }
    return A.dropdown({label: t("sch.to"), options: options, value: value || undefined, name: "to"});
  }

  // The fields of a schedule; `s` fills them for changing it. Returns {box, read(), focus()} where read() gives the
  // body (only what changed, when changing) or null when the time is missing.
  function fields(s) {
    var box = make("div", "sch-fields");
    var to = placeSelect(s ? s.to : "");
    var text = make("textarea");
    text.name = "text";
    text.rows = 3;
    text.maxLength = 4000;
    text.required = true;
    if (s) text.value = s.text;
    var level = A.dropdown({label: t("sch.level"), name: "level", value: s ? s.level : "normal",
                            options: LEVELS.map(function (l) { return {value: l, label: t("sch.level." + l)}; })});
    var start = make("input");
    start.type = "datetime-local";
    start.name = "start_at";
    start.required = true;
    start.value = localInput(s ? new Date(s.start_at) : nextHour());
    var n = make("input"), every = null;
    if (s && s.every_s) every = s.every_s % 3600 === 0 ? "hours" : "minutes";
    var repeat = A.dropdown({label: t("sch.repeat"), name: "repeat", value: every || "once", onChange: function () { sync(); },
                             options: [["once", "sch.once"], ["minutes", "sch.minutes"], ["hours", "sch.hours"]].map(function (x) {
                               return {value: x[0], label: t(x[1])};
                             })});
    n.type = "number";
    n.min = "1";
    n.step = "1";
    n.name = "every_n";
    n.setAttribute("aria-label", t("sch.every_n"));
    n.value = s && s.every_s ? String(s.every_s % 3600 === 0 ? s.every_s / 3600 : Math.max(1, Math.round(s.every_s / 60)))
                             : String(Math.max(1, Math.ceil(MIN_EVERY / 60)));
    function sync() { n.hidden = repeat.value === "once"; }
    sync();
    var how = make("span", "sch-repeat");
    how.append(repeat.el, n, make("small", "muted", MIN_EVERY >= 60 ? t("sch.min_minutes", {n: MIN_EVERY / 60})
                                                                     : t("sch.min_seconds", {n: MIN_EVERY})));
    box.append(field(t("sch.to"), to.el), field(t("sch.level"), level.el), field(t("sch.text"), text, true),
               field(t("sch.start"), start), field(t("sch.repeat"), how));

    function read() {
      var at = fromInput(start.value);
      if (!at) return null;
      var every = repeat.value === "once" ? null : Math.round(Number(n.value) * (repeat.value === "hours" ? 3600 : 60));
      var body = {to: to.value, text: text.value, level: level.value, start_at: at, every_s: every};
      if (!s) return body;
      var changed = {};
      if (body.to !== s.to) changed.to = body.to;
      if (body.text !== s.text) changed.text = body.text;
      if (body.level !== s.level) changed.level = body.level;
      if (start.value !== localInput(new Date(s.start_at))) changed.start_at = body.start_at;
      if (body.every_s !== s.every_s) changed.every_s = body.every_s;
      return changed;
    }
    return {box: box, read: read, text: text, focus: function () { to.button.focus(); }};
  }

  // Escape gives up (`cancel`), Ctrl/Cmd+Enter in the text sends.
  function keys(form, cancel) {
    form.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); cancel(); }
      else if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey) && ev.target.tagName === "TEXTAREA") {
        ev.preventDefault();
        form.requestSubmit();
      }
    });
  }

  // ------------------------------------------------------------------ the list

  function canControl(s) { return s.by === ME || G.canManage; }
  function isMember(to) { return to.charAt(0) !== "#"; }

  function place(to) {
    var span = make("span", "ag-line");
    if (isMember(to) && S) span.appendChild(S.presence(S.directory[to] || {kind: "person"}));
    span.appendChild(make("span", "sch-to" + (isMember(to) ? " mono" : ""), to));
    var who = S && S.directory[to];
    if (who && who.kind === "agent" && who.owner === ME) span.appendChild(make("span", "dim", t("nav.my_agent")));
    return span;
  }

  // Where the last message it posted is: a channel's in chat, a private one (only mine to open) on its page.
  function lastHref(s) {
    var base = "/" + encodeURIComponent(G.slug);
    if (!isMember(s.to)) return base + "?m=" + s.last_message + "#" + encodeURIComponent(s.to);
    return s.by === ME ? base + "/dm/" + encodeURIComponent(s.to) + "?m=" + s.last_message : null;
  }

  function item(s) {
    var li = make("li", "sch-item" + (s.paused ? " paused" : "")), out = make("div", "out");
    li.id = "s-" + s.id;
    out.setAttribute("aria-live", "polite");
    if (editing === s.id) { li.appendChild(editor(li, s, out)); li.appendChild(out); return li; }
    var line = place(s.to);
    if (s.level !== "normal") line.appendChild(make("span", "tag", t("sch.level_short." + s.level)));
    if (s.paused) line.appendChild(make("span", "tag", t("sch.paused")));
    if (s.by !== ME) line.appendChild(make("span", "dim", t("sch.by", {name: s.by})));
    li.appendChild(line);
    var when = make("div", "sch-when");
    if (!s.paused) when.appendChild(document.createTextNode(s.next_at ? t("sch.next", {time: G.time(s.next_at, true)}) : t("sch.no_next")));
    when.appendChild(make("span", "dim", s.every_s ? everyText(s.every_s) : t("sch.runs_once")));
    li.appendChild(when);
    if (canControl(s)) {
      var open = function (where, opener) {
        A.menu(Object.assign({label: t("sch.acts", {text: s.text})}, where), menuItems(s, li, out), opener);
      };
      var acts = G.acts(t("sch.acts", {text: s.text}), "sacts:" + s.id, open);
      li.appendChild(acts);
      G.menuOn(li, acts, open);
    }
    li.appendChild(G.clamp(s.text, "s" + s.id, opened));
    var foot = [];
    if (s.last_message) {
      var href = lastHref(s);
      if (href) { var a = make("a", "", t("sch.last")); a.href = href; foot.push(a); } else foot.push(t("sch.last"));
    }
    if (s.paused && s.paused_because) foot.push(t("sch.paused." + s.paused_because));
    if (foot.length) li.appendChild(G.facts("sch-foot", foot));
    li.appendChild(out);
    return li;
  }

  function menuItems(s, li, out) {
    var items = [{label: t(s.paused ? "sch.resume" : "sch.pause"), run: function () { act("schedules/" + s.id, {paused: !s.paused}, out); }}];
    if (s.by === ME) items.push({label: t("sch.edit"), run: function () { editing = s.id; G.redraw(true); }});
    items.push({separator: true}, {label: t("sch.remove"), run: function () { armRemove(s, li, out); }});
    return items;
  }

  // Removing asks in place: a button armed on the block, a second press removes it.
  function armRemove(s, li, out) {
    var rm = A.button("btn tremove", t("sch.remove"));
    rm.dataset.key = "srm:" + s.id;
    li.insertBefore(rm, out);
    rm.addEventListener("click", function () {
      if (!A.twoStep(rm, t("sch.confirm_remove"))) return;
      act("schedules/" + s.id + "/remove", {}, out);
    });
    function drop() { setTimeout(function () { if (!rm._armed) { rm.remove(); G.redraw(false); } }, 0); }
    rm.addEventListener("blur", drop);
    setTimeout(drop, 5200);
    A.twoStep(rm, t("sch.confirm_remove"));
  }

  var editing = null;            // the id of the schedule being changed

  function editor(li, s, out) {
    var form = make("form", "ag-form sch-edit"), f = fields(s);
    var resume = null;
    form.appendChild(f.box);
    if (s.paused) {
      resume = make("input");
      resume.type = "checkbox";
      resume.checked = true;
      resume.id = "resume-" + s.id;
      var lab = make("label", "ag-check");
      lab.htmlFor = resume.id;
      lab.append(resume, make("span", "", t("sch.resume_after")));
      form.appendChild(lab);
    }
    function cancel() {
      editing = null;
      G.redraw(true);
      var b = list.querySelector('[data-key="sacts:' + s.id + '"]');
      if (b) b.focus();
    }
    var row = make("div", "row");
    row.append(make("button", "btn primary", t("sch.save")), A.button("btn", t("sch.cancel"), cancel));
    form.appendChild(row);
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var body = f.read();
      if (body === null) { out.textContent = t("sch.no_time"); return; }
      if (resume && resume.checked) body.paused = false;
      if (!Object.keys(body).length) { cancel(); return; }
      if (await act("schedules/" + s.id, body, out)) cancel();
    });
    keys(form, cancel);
    setTimeout(function () { f.text.focus(); }, 0);
    return form;
  }

  async function act(path, body, out) {
    var r = await call(path, body);
    if (!r.ok) { G.say(out, A.refusal("sch.refused", r.data)); return false; }
    await load(true);
    return true;
  }

  async function load(force) {
    var r = await call("schedules");
    if (!r.ok) return;
    var now = JSON.stringify(r.data.schedules || []);
    loaded = true;
    if (now === raw && !force) return;
    raw = now;
    data = r.data.schedules || [];
    G.redraw(!!force, !!force);
  }

  // ------------------------------------------------------------------ the scope

  function scope() {
    var p = G.params(), show = p.get("show"), to = p.get("to");
    if (show === "mine" || show === "paused") return {show: show};
    if (to && data.some(function (s) { return s.to === to; })) return {to: to};
    return {};
  }
  function query(sc) {
    return sc.show ? "show=" + sc.show : sc.to ? "to=" + encodeURIComponent(sc.to) : "";
  }
  function inScope(s, sc) {
    if (sc.show === "mine") return s.by === ME;
    if (sc.show === "paused") return s.paused;
    if (sc.to) return s.to === sc.to;
    return true;
  }

  function draw() {
    var sc = scope(), shown = data.filter(function (s) { return inScope(s, sc); });
    list.textContent = "";
    if (!loaded) return;
    if (!shown.length) { list.appendChild(make("p", "ag-empty", t(data.length ? "sch.empty_scope" : "sch.empty"))); return; }
    var ul = make("ul", "ag-list");
    shown.forEach(function (s) { ul.appendChild(item(s)); });
    list.appendChild(ul);
  }

  // ------------------------------------------------------------------ the form for a new schedule

  var form = document.getElementById("schedule-form"), action = document.getElementById("schedule-new");
  var made = null;
  function openForm() {
    form.textContent = "";
    made = fields(null);
    var out = make("span", "out");
    out.setAttribute("aria-live", "polite");
    var row = make("div", "row");
    row.append(make("button", "btn primary", t("sch.create")), A.button("btn", t("sch.cancel"), function () { closeForm(true); }), out);
    form.append(made.box, row);
    form.hidden = false;
    action.setAttribute("aria-expanded", "true");
    made.focus();
  }
  function closeForm(refocus) {
    form.hidden = true;
    form.textContent = "";
    made = null;
    action.setAttribute("aria-expanded", "false");
    if (refocus) action.focus();
  }
  if (form && action) {
    action.addEventListener("click", function () { if (form.hidden) openForm(); else closeForm(true); });
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var out = form.querySelector(".out"), body = made && made.read();
      if (!body) { out.textContent = t("sch.no_time"); return; }
      out.textContent = "";
      var r = await call("schedules", body);
      if (!r.ok) { out.textContent = A.refusal("sch.refused", r.data); return; }
      closeForm(true);
      await load(true);
    });
    keys(form, function () { closeForm(true); });
  }

  // ------------------------------------------------------------------ the tab

  function count(f) { return data.filter(f).length; }

  G.register({
    scopes: function () {
      var out = [{heading: t("sch.title")},
                 {query: "", label: t("sch.all"), count: data.length},
                 {query: "show=mine", label: t("sch.mine"), count: count(function (s) { return s.by === ME; })},
                 {query: "show=paused", label: t("sch.paused_scope"), count: count(function (s) { return s.paused; })}];
      var seen = [];
      data.forEach(function (s) { if (seen.indexOf(s.to) < 0) seen.push(s.to); });
      if (seen.length) out.push({heading: t("sch.to_scope")});
      seen.forEach(function (to) {
        out.push({query: "to=" + encodeURIComponent(to), label: to, mono: isMember(to),
                  presence: isMember(to) && S ? S.directory[to] || {kind: "person"} : null,
                  count: count(function (s) { return s.to === to; })});
      });
      return out;
    },
    current: function () { return query(scope()); },
    title: function () {
      var sc = scope();
      var name = sc.show === "mine" ? t("sch.mine") : sc.show === "paused" ? t("sch.paused_scope") : sc.to || t("sch.scope_all");
      return t("ag.count", {name: name, n: count(function (s) { return inScope(s, sc); })});
    },
    draw: draw,
    busy: function () { return editing !== null; },
    load: function () { load(false); }
  });
  if (S) S.onMembers(function () { G.redraw(false); });
  load(true);
})();
