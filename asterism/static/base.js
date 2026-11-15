// What every page's scripts share (window.Asterism): the message catalogue (body data-msg), a JSON call, a small
// element maker, the two-step confirmation in place, the floating confirmation of what cannot be undone, what the
// browser keeps (A.store), copying, the addresses of the repository's files, the one popup menu (A.menu), and the
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
  //
  // A POST is done once however often it is sent: it carries an Idempotency-Key, and while the server cannot be
  // reached (a network failure, or a proxy's 502/503/504 without the server's error) it is sent again with the same
  // key, pausing 1, 2, 4 ... seconds, for at most RETRY_MS. If no answer came, the key is kept with the address and
  // body for KEY_KEPT_MS, so that repeating the same act uses it; any answer from the server forgets it.
  var RETRY_MS = 20000, KEY_KEPT_MS = 3600000;
  var unanswered = {};          // address + body -> {key, at}

  function newKey() {
    var bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    return Array.prototype.map.call(bytes, function (b) { return (b < 16 ? "0" : "") + b.toString(16); }).join("");
  }

  function keyFor(what) {
    var now = Date.now();
    Object.keys(unanswered).forEach(function (w) { if (now - unanswered[w].at >= KEY_KEPT_MS) delete unanswered[w]; });
    return unanswered[what] ? unanswered[what].key : newKey();
  }

  function sleep(ms) {
    return new Promise(function (done) { setTimeout(done, ms); });
  }

  async function attempt(u, opts) {
    var r, data = {};
    try {
      r = await fetch(u, opts);
    } catch (err) {
      return {ok: false, status: 0, data: {error: "network"}, lost: true};
    }
    try { data = (await r.json()) || {}; } catch (err) { data = {}; }
    var proxy = (r.status === 502 || r.status === 503 || r.status === 504) && !data.error;
    return {ok: r.ok, status: r.status, data: data, lost: proxy};
  }

  A.request = async function (url, params, body) {
    var u = new URL(url, window.location.origin);
    Object.keys(params || {}).forEach(function (k) { u.searchParams.set(k, params[k]); });
    var opts = {method: body === undefined ? "GET" : "POST", credentials: "same-origin",
                headers: {"Accept": "application/json"}};
    if (body === undefined) {
      var got = await attempt(u, opts);
      return {ok: got.ok, status: got.status, data: got.data};
    }
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
    var what = u.href + "\n" + opts.body;
    var key = opts.headers["Idempotency-Key"] = keyFor(what);
    var first = Date.now(), pause = 1000, out;
    for (;;) {
      out = await attempt(u, opts);
      var left = RETRY_MS - (Date.now() - first);
      if (!out.lost || left <= 0) break;
      await sleep(Math.min(pause, left));
      pause *= 2;
    }
    if (out.lost) unanswered[what] = {key: key, at: Date.now()};
    else delete unanswered[what];
    return {ok: out.ok, status: out.status, data: out.data};
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

  // ------------------------------------------------------------------ small shared things

  // What the browser keeps for this reader (localStorage, as JSON). It may be refused or full: then nothing is kept
  // and the page goes on.
  A.store = {
    get: function (key, fallback) {
      try {
        var raw = localStorage.getItem(key);
        return raw === null ? fallback : A.parseJSON(raw, fallback);
      } catch (err) { return fallback; }
    },
    set: function (key, value) {
      try { localStorage.setItem(key, JSON.stringify(value)); } catch (err) { /* kept for this page only */ }
    },
    take: function (key) {
      var v = A.store.get(key, null);
      try { localStorage.removeItem(key); } catch (err) { /* nothing kept */ }
      return v;
    }
  };

  // Copy a text; true when it was copied. A blocker may refuse the write.
  A.copy = async function (text) {
    if (navigator.clipboard && window.isSecureContext) {
      try { await navigator.clipboard.writeText(text); return true; } catch (err) { /* fall back below */ }
    }
    var area = A.make("textarea", null, text);
    area.setAttribute("readonly", "");
    area.style.position = "fixed"; area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
    area.remove();
    return ok;
  };

  // ------------------------------------------------------------------ paths of the repository
  //
  // A path is folder and file names joined by "/", without empty, "." or ".." names, backslashes or control
  // characters (the server's rule). Addresses built from a path go through the URL API, one encoded name at a time.

  A.splitPath = function (raw) {
    if (typeof raw !== "string" || !raw || raw.length > 4096 || /[\\\u0000-\u001f\u007f-\u009f]/.test(raw)) return null;
    var segs = raw.split("/");
    for (var i = 0; i < segs.length; i++) if (segs[i] === "" || segs[i] === "." || segs[i] === "..") return null;
    return segs;
  };

  function under(slug, base, path) {
    var u = new URL("/", window.location.origin);
    u.pathname = "/" + encodeURIComponent(slug) + base + (path ? path.split("/").map(encodeURIComponent).join("/") : "");
    return u;
  }
  // The address of a file in files mode, and of its bytes.
  A.fileHref = function (slug, path) { return under(slug, "/files/", path).pathname; };
  A.rawUrl = function (slug, path) { return under(slug, "/api/files/raw/", path).pathname; };
  // The file or folder on GitHub, or null when the project's address is not a GitHub repository.
  A.githubUrl = function (repo, ref, path, folder) {
    var u;
    try { u = new URL(repo); } catch (err) { return null; }
    if (u.protocol !== "https:" || u.hostname.toLowerCase() !== "github.com") return null;
    var segs = u.pathname.replace(/\/+$/, "").replace(/\.git$/, "").split("/").filter(Boolean);
    if (segs.length !== 2) return null;
    var out = new URL("https://github.com/");
    var rest = path ? [folder ? "tree" : "blob", ref || "HEAD"].concat(path.split("/")) : [];
    out.pathname = "/" + segs.concat(rest).map(function (s, i) { return i < 2 ? s : encodeURIComponent(s); }).join("/");
    return out.href;
  };

  // ------------------------------------------------------------------ a menu
  //
  // One popup menu for the page: a list of commands (buttons) and destinations (links) moved through with the arrow
  // keys, Home and End. It opens at a point (a right click) or under an element (its control, or a focused row),
  // closes on Escape, Tab, a click outside or a choice, and gives the focus back to what opened it. An item with
  // `items` opens a second list in its place, with a way back (ArrowLeft or the first item).
  //   A.menu({label, x, y} | {label, anchor}, items, opener)
  //   items: [{label, run: function () {}} | {label, href} | {label, items: [...]} | {separator: true}]

  var menu = null;

  function menuBox() {
    if (menu) return menu;
    var box = A.make("div", "menu");
    box.setAttribute("role", "menu");
    box.tabIndex = -1;
    if (typeof box.showPopover === "function") box.setAttribute("popover", "manual");
    document.body.appendChild(box);
    menu = {box: box, open: false, opener: null, stack: []};
    box.addEventListener("keydown", function (ev) {
      var items = Array.prototype.slice.call(box.querySelectorAll("[role=menuitem]:not([aria-disabled=true])"));
      var i = items.indexOf(document.activeElement);
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        var n = items.length;
        if (n) items[i < 0 ? (ev.key === "ArrowDown" ? 0 : n - 1) : (i + (ev.key === "ArrowDown" ? 1 : n - 1)) % n].focus();
      } else if (ev.key === "Home" || ev.key === "End") {
        ev.preventDefault();
        if (items.length) items[ev.key === "Home" ? 0 : items.length - 1].focus();
      } else if (ev.key === "Escape") {
        ev.preventDefault();
        ev.stopPropagation();
        if (menu.stack.length > 1) back(); else closeMenu(true);
      } else if (ev.key === "ArrowLeft" && menu.stack.length > 1) {
        ev.preventDefault();
        back();
      } else if (ev.key === "ArrowRight" && document.activeElement && document.activeElement.getAttribute("aria-haspopup")) {
        ev.preventDefault();
        document.activeElement.click();
      } else if (ev.key === "Tab") {
        closeMenu(false);
      } else if (ev.key.length === 1 && /\S/.test(ev.key)) {        // type a letter: the next item starting with it
        var k = ev.key.toLowerCase(), from = i + 1;
        for (var j = 0; j < items.length; j++) {
          var it = items[(from + j) % items.length];
          if (it.textContent.trim().toLowerCase().indexOf(k) === 0) { it.focus(); break; }
        }
      }
    });
    document.addEventListener("pointerdown", function (ev) {
      if (!menu.open || box.contains(ev.target)) return;
      // A press on the control that opened it closes it, and the click that follows does not open it again.
      menu.shut = menu.opener && menu.opener.contains && menu.opener.contains(ev.target) ? {by: menu.opener, at: Date.now()} : null;
      closeMenu(false);
    }, true);
    window.addEventListener("blur", function () { if (menu.open) closeMenu(false); });
    window.addEventListener("resize", function () { if (menu.open) closeMenu(false); });
    return menu;
  }

  function closeMenu(refocus) {
    if (!menu || !menu.open) return;
    menu.open = false;
    var hadFocus = menu.box.contains(document.activeElement);
    if (menu.box.hasAttribute("popover")) {
      try { menu.box.hidePopover(); } catch (err) { /* already hidden */ }
    }
    menu.box.classList.remove("shown");
    var opener = menu.opener;
    if (opener && opener.setAttribute && opener.hasAttribute("aria-expanded")) opener.setAttribute("aria-expanded", "false");
    menu.opener = null;
    if ((refocus || hadFocus) && opener && opener.isConnected) opener.focus({preventScroll: true});
  }
  A.closeMenu = closeMenu;

  function fill(list) {
    var box = menu.box;
    box.textContent = "";
    list.forEach(function (it) {
      if (it.separator) {
        var sep = A.make("div", "menu-sep");
        sep.setAttribute("role", "separator");
        box.appendChild(sep);
        return;
      }
      var el;
      if (it.href) {
        el = A.make("a", "menu-item", it.label);
        el.href = it.href;
        if (it.external) { el.target = "_blank"; el.rel = "noopener noreferrer"; }
        el.addEventListener("click", function () { closeMenu(false); });
      } else {
        el = A.button("menu-item" + (it.back ? " menu-back" : ""), it.label, function () {
          if (it.disabled) return;
          if (it.back) { back(); return; }
          if (it.items) { open(it.items, it.label); return; }
          var run = it.run;
          closeMenu(true);
          if (run) run();
        });
      }
      el.setAttribute("role", "menuitem");
      el.tabIndex = -1;
      if (it.disabled) el.setAttribute("aria-disabled", "true");
      if (it.items) {
        el.setAttribute("aria-haspopup", "menu");
        el.appendChild(A.make("span", "menu-more"));
        el.lastChild.setAttribute("aria-hidden", "true");
      }
      if (it.mono) el.classList.add("mono");
      box.appendChild(el);
    });
    var first = box.querySelector("[role=menuitem]:not([aria-disabled=true])");
    (first || box).focus({preventScroll: true});
  }

  function open(list, label) {
    menu.stack.push(list);
    fill([{label: A.t("files.back"), back: true}, {separator: true}].concat(list));
    if (label) menu.box.setAttribute("aria-label", label);
    place();
  }
  function back() {
    menu.stack.pop();
    menu.box.setAttribute("aria-label", menu.label);
    fill(menu.stack[menu.stack.length - 1]);
    place();
  }

  function place() {
    var box = menu.box, at = menu.at, w = box.offsetWidth, h = box.offsetHeight;
    var vw = document.documentElement.clientWidth, vh = window.innerHeight, x = at.x, y = at.y;
    if (x + w > vw - 8) x = Math.max(8, (at.right !== undefined ? at.right : vw) - w);
    if (y + h > vh - 8) y = Math.max(8, (at.top !== undefined ? at.top : y) - h);
    box.style.left = Math.max(8, x) + "px";
    box.style.top = Math.max(8, y) + "px";
  }

  A.menu = function (where, items, opener) {
    var m = menuBox();
    if (m.shut && m.shut.by === opener && Date.now() - m.shut.at < 600) { m.shut = null; return; }
    if (m.open) closeMenu(false);
    m.opener = opener || document.activeElement;
    m.label = where.label || "";
    m.box.setAttribute("aria-label", m.label);
    if (where.anchor) {
      var r = where.anchor.getBoundingClientRect();
      m.at = {x: r.left, y: r.bottom + 2, right: r.right, top: r.top - 2};
    } else {
      m.at = {x: where.x, y: where.y};
    }
    m.stack = [items];
    m.open = true;
    m.box.style.left = "0px";
    m.box.style.top = "0px";
    m.box.classList.add("shown");
    if (m.box.hasAttribute("popover")) {
      try { m.box.showPopover(); } catch (err) { /* shown by the class */ }
    }
    if (m.opener && m.opener.hasAttribute && m.opener.hasAttribute("aria-expanded")) m.opener.setAttribute("aria-expanded", "true");
    fill(items);
    place();
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
