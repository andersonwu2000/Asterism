// Statuses (Asterism.statuses; m1s_contract.md), on the messages pages, the agent page and the work page. Each agent
// has one status that it writes itself: a one-line title and a body saying where it stands; its person may ask for an
// update every N hours, and an agent late with it is overdue. A person's status is a title only (a mood or a few
// words about themselves), set by the person. A status changes nothing of how messages reach anyone.
// - The members (frame.js) carry each member's status title, and an agent's when and overdue: the member list and the
//   profile card (people.js) draw from them. The agents' bodies are read from /api/statuses (St.load) where they are
//   shown: the dashboard (dashboard.js) and the agent page (agentpage.js).
// - The shared parts: "更新於 3 小時前" and the overdue mark (a shape and a word, never a colour alone); the body as
//   Markdown with mathematics (render.js), folded after a few lines and opened in place; "要求每 __ 小時更新" for the
//   agent's person (set or clear, saved in place); and the reader's own one-line status (saved in place).
"use strict";
(function () {
  var A = window.Asterism, rail = document.getElementById("rail");
  if (!A || !rail) return;
  var t = A.t, make = A.make;
  var SLUG = rail.dataset.slug, API = "/" + encodeURIComponent(SLUG) + "/api/";
  var LANG = document.documentElement.lang || undefined, EVERY_MS = 4000;
  var St = A.statuses = {data: null, last: "", listeners: [], opened: {}, writing: null};
  St.onChange = function (fn) { St.listeners.push(fn); };
  function changed() { St.listeners.forEach(function (fn) { fn(St.data); }); }

  // ------------------------------------------------------------------ the data (bodies)

  St.agent = function (name) {
    return ((St.data && St.data.agents) || []).filter(function (x) { return x.agent === name; })[0] || null;
  };
  // Read /api/statuses again; listeners hear of it only when it changed (`force`: always).
  St.load = async function (force) {
    var r = await A.request(API + "statuses");
    if (!r.ok) return;
    var raw = JSON.stringify(r.data);
    if (raw === St.last && !force) return;
    St.last = raw;
    St.data = r.data;
    changed();
  };
  // Start reading it every few seconds (the pages that show bodies).
  St.follow = function () {
    St.load(true);
    setInterval(function () { St.load(false); }, EVERY_MS);
  };

  // ------------------------------------------------------------------ times and marks

  // How long ago, in the reader's words ("3 小時前"); a date beyond a week.
  var rtf = window.Intl && Intl.RelativeTimeFormat ? new Intl.RelativeTimeFormat(LANG, {numeric: "auto"}) : null;
  St.ago = function (iso) {
    var d = new Date(iso);
    if (!iso || isNaN(d.getTime())) return "";
    var s = (d.getTime() - Date.now()) / 1000, a = Math.abs(s);
    if (!rtf || a >= 7 * 86400) return d.toLocaleDateString(LANG, {month: "long", day: "numeric"});
    if (a < 60) return rtf.format(0, "second");
    if (a < 3600) return rtf.format(Math.round(s / 60), "minute");
    if (a < 86400) return rtf.format(Math.round(s / 3600), "hour");
    return rtf.format(Math.round(s / 86400), "day");
  };
  St.timeEl = function (iso) {
    var el = make("time", "", St.ago(iso));
    el.dateTime = iso;
    el.title = new Date(iso).toLocaleString(LANG);
    return el;
  };
  // The overdue mark: a shape (app.css: .overdue) and a word, never a colour alone.
  St.overdueMark = function () {
    var m = make("span", "tag overdue", t("st.overdue"));
    m.title = t("st.overdue_hint");
    return m;
  };
  // "更新於 3 小時前" and the overdue mark, for a status {at, overdue}; null when there is neither.
  St.updated = function (st, cls) {
    var box = make("span", "st-updated" + (cls ? " " + cls : ""));
    if (!st) return null;
    if (st.at) box.append(t("st.updated") + " ", St.timeEl(st.at));
    if (st.overdue) box.appendChild(St.overdueMark());
    return box.childNodes.length ? box : null;
  };

  // The body, rendered as Markdown with mathematics (render.js), folded after a few lines; "顯示全部" opens it in place
  // (remembered by `key` while the page is open).
  St.body = function (text, key) {
    var box = make("div", "st-bodytext");
    if (!text) return box;
    var shown = A.renderText ? A.renderText(text) : make("div", "text", text);
    shown.classList.add("st-md");
    if (A.paths) A.paths.scan(shown);
    if (!St.opened[key]) shown.classList.add("folded");
    box.appendChild(shown);
    requestAnimationFrame(function () {
      if (St.opened[key] || !shown.isConnected || shown.scrollHeight <= shown.clientHeight + 1) return;
      var more = A.button("btn tt-more", t("ag.more"), function () {
        St.opened[key] = true;
        shown.classList.remove("folded");
        more.remove();
      });
      more.dataset.key = "more:" + key;
      box.appendChild(more);
    });
    return box;
  };

  // ------------------------------------------------------------------ asking for updates (the agent's person)

  // "要求每 [n] 小時更新" for the agent `st` ({agent, update_every_h}): the hours saved in place, or cleared. `done(r)`
  // after the server answered.
  St.everyControl = function (st, done) {
    var form = make("form", "st-every"), out = make("span", "out");
    form.noValidate = true;
    out.setAttribute("aria-live", "polite");
    var n = make("input");
    n.type = "number";
    n.min = "1";
    n.max = "168";
    n.step = "1";
    n.inputMode = "numeric";
    n.className = "st-every-n";
    n.value = st.update_every_h ? String(st.update_every_h) : "";
    n.dataset.key = "every:" + st.agent;
    n.setAttribute("aria-label", t("st.every_label", {name: st.agent}));
    var words = t("st.every_form").split("{n}"), line = make("span", "st-every-line");
    line.append(words[0] || "", n, words[1] || "");
    var save = make("button", "btn", t("st.every_set"));
    save.dataset.key = "every-set:" + st.agent;
    form.append(line, save);
    async function send(hours) {
      out.textContent = "";
      var r = await A.request(API + "agents/" + encodeURIComponent(st.agent) + "/update-every", null, {hours: hours});
      if (!r.ok) { out.textContent = A.refusal("st.refused", r.data); return; }
      if (done) done(r);
    }
    if (st.update_every_h) {
      var clear = A.button("btn quiet", t("st.every_clear"), function () { send(null); });
      clear.dataset.key = "every-clear:" + st.agent;
      form.appendChild(clear);
    }
    form.appendChild(out);
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var v = n.value.trim();
      if (!v) { send(null); return; }
      if (!(/^\d+$/.test(v) && +v >= 1 && +v <= 168)) { out.textContent = t("st.every_bad"); n.focus(); return; }
      send(+v);
    });
    return form;
  };

  // ------------------------------------------------------------------ the reader's own status

  // The reader's own one-line status, saved in place: the line (or "設定狀態" when there is none), which turns into an
  // input; Enter saves, Escape gives up. `done()` after it was saved.
  St.mine = function (title, done) {
    var box = make("div", "st-mine");
    if (St.writing === null) {
      var b = A.button("st-mine-btn" + (title ? "" : " dim"), title || t("st.set"), function () {
        St.writing = title || "";
        changed();
      });
      b.dataset.key = "st-mine";
      b.title = t("st.edit_hint");
      box.appendChild(b);
      return box;
    }
    var form = make("form", "st-mine-form"), input = make("input"), out = make("span", "out");
    out.setAttribute("aria-live", "polite");
    input.maxLength = 200;
    input.value = St.writing;
    input.placeholder = t("st.mine_hint");
    input.setAttribute("aria-label", t("st.mine_label"));
    input.dataset.key = "st-mine-input";
    input.addEventListener("input", function () { St.writing = input.value; });
    form.append(input, out);
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var r = await A.request(API + "me/status", null, {title: input.value});
      if (!r.ok) { out.textContent = A.refusal("st.refused", r.data); return; }
      St.writing = null;
      if (done) done(r);
      changed();
    });
    input.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); St.writing = null; changed(); }
    });
    setTimeout(function () { if (input.isConnected && document.activeElement !== input) input.focus(); }, 0);
    box.appendChild(form);
    return box;
  };
  St.busy = function () { return St.writing !== null; };
})();
