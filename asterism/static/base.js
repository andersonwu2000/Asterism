// What every page's scripts share (window.Asterism): the message catalogue (body data-msg), a JSON call, a small
// element maker, the two-step confirmation in place, the floating confirmation of what cannot be undone, what the
// browser keeps (A.store), copying, the addresses of the repository's files, the one popup menu (A.menu), the one
// dropdown (A.dropdown, and every [data-dropdown] the server drew), and the theme switch (#theme-toggle). Loaded first
// on every page.
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
  //   items: [{label, run: function () {}} | {label, href} | {label, items: [...]} | {separator: true} |
  //           {heading: text}]; `checked` (true or false) makes an item a check box, with `radio` a choice of one.

  var menu = null;
  var ITEMS = "[role^=menuitem]:not([aria-disabled=true])";

  // The keys every menu shares: the arrows, Home and End move; a letter goes to the next item starting with it.
  // True when the key was one of them.
  A.menuKeys = function (box, ev) {
    var items = Array.prototype.slice.call(box.querySelectorAll(ITEMS));
    var i = items.indexOf(document.activeElement), n = items.length;
    if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
      ev.preventDefault();
      if (n) items[i < 0 ? (ev.key === "ArrowDown" ? 0 : n - 1) : (i + (ev.key === "ArrowDown" ? 1 : n - 1)) % n].focus();
      return true;
    }
    if (ev.key === "Home" || ev.key === "End") {
      ev.preventDefault();
      if (n) items[ev.key === "Home" ? 0 : n - 1].focus();
      return true;
    }
    if (ev.key.length === 1 && /\S/.test(ev.key) && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
      var k = ev.key.toLowerCase();
      for (var j = 0; j < n; j++) {
        var it = items[(i + 1 + j) % n];
        if (it.textContent.trim().toLowerCase().indexOf(k) === 0) { it.focus(); break; }
      }
      return true;
    }
    return false;
  };

  function menuBox() {
    if (menu) return menu;
    var box = A.make("div", "menu");
    box.setAttribute("role", "menu");
    box.tabIndex = -1;
    if (typeof box.showPopover === "function") box.setAttribute("popover", "manual");
    document.body.appendChild(box);
    menu = {box: box, open: false, opener: null, stack: []};
    box.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") {
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
      } else {
        A.menuKeys(box, ev);
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
      if (it.heading !== undefined) {
        var head = A.make("div", "menu-head", it.heading);
        head.setAttribute("role", "presentation");
        box.appendChild(head);
        return;
      }
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
      // An item with `checked` (true or false) is a check box: choosing it runs its act, which turns it over.
      el.setAttribute("role", it.checked === undefined ? "menuitem" : it.radio ? "menuitemradio" : "menuitemcheckbox");
      if (it.checked !== undefined) el.setAttribute("aria-checked", String(!!it.checked));
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
    var first = box.querySelector("[role=menuitemradio][aria-checked=true]") || box.querySelector(ITEMS);
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

  // ------------------------------------------------------------------ the one dropdown
  //
  // Instead of a native <select>: a button with the current choice and a chevron, opening the choices as the one menu
  // (each a menuitemradio, the current one checked and focused): the arrow keys, Home, End and a letter move, Escape
  // closes, and the focus goes back to the button. ArrowDown or ArrowUp on the button opens it too. With a hidden
  // field beside the button (`name`), a form sends the value as it would a select's.
  //   var d = A.dropdown({label, options: [{value, label, group}], value, name, list, onChange: function (value) {}})
  //   d.el (to put in the page), d.value, d.set(value), d.setOptions(options)

  function dropdownOn(b, hidden, opts) {
    var text = b.querySelector(".dropdown-value");
    var d = {el: b.parentNode, button: b, options: opts.options || [], value: ""};
    function find(v) { for (var i = 0; i < d.options.length; i++) if (d.options[i].value === v) return d.options[i]; return null; }
    function show() {
      var o = find(d.value);
      text.textContent = o ? o.label : "";
      if (hidden) hidden.value = d.value;
    }
    d.set = function (v) { d.value = find(v) ? v : (d.options[0] ? d.options[0].value : ""); show(); };
    d.setOptions = function (list) { d.options = list || []; d.set(d.value); };
    d.set(opts.value !== undefined && opts.value !== null ? opts.value : hidden ? hidden.value : "");
    function open() {
      var items = [], group;
      d.options.forEach(function (o) {
        if (o.group && o.group !== group) items.push({heading: o.group});
        group = o.group;
        items.push({label: o.label, radio: true, checked: o.value === d.value, run: function () {
          var was = d.value;
          d.set(o.value);
          if (was !== d.value && opts.onChange) opts.onChange(d.value);
        }});
      });
      A.menu({label: b.getAttribute("aria-label") || "", anchor: b}, items, b);
    }
    b.addEventListener("click", open);
    b.addEventListener("keydown", function (ev) {
      if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
      ev.preventDefault();
      open();
    });
    b._dropdown = d;
    return d;
  }

  A.dropdown = function (opts) {
    var wrap = A.make("span", "dropdown-field"), b = A.button("dropdown");
    b.setAttribute("aria-haspopup", "menu");
    b.setAttribute("aria-expanded", "false");
    if (opts.label) { b.setAttribute("aria-label", opts.label); b.title = opts.label; }
    b.append(A.make("span", "dropdown-value"), A.glyph("chevron"));
    wrap.appendChild(b);
    var hidden = null;
    if (opts.name) {
      hidden = A.make("input");
      hidden.type = "hidden";
      hidden.name = opts.name;
      if (opts.list) hidden.setAttribute("data-list", "");
      wrap.appendChild(hidden);
    }
    return dropdownOn(b, hidden, opts);
  };

  // The dropdowns the server drew (pages.dropdown): their choices are in data-dropdown as [[value, label], ...].
  A.wireDropdowns = function (root) {
    Array.prototype.forEach.call((root || document).querySelectorAll("button[data-dropdown]"), function (b) {
      if (b._dropdown) return;
      var options = (A.parseJSON(b.dataset.dropdown, []) || []).map(function (x) { return {value: x[0], label: x[1]}; });
      dropdownOn(b, b.parentNode.querySelector("input[type=hidden]"), {options: options});
    });
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

  // ------------------------------------------------------------------ a box that floats by its control
  //
  // A popover (the project menu, the pins of a channel, a profile card): shown by its control, closed by Escape, a
  // click outside, the focus leaving it or A.popup.close(); the focus goes into it and back to the control. One at a
  // time. A menu or a dialog opened from inside it does not count as outside.
  //   A.popup.open(box, anchor, {align: "start" | "end", at: {left, right, top, bottom}, focus: element, onClose})

  var pop = null, popShut = null;

  function inside(target) {
    return !!(target && target.closest && (pop.box.contains(target) || target.closest(".menu") || target.closest("dialog")));
  }

  function popPlace() {
    var box = pop.box, r = pop.at || pop.anchor.getBoundingClientRect();
    var w = box.offsetWidth, h = box.offsetHeight, vw = document.documentElement.clientWidth, vh = window.innerHeight;
    var x = pop.align === "end" ? r.right - w : r.left, y = r.bottom + 4;
    if (x + w > vw - 8) x = vw - 8 - w;
    if (y + h > vh - 8) y = Math.max(8, r.top - 4 - h);
    box.style.left = Math.max(8, x) + "px";
    box.style.top = Math.max(8, y) + "px";
  }

  A.popup = {
    open: function (box, anchor, opts) {
      opts = opts || {};
      if (popShut && popShut.by === anchor && Date.now() - popShut.at < 600) { popShut = null; return false; }
      A.popup.close(false);
      pop = {box: box, anchor: anchor, at: opts.at || null, align: opts.align, onClose: opts.onClose};
      box.hidden = false;
      box.classList.add("shown");
      if (box.hasAttribute("popover")) {
        try { box.showPopover(); } catch (err) { /* shown by the class */ }
      }
      if (anchor.hasAttribute && anchor.hasAttribute("aria-expanded")) anchor.setAttribute("aria-expanded", "true");
      popPlace();
      var first = opts.focus || box.querySelector("a[href], button:not([disabled]), input, select, textarea, [tabindex]");
      (first || box).focus({preventScroll: true});
      return true;
    },
    close: function (refocus) {
      if (!pop) return;
      var was = pop;
      pop = null;
      if (was.box.hasAttribute("popover")) {
        try { was.box.hidePopover(); } catch (err) { /* already hidden */ }
      }
      was.box.classList.remove("shown");
      was.box.hidden = true;
      var a = was.anchor;
      if (a.hasAttribute && a.hasAttribute("aria-expanded")) a.setAttribute("aria-expanded", "false");
      var hadFocus = was.box.contains(document.activeElement) || document.activeElement === document.body;
      if ((refocus || hadFocus) && a.isConnected) a.focus({preventScroll: true});
      if (was.onClose) was.onClose();
    },
    isOpen: function (box) { return !!pop && (!box || pop.box === box); },
    place: function () { if (pop) popPlace(); }
  };

  document.addEventListener("pointerdown", function (ev) {
    if (!pop || inside(ev.target)) return;
    // A press on the control that opened it closes it, and the click that follows does not open it again.
    popShut = pop.anchor.contains && pop.anchor.contains(ev.target) ? {by: pop.anchor, at: Date.now()} : null;
    A.popup.close(false);
  }, true);
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape" || !pop || ev.defaultPrevented || !pop.box.contains(document.activeElement)) return;
    ev.preventDefault();
    ev.stopPropagation();
    A.popup.close(true);
  }, true);
  document.addEventListener("focusout", function (ev) {
    if (!pop || !pop.box.contains(ev.target)) return;
    var next = ev.relatedTarget;
    if (next && !inside(next)) A.popup.close(false);
  });
  window.addEventListener("resize", function () { if (pop) A.popup.close(false); });

  // A line drawing of the page's glyph set (the server puts it in <template id="glyphs">), or an empty span.
  A.glyph = function (name) {
    var set = document.getElementById("glyphs");
    var g = set && set.content.querySelector('[data-glyph="' + name + '"]');
    return g ? g.cloneNode(true) : A.make("span");
  };

  // ------------------------------------------------------------------ the kind of a file, as a mark
  //
  // v1's kind marks (web/src/components/glyphs.tsx, KIND_MARKS), on its 10x11 box, stroked in the current ink:
  // a folder; md, prose lines; tex, the same lines centred; lean, a chevron; pdf, a folded corner; image, a landscape
  // frame; anything else, a blank page. Decorative: the name beside it says the kind. Used by the explorer's rows and
  // the tabs of files mode.
  var SVG_NS = "http://www.w3.org/2000/svg";
  var PAGE = [["rect", {x: "1", y: "1", width: "8", height: "9", rx: "1", "stroke-width": "1"}]];
  var KIND_MARKS = {
    folder: [["path", {d: "M1 9.5V2h2.7l1 1.3H9v6.2z", "stroke-width": "1", "stroke-linejoin": "round"}]],
    md: PAGE.concat([["path", {d: "M3 4.25h4M3 6.75h2.5", "stroke-width": "0.9", "stroke-linecap": "round", opacity: "0.55"}]]),
    tex: PAGE.concat([["path", {d: "M2.7 4.25h4.6M4.3 6.75h1.4", "stroke-width": "0.9", "stroke-linecap": "round", opacity: "0.55"}]]),
    lean: PAGE.concat([["path", {d: "M4 4.1l1.6 1.4L4 6.9", "stroke-width": "0.9", "stroke-linecap": "round",
                                 "stroke-linejoin": "round", opacity: "0.75"}]]),
    pdf: [["path", {d: "M1 10V1h4.7L9 4.2V10z", "stroke-width": "1", "stroke-linejoin": "round"}],
          ["path", {d: "M5.7 1v3.2H9", "stroke-width": "0.9", "stroke-linejoin": "round", opacity: "0.55"}]],
    image: [["rect", {x: "1", y: "2", width: "8", height: "7", rx: "1", "stroke-width": "1"}],
            ["circle", {cx: "3.4", cy: "4.4", r: "0.8", fill: "currentColor", stroke: "none", opacity: "0.55"}],
            ["path", {d: "M1.4 8.3l2.4-2.4 1.6 1.5 1.2-1.1L8.6 7.6", "stroke-width": "0.9", "stroke-linecap": "round",
                      "stroke-linejoin": "round", opacity: "0.55"}]],
    other: PAGE
  };
  // The kind of a path, as v1 named it: a folder, or by the file's extension.
  A.kindOf = function (path, folder) {
    if (folder) return "folder";
    var m = /\.([A-Za-z0-9]+)$/.exec(path || ""), ext = m ? m[1].toLowerCase() : "";
    if (ext === "md" || ext === "lean" || ext === "tex" || ext === "pdf") return ext;
    return /^(?:png|jpe?g|gif|webp|svg)$/.test(ext) ? "image" : "other";
  };
  A.kindMark = function (path, folder) {
    var svg = document.createElementNS(SVG_NS, "svg"), kind = A.kindOf(path, folder);
    svg.setAttribute("class", "kind-mark kind-" + kind);
    svg.setAttribute("viewBox", "0 0 10 11");
    svg.setAttribute("width", "10");
    svg.setAttribute("height", "11");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    KIND_MARKS[kind].forEach(function (part) {
      var el = document.createElementNS(SVG_NS, part[0]);
      Object.keys(part[1]).forEach(function (k) { el.setAttribute(k, part[1][k]); });
      svg.appendChild(el);
    });
    return svg;
  };

  // ------------------------------------------------------------------ invitations (the project menu, "my agents")

  // A line with the text to copy and its copy button.
  A.copyLine = function (text) {
    var line = A.make("div", "copy-line");
    var code = A.make("code", null, text);
    var button = A.button("btn", A.t("invite.copy"), async function () {
      // A blocker may refuse the write: then say so; the text beside stays selectable to copy by hand.
      var ok = false;
      try { ok = await A.copy(text); } catch (err) { ok = false; }
      button.textContent = ok ? A.t("invite.copied") : A.t("invite.copy_failed");
      setTimeout(function () { button.textContent = A.t("invite.copy"); }, ok ? 2000 : 5000);
    });
    button.setAttribute("aria-live", "polite");
    line.append(code, button);
    return line;
  };

  // What an agent invitation answers: the sentence for the agent, and the commands to set up a computer oneself.
  var SYSTEMS = ["macos-linux", "windows"], PRODUCTS = ["claude-code", "codex"], invites = 0;
  A.showInvite = function (box, data) {
    var make = A.make, t = A.t;
    invites += 1;
    box.replaceChildren();
    box.append(make("p", null, t("invite.say")), A.copyLine(data.say));
    var until = new Date(Date.now() + data.expires_in * 1000);
    var time = until.toLocaleTimeString(document.documentElement.lang || undefined, {hour: "2-digit", minute: "2-digit"});
    box.append(make("p", "muted", t("invite.expires", {time: time})));
    if (!data.program || !data.program.available) {
      box.append(make("p", "muted", t("invite.unavailable")));
      return;
    }
    box.append(make("p", null, t("invite.self")));
    SYSTEMS.forEach(function (system) {
      var group = make("fieldset");
      group.append(make("legend", null, t("invite.system." + system)));
      var choices = make("div"), lines = {};
      PRODUCTS.forEach(function (product, i) {
        var label = make("label");
        var radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "invite-product-" + system + "-" + invites;
        radio.value = product;
        radio.checked = i === 0;
        radio.addEventListener("change", function () {
          PRODUCTS.forEach(function (p) { lines[p].hidden = p !== product; });
        });
        label.append(radio, " " + t("invite.product." + product));
        choices.append(label);
      });
      group.append(choices);
      PRODUCTS.forEach(function (product, i) {
        lines[product] = A.copyLine(data.commands[system][product]);
        lines[product].hidden = i !== 0;
        group.append(lines[product]);
      });
      box.append(group);
    });
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
  A.wireDropdowns(document);
})();
