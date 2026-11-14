// The schedules page: every schedule of the project (#schedules) and, for a person who may make one, the form
// (#schedule-form). It speaks only the JSON API (/api/schedules) and reads the list again every few seconds,
// except while the person is editing. Times are shown and entered in the browser's local time; the API gets ISO
// times. A refusal shows the server's sentence. All texts come from the page's message catalogue (body data-msg).
"use strict";
(function () {
  var root = document.getElementById("schedules");
  if (!root) return;

  function parseJSON(raw, fallback) {
    try { return JSON.parse(raw); } catch (err) { return fallback; }
  }
  var MSG = parseJSON(document.body.dataset.msg || "{}", {});
  function t(key, vars) {
    var s = MSG[key] || key;
    Object.keys(vars || {}).forEach(function (k) { s = s.split("{" + k + "}").join(String(vars[k])); });
    return s;
  }
  function errorText(code) {
    return MSG["error." + code] || (MSG["error.generic"] || "{code}").replace("{code}", code || "?");
  }

  var SLUG = root.dataset.slug, ME = root.dataset.me, CAN_MANAGE = !!root.dataset.canManage;
  var PLACES = parseJSON(root.dataset.places, {channels: [], people: [], agents: []});
  var MIN_EVERY = Number(root.dataset.minEvery) || 300;
  var API = "/" + encodeURIComponent(SLUG) + "/api/";
  var LEVELS = ["important", "normal", "muted"], EVERY_MS = 4000;
  var LANG = document.documentElement.lang || undefined;
  var shown = "";

  async function call(path, body) {
    var opts = {method: body === undefined ? "GET" : "POST", credentials: "same-origin",
                headers: {"Accept": "application/json"}};
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    try {
      var r = await fetch(API + path, opts);
      return {ok: r.ok, data: (await r.json()) || {}};
    } catch (err) {
      return {ok: false, data: {error: "network"}};
    }
  }

  function make(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function refused(out, data) {
    out.textContent = data.message ? t("sch.refused", {message: data.message}) : errorText(data.error);
  }

  // ------------------------------------------------------------------ times

  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function localInput(iso) {               // an ISO time as the value of a datetime-local input
    var d = new Date(iso);
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + "T" + pad(d.getHours()) + ":" +
           pad(d.getMinutes());
  }
  function fromInput(value) {              // the input's local time as an ISO time (UTC, with Z)
    var d = new Date(value);
    return isNaN(d.getTime()) ? null : d.toISOString();
  }
  function showTime(iso) {
    return new Date(iso).toLocaleString(LANG, {dateStyle: "medium", timeStyle: "short"});
  }
  function everyText(s) {
    if (s % 3600 === 0) return t("sch.every_h", {n: s / 3600});
    if (s % 60 === 0) return t("sch.every_m", {n: s / 60});
    return t("sch.every_s", {n: s});
  }

  // ------------------------------------------------------------------ the fields (new schedule and editing)

  function field(label, input) {
    var lab = make("label", "sch-field");
    lab.appendChild(make("span", "sch-label", label));
    lab.appendChild(input);
    return lab;
  }

  function placeSelect(value) {
    var sel = make("select");
    sel.name = "to";
    function group(label, items, text) {
      if (!items.length) return;
      var g = make("optgroup");
      g.label = label;
      items.forEach(function (v) {
        var o = make("option", "", text(v));
        o.value = v.value;
        g.appendChild(o);
      });
      sel.appendChild(g);
    }
    group(t("sch.channels"), PLACES.channels.map(function (n) { return {value: "#" + n}; }), function (v) { return v.value; });
    group(t("sch.people"), PLACES.people.map(function (n) { return {value: n}; }), function (v) { return v.value; });
    group(t("sch.agents"), PLACES.agents.map(function (n) { return {value: n}; }),
          function (v) { return t("msg.my_agent", {name: v.value}); });
    if (value) {
      if (!Array.prototype.some.call(sel.options, function (o) { return o.value === value; })) {
        var keep = make("option", "", value);              // a place no longer offered: kept so it shows
        keep.value = value;
        sel.insertBefore(keep, sel.firstChild);
      }
      sel.value = value;
    }
    return sel;
  }

  // The fields of a schedule; `s` fills them for editing. Returns {box, read()} where read() gives the body
  // (only what changed, when editing) or null when the time is missing.
  function fields(s) {
    var box = make("div", "sch-fields");
    var to = placeSelect(s ? s.to : "");
    var text = make("textarea");
    text.name = "text";
    text.rows = 3;
    text.maxLength = 4000;
    text.required = true;
    if (s) text.value = s.text;
    var level = make("select");
    level.name = "level";
    LEVELS.forEach(function (l) {
      var o = make("option", "", t("sch.level." + l));
      o.value = l;
      level.appendChild(o);
    });
    level.value = s ? s.level : "normal";
    var start = make("input");
    start.type = "datetime-local";
    start.name = "start_at";
    start.required = true;
    if (s) start.value = localInput(s.start_at);
    var repeat = make("select"), n = make("input");
    repeat.name = "repeat";
    [["once", "sch.once"], ["minutes", "sch.minutes"], ["hours", "sch.hours"]].forEach(function (x) {
      var o = make("option", "", t(x[1]));
      o.value = x[0];
      repeat.appendChild(o);
    });
    n.type = "number";
    n.min = "1";
    n.step = "1";
    n.name = "every_n";
    n.setAttribute("aria-label", t("sch.every_n"));
    if (s && s.every_s) {
      repeat.value = s.every_s % 3600 === 0 ? "hours" : "minutes";
      n.value = String(s.every_s % 3600 === 0 ? s.every_s / 3600 : Math.max(1, Math.round(s.every_s / 60)));
    } else {
      repeat.value = "once";
      n.value = String(Math.max(1, Math.ceil(MIN_EVERY / 60)));
    }
    function sync() { n.hidden = repeat.value === "once"; }
    repeat.addEventListener("change", sync);
    sync();
    var how = make("span", "sch-repeat");
    how.appendChild(repeat);
    how.appendChild(document.createTextNode(" "));
    how.appendChild(n);
    var hint = make("small", "muted", " " + (MIN_EVERY >= 60 ? t("sch.min_minutes", {n: MIN_EVERY / 60})
                                                             : t("sch.min_seconds", {n: MIN_EVERY})));
    how.appendChild(hint);

    box.appendChild(field(t("sch.to"), to));
    box.appendChild(field(t("sch.text"), text));
    box.appendChild(field(t("sch.level"), level));
    box.appendChild(field(t("sch.start"), start));
    box.appendChild(field(t("sch.repeat"), how));

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
      if (start.value !== localInput(s.start_at)) changed.start_at = body.start_at;
      if (body.every_s !== s.every_s) changed.every_s = body.every_s;
      return changed;
    }
    return {box: box, read: read};
  }

  // ------------------------------------------------------------------ the list

  function canControl(s) { return s.by === ME || CAN_MANAGE; }

  function item(s) {
    var li = make("li", "sch" + (s.paused ? " paused" : ""));
    li.id = "s-" + s.id;
    var head = make("div", "sch-head");
    head.appendChild(make("span", "tid", "#" + s.id));
    head.appendChild(make("strong", "", s.to));
    head.appendChild(make("span", "tag" + (s.level === "important" ? " important" : ""), t("sch.level_short." + s.level)));
    head.appendChild(make("span", "muted", t("sch.by", {name: s.by})));
    li.appendChild(head);
    li.appendChild(make("div", "sch-text", s.text));
    var when = make("div", "sch-when muted");
    var parts = [s.every_s ? everyText(s.every_s) : t("sch.runs_once")];
    if (!s.paused) parts.push(s.next_at ? t("sch.next", {time: showTime(s.next_at)}) : t("sch.no_next"));
    if (s.last_message) parts.push(t("sch.last", {id: s.last_message}));
    when.textContent = parts.join(" · ");
    li.appendChild(when);
    if (s.paused) {
      li.appendChild(make("div", "sch-paused", s.paused_because ? t("sch.paused." + s.paused_because) : t("sch.paused")));
    }
    var tools = make("div", "sch-tools"), out = make("span", "out");
    if (canControl(s)) {
      var pause = make("button", "", t(s.paused ? "sch.resume" : "sch.pause"));
      pause.type = "button";
      pause.addEventListener("click", function () { act("schedules/" + s.id, {paused: !s.paused}, out); });
      tools.appendChild(pause);
    }
    if (s.by === ME) {
      var edit = make("button", "", t("sch.edit"));
      edit.type = "button";
      edit.addEventListener("click", function () { editor(li, s); });
      tools.appendChild(edit);
    }
    if (canControl(s)) {
      var rm = make("button", "", t("sch.remove"));
      rm.type = "button";
      rm.addEventListener("click", function () {
        if (window.confirm(t("sch.confirm_remove", {id: s.id}))) act("schedules/" + s.id + "/remove", {}, out);
      });
      tools.appendChild(rm);
    }
    tools.appendChild(out);
    if (tools.children.length > 1) li.appendChild(tools);
    return li;
  }

  function editor(li, s) {
    var form = make("form", "sch-form sch-edit"), f = fields(s), out = make("span", "out");
    var save = make("button", "", t("sch.save")), cancel = make("button", "", t("sch.cancel"));
    cancel.type = "button";
    cancel.addEventListener("click", function () { shown = ""; load(true); });
    form.appendChild(f.box);
    var row = make("div", "sch-tools");
    row.appendChild(save);
    row.appendChild(cancel);
    row.appendChild(out);
    form.appendChild(row);
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var body = f.read();
      if (body === null) { out.textContent = t("sch.no_time"); return; }
      if (!Object.keys(body).length) { shown = ""; load(true); return; }
      await act("schedules/" + s.id, body, out);
    });
    li.textContent = "";
    li.appendChild(form);
  }

  async function act(path, body, out) {
    var r = await call(path, body);
    if (!r.ok) { refused(out, r.data); return false; }
    shown = "";
    await load(true);
    return true;
  }

  function draw(list) {
    root.textContent = "";
    if (!list.length) { root.appendChild(make("p", "muted", t("sch.empty"))); return; }
    var ul = make("ul", "sch-list");
    list.forEach(function (s) { ul.appendChild(item(s)); });
    root.appendChild(ul);
  }

  function editing() { return !!root.querySelector("form.sch-edit"); }

  async function load(force) {
    if (!force && editing()) return;
    var r = await call("schedules");
    if (!r.ok) return;
    var raw = JSON.stringify(r.data.schedules || []);
    if (raw === shown || (!force && editing())) return;
    shown = raw;
    draw(r.data.schedules || []);
  }

  // ------------------------------------------------------------------ the form for a new schedule

  var form = document.getElementById("schedule-form");
  if (form) {
    var f = fields(null), out = make("span", "out"), btn = make("button", "", t("sch.create"));
    form.appendChild(f.box);
    var row = make("div", "sch-tools");
    row.appendChild(btn);
    row.appendChild(out);
    form.appendChild(row);
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var body = f.read();
      if (body === null) { out.textContent = t("sch.no_time"); return; }
      out.textContent = "";
      if (await act("schedules", body, out)) form.elements.text.value = "";
    });
  }

  setInterval(function () { load(false); }, EVERY_MS);
  load(true);
})();
