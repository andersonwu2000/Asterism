// What every page's scripts share (window.Asterism): the message catalogue (body data-msg), a JSON call, a small
// element maker, the two-step confirmation in place, the floating confirmation of what cannot be undone, and the
// theme switch (#theme-toggle). Loaded first on every page.
// This file holds no interface text: all of it comes from the catalogue.
"use strict";
(function () {
  var A = window.Asterism = window.Asterism || {};

  A.parseJSON = function (raw, fallback) {
    try { return JSON.parse(raw); } catch (err) { return fallback; }
  };
  var MSG = A.MSG = A.parseJSON(document.body.dataset.msg || "{}", {});

  A.t = function (key, vars) {
    var s = MSG[key] || key;
    Object.keys(vars || {}).forEach(function (k) { s = s.split("{" + k + "}").join(String(vars[k])); });
    return s;
  };
  A.errorText = function (code) {
    return MSG["error." + code] || (MSG["error.generic"] || "{code}").replace("{code}", code || "?");
  };
  // A refusal in the server's words after the catalogue's prefix, or the catalogue's sentence for its code.
  A.refusal = function (prefixKey, data) {
    return data && data.message ? A.t(prefixKey, {message: data.message}) : A.errorText(data && data.error);
  };

  A.make = function (tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  };
  A.button = function (cls, text, onClick) {
    var b = A.make("button", cls, text);
    b.type = "button";
    if (onClick) b.addEventListener("click", onClick);
    return b;
  };

  // GET when body is undefined, else POST with a JSON body. Answers {ok, status, data}; a network failure is
  // {ok: false, data: {error: "network"}}.
  A.request = async function (url, params, body) {
    var u = new URL(url, window.location.origin);
    Object.keys(params || {}).forEach(function (k) { u.searchParams.set(k, params[k]); });
    var opts = {method: body === undefined ? "GET" : "POST", credentials: "same-origin",
                headers: {"Accept": "application/json"}};
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    var r, data = {};
    try {
      r = await fetch(u, opts);
    } catch (err) {
      return {ok: false, status: 0, data: {error: "network"}};
    }
    try { data = (await r.json()) || {}; } catch (err) { data = {}; }
    return {ok: r.ok, status: r.status, data: data};
  };

  // ------------------------------------------------------------------ two steps, in place
  //
  // An act with a consequence: the first press arms the control, which then says what will happen; a second press
  // does it. Moving away (blur), Escape or a few seconds disarm it. Usage: if (!A.twoStep(button, label)) return;

  var DISARM_MS = 5000;

  function disarm(b) {
    var was = b._armed;
    if (!was) return;
    b._armed = null;
    clearTimeout(was.timer);
    b.removeEventListener("blur", was.onBlur);
    b.removeEventListener("keydown", was.onKey);
    b.textContent = was.text;
    if (was.aria === null) b.removeAttribute("aria-label"); else b.setAttribute("aria-label", was.aria);
    b.classList.remove("armed");
  }

  A.twoStep = function (b, label) {
    if (b._armed) { disarm(b); return true; }
    var was = {text: b.textContent, aria: b.getAttribute("aria-label")};
    was.onBlur = function () { disarm(b); };
    was.onKey = function (ev) { if (ev.key === "Escape") { ev.stopPropagation(); disarm(b); } };
    was.timer = setTimeout(function () { disarm(b); }, DISARM_MS);
    b._armed = was;
    b.textContent = label;
    if (was.aria !== null) b.setAttribute("aria-label", label);
    b.classList.add("armed");
    b.addEventListener("blur", was.onBlur);
    b.addEventListener("keydown", was.onKey);
    if (document.activeElement !== b) b.focus({preventScroll: true});
    return false;
  };
  A.isArmed = function (box) { return !!(box && box.querySelector(".armed")); };

  // ------------------------------------------------------------------ a destruction that cannot be undone floats
  //
  // A centred panel over the dimmed page (a modal <dialog>): one or two sentences on what will be gone, a field
  // where the thing's name is typed, and the one red button, armed only while the name matches. Escape and a click
  // outside close it; focus goes in on open and back to the opener on close; the server's refusal shows inside.
  //   A.gone({title, text, name, button, opener, run: async () => A.request(...), done: function (res) {}})

  var gone = null;

  function goneDialog() {
    if (gone) return gone;
    var d = A.make("dialog", "gone");
    d.setAttribute("closedby", "any");
    d.setAttribute("aria-labelledby", "gone-title");
    d.setAttribute("aria-describedby", "gone-text");
    var form = A.make("form", "gone-form");
    var title = A.make("h2", "gone-title"), text = A.make("p", "gone-text");
    title.id = "gone-title";
    text.id = "gone-text";
    var field = A.make("label", "field"), ask = A.make("span"), input = A.make("input");
    input.autocomplete = "off";
    input.spellcheck = false;
    input.setAttribute("autocapitalize", "off");
    field.append(ask, input);
    var out = A.make("p", "out gone-out");
    out.setAttribute("role", "alert");
    var row = A.make("div", "row gone-row");
    var cancel = A.button("btn", "", function () { d.close(); });
    var go = A.make("button", "btn destruct");
    go.type = "submit";
    row.append(cancel, go);
    form.append(title, text, field, out, row);
    d.appendChild(form);
    document.body.appendChild(d);
    gone = {dialog: d, title: title, text: text, ask: ask, input: input, out: out, cancel: cancel, go: go, opts: null};

    function armed() { return !!gone.opts && input.value === gone.opts.name; }
    input.addEventListener("input", function () { go.disabled = !armed() || gone.running; });
    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      if (!armed() || gone.running) return;
      var opts = gone.opts;
      gone.running = true;
      go.disabled = true;
      out.textContent = "";
      var res;
      try { res = await opts.run(); } finally { gone.running = false; }
      if (res && res.ok) {
        gone.succeeded = true;
        d.close();
        if (opts.done) opts.done(res);
        return;
      }
      out.textContent = A.refusal("gone.refused", res && res.data);
      go.disabled = !armed();
      input.focus();
    });
    // Browsers without closedby: a click on the dialog itself (not its panel) is a click outside.
    if (!("closedBy" in HTMLDialogElement.prototype)) {
      d.addEventListener("click", function (ev) {
        if (ev.target !== d) return;
        var r = d.getBoundingClientRect();
        var inside = r.top <= ev.clientY && ev.clientY <= r.bottom && r.left <= ev.clientX && ev.clientX <= r.right;
        if (!inside) d.close();
      });
    }
    d.addEventListener("close", function () {
      var opts = gone.opts;
      gone.opts = null;
      if (!opts) return;
      var back = opts.opener && opts.opener.isConnected ? opts.opener : null;
      if (gone.succeeded && opts.after && opts.after.isConnected) back = opts.after;
      if (back) back.focus();
    });
    return gone;
  }

  A.gone = function (opts) {
    var g = goneDialog();
    g.opts = opts;
    g.succeeded = false;
    g.running = false;
    g.title.textContent = opts.title;
    g.text.textContent = opts.text;
    g.ask.textContent = A.t("gone.type", {name: opts.name});
    g.input.value = "";
    g.out.textContent = "";
    g.cancel.textContent = A.t("gone.cancel");
    g.go.textContent = opts.button;
    g.go.disabled = true;
    g.dialog.showModal();
    g.input.focus();
  };

  // Put the focus back on the element of `box` with the same data-key after `box` was redrawn.
  A.keepFocus = function (box, redraw) {
    var a = document.activeElement, key = a && box.contains(a) && a.dataset ? a.dataset.key : null;
    redraw();
    if (key) {
      var again = box.querySelector('[data-key="' + key.replace(/["\\]/g, "\\$&") + '"]');
      if (again) again.focus({preventScroll: true});
    }
  };

  // ------------------------------------------------------------------ the theme
  //
  // The head script set data-theme before the first paint (the stored choice, else the system's). The switch
  // stores the reader's choice; without one, the page follows the system as it changes.

  var KEY = "asterism-theme", html = document.documentElement;
  function stored() { try { return localStorage.getItem(KEY); } catch (err) { return null; } }
  function now() { return html.getAttribute("data-theme") === "light" ? "light" : "dark"; }
  function label() {
    var to = now() === "dark" ? "light" : "dark";
    Array.prototype.forEach.call(document.querySelectorAll("#theme-toggle"), function (b) {
      b.textContent = A.t("theme.to_" + to);
      b.setAttribute("aria-label", A.t("theme.to_" + to + "_label"));
    });
  }
  function set(theme) { html.setAttribute("data-theme", theme); label(); }

  document.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("#theme-toggle");
    if (!b) return;
    var to = now() === "dark" ? "light" : "dark";
    try { localStorage.setItem(KEY, to); } catch (err) { /* kept for this page only */ }
    set(to);
  });
  if (window.matchMedia) {
    var light = window.matchMedia("(prefers-color-scheme: light)");
    var follow = function () { if (stored() !== "dark" && stored() !== "light") set(light.matches ? "light" : "dark"); };
    if (light.addEventListener) light.addEventListener("change", follow);
  }
  window.addEventListener("storage", function (ev) {
    if (ev.key === KEY && (ev.newValue === "dark" || ev.newValue === "light")) set(ev.newValue);
  });
  label();
})();
