// What every page's scripts share (window.Asterism): the message catalogue (body data-msg), a JSON call, a small
// element maker, the two-step confirmation in place, and the theme switch (#theme-toggle). Loaded first on every page.
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
