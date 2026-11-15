// Files mode, the tab strip (#file-tabs) and the document (#file-view), Asterism.viewer.
// The strip says what is open; the explorer chooses. One tab per open file (its name, the full path as its title, a
// close control; a middle click also closes); it scrolls sideways and never wraps; the arrow keys move between tabs
// and Delete closes one. At its far right: the view switch (#view-switch: rendered, source, or source on the left with
// the rendering on the right; what makes no sense for the file is disabled) and "open on GitHub". The tabs, the active
// one and the view chosen per kind of file are kept in localStorage; the address names the active file.
// A file is read from GET /api/files/raw/<path> and shown by kind: Markdown rendered (render.js) in a reading column,
// text as source with line numbers (Lean and TeX highlighted by highlight.js), pictures as pictures (an SVG too, never
// inlined), a PDF in the browser's own viewer in a frame, anything else as one sentence and a link.
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("files"), E = A && A.explorer;
  if (!A || !root || !E) return;
  var t = A.t, make = A.make;
  var SLUG = root.dataset.slug, CAN_MANAGE = !!root.dataset.canManage;
  var TABS_KEY = "asterism-files:" + SLUG, VIEW_KEY = "asterism-files-view";
  var SLOW_MS = 500, MAX_BYTES = Number(root.dataset.maxBytes) || Infinity;
  var el = {tabs: document.getElementById("file-tabs"), view: document.getElementById("file-view"),
            sw: document.getElementById("view-switch"), github: document.getElementById("file-github")};
  var MODES = {markdown: ["rendered", "source", "split"], text: ["source"], image: ["rendered"], pdf: ["rendered"]};
  var PICTURES = /\.(?:png|jpe?g|gif|webp|svg)$/i, MARKDOWN = /\.(?:md|markdown)$/i, PDF = /\.pdf$/i;

  var V = A.viewer = {};
  var tabs = [];                 // {path, status: idle|loading|ok|gone|too_large|unavailable|error, kind, text, code, scroll}
  var active = null;
  var views = A.store.get(VIEW_KEY, {}) || {};

  function nameOf(path) { return path.slice(path.lastIndexOf("/") + 1); }
  function find(path) { for (var i = 0; i < tabs.length; i++) if (tabs[i].path === path) return tabs[i]; return null; }
  function tabFor(path) { return {path: path, status: "idle", kind: null, text: null}; }
  function save() { A.store.set(TABS_KEY, {tabs: tabs.map(function (x) { return x.path; }), active: active}); }

  // ------------------------------------------------------------------ opening and closing

  V.open = function (path) {
    if (!A.splitPath(path)) return;
    if (!find(path)) tabs.push(tabFor(path));
    activate(path, true);
  };

  function activate(path, focusTab) {
    var before = find(active);
    if (before && before !== find(path)) before.scroll = scroller() ? scroller().scrollTop : 0;
    active = path;
    save();
    var where = path ? A.fileHref(SLUG, path) : A.fileHref(SLUG, "").replace(/\/$/, "");
    if (window.location.pathname !== where) history.replaceState(null, "", where);
    E.setCurrent(path);
    drawTabs(focusTab);
    var tab = find(path);
    if (tab && (tab.status === "idle")) load(tab); else draw();
  }

  function close(path) {
    var i = tabs.indexOf(find(path));
    if (i < 0) return;
    tabs.splice(i, 1);
    var next = path === active ? (tabs[i] || tabs[i - 1] || null) : find(active);
    var hadFocus = el.tabs.contains(document.activeElement);
    activate(next ? next.path : null, false);
    if (hadFocus) {
      var b = next && tabButton(next.path);
      (b || el.view).focus();
    }
  }

  // ------------------------------------------------------------------ the strip

  function tabButton(path) {
    var w = el.tabs.querySelector('.tab[data-path="' + path.replace(/["\\]/g, "\\$&") + '"]');
    return w && w.querySelector("[role=tab]");
  }

  function drawTabs(focusTab) {
    el.tabs.textContent = "";
    tabs.forEach(function (x) {
      var wrap = make("div", "tab" + (x.status === "gone" ? " gone" : ""));
      wrap.dataset.path = x.path;
      wrap.setAttribute("role", "presentation");
      var b = A.button("tab-btn", null, function () { activate(x.path, true); });
      b.setAttribute("role", "tab");
      b.id = "tab-" + tabs.indexOf(x);
      b.setAttribute("aria-selected", String(x.path === active));
      b.setAttribute("aria-keyshortcuts", "Delete");
      b.tabIndex = x.path === active ? 0 : -1;
      b.title = x.path;
      b.appendChild(make("span", "tab-name", x.status === "gone" ? t("files.tab_gone", {name: nameOf(x.path)}) : nameOf(x.path)));
      var c = A.button("tab-close", null, function (ev) { ev.stopPropagation(); close(x.path); });
      c.tabIndex = -1;
      c.setAttribute("aria-label", t("files.close_tab", {name: nameOf(x.path)}));
      c.title = t("files.close_tab", {name: nameOf(x.path)});
      c.appendChild(make("span", "cross"));
      c.firstChild.setAttribute("aria-hidden", "true");
      wrap.append(b, c);
      // A middle click closes, as in every tab strip.
      wrap.addEventListener("mousedown", function (ev) { if (ev.button === 1) ev.preventDefault(); });
      wrap.addEventListener("auxclick", function (ev) { if (ev.button === 1) { ev.preventDefault(); close(x.path); } });
      wrap.addEventListener("contextmenu", function (ev) {
        ev.preventDefault();
        A.menu({x: ev.clientX, y: ev.clientY, label: t("files.acts", {name: nameOf(x.path)})}, E.menuItems(x.path, false), b);
      });
      el.tabs.appendChild(wrap);
    });
    var cur = active && tabButton(active);
    if (cur) {
      el.view.setAttribute("aria-labelledby", cur.id);
      cur.parentNode.scrollIntoView({block: "nearest", inline: "nearest"});
      if (focusTab && el.tabs.contains(document.activeElement)) cur.focus();
    } else {
      el.view.removeAttribute("aria-labelledby");
    }
  }

  el.tabs.addEventListener("keydown", function (ev) {
    var b = ev.target.closest("[role=tab]");
    if (!b) return;
    var list = Array.prototype.slice.call(el.tabs.querySelectorAll("[role=tab]")), i = list.indexOf(b), j = null;
    if (ev.key === "ArrowRight") j = (i + 1) % list.length;
    else if (ev.key === "ArrowLeft") j = (i - 1 + list.length) % list.length;
    else if (ev.key === "Home") j = 0;
    else if (ev.key === "End") j = list.length - 1;
    else if (ev.key === "Delete") { ev.preventDefault(); close(b.parentNode.dataset.path); return; }
    else if (ev.key === "ContextMenu" || (ev.key === "F10" && ev.shiftKey)) {
      ev.preventDefault();
      var p = b.parentNode.dataset.path;
      A.menu({anchor: b, label: t("files.acts", {name: nameOf(p)})}, E.menuItems(p, false), b);
      return;
    }
    if (j === null) return;
    ev.preventDefault();
    activate(list[j].parentNode.dataset.path, false);
    var again = tabButton(list[j].parentNode.dataset.path);
    if (again) again.focus();
  });

  // ------------------------------------------------------------------ reading a file

  function kindByName(path) {
    if (MARKDOWN.test(path)) return "markdown";
    if (PICTURES.test(path)) return "image";
    if (PDF.test(path)) return "pdf";
    return null;
  }

  async function load(tab) {
    tab.status = "loading";
    tab.text = null;
    tab.code = null;
    draw();
    // What the listing already says needs no request: a file that is not there, or one too large to be fetched.
    var slash = tab.path.lastIndexOf("/"), entries = await E.list(slash < 0 ? "" : tab.path.slice(0, slash));
    if (entries) {
      var entry = entries.filter(function (x) { return x.path === tab.path; })[0];
      var known = !entry || entry.type !== "file" ? "gone" : entry.size > MAX_BYTES ? "too_large" : null;
      if (known) {
        tab.status = known;
        if (known === "gone") drawTabs(false);
        if (tab.path === active) draw();
        return;
      }
    }
    var url = A.rawUrl(SLUG, tab.path), byName = kindByName(tab.path), r;
    var ctl = new AbortController();
    try {
      // Pictures and PDFs are shown by the browser from the same address; only their state is asked here.
      r = await fetch(url, {method: byName === "image" || byName === "pdf" ? "HEAD" : "GET", credentials: "same-origin",
                            signal: ctl.signal, cache: "no-cache"});
    } catch (err) {
      tab.status = "unavailable";
      if (tab.path === active) draw();
      return;
    }
    if (r.status === 404) tab.status = "gone";
    else if (r.status === 413) tab.status = "too_large";
    else if (r.status === 502) tab.status = "unavailable";
    else if (r.status === 409) tab.status = "not_connected";
    else if (!r.ok) { tab.status = "error"; tab.code = String(r.status); }
    else {
      var ctype = (r.headers.get("content-type") || "").toLowerCase();
      if (ctype.indexOf("text/plain") === 0) {
        tab.kind = byName === "markdown" ? "markdown" : "text";
        tab.text = await r.text();
      } else {
        ctl.abort();
        tab.kind = ctype.indexOf("image/") === 0 ? "image" : ctype === "application/pdf" ? "pdf" : "download";
      }
      tab.status = "ok";
    }
    if (tab.status === "gone") drawTabs(false);
    if (tab.path === active) draw();
  }

  // After a push: the active file is read again, the other tabs when they are next shown, and a file that is gone
  // says so on its tab.
  E.on("commit", async function () {
    tabs.forEach(function (x) { if (x.status !== "loading") x.status = "idle"; });
    var paths = tabs.map(function (x) { return x.path; });
    if (paths.length) {
      var r = await A.request("/" + encodeURIComponent(SLUG) + "/api/files/resolve", null, {paths: paths.slice(0, 200)});
      if (r.ok) tabs.forEach(function (x) { if ((r.data.found || {})[x.path] !== "file") x.status = "gone"; });
    }
    drawTabs(false);
    var cur = find(active);
    if (cur && cur.status === "idle") load(cur); else draw();
  });
  E.on("state", function () { draw(); });

  // ------------------------------------------------------------------ the view switch

  function modesOf(tab) { return tab && tab.status === "ok" ? (MODES[tab.kind] || []) : []; }
  function modeOf(tab) {
    var modes = modesOf(tab), chosen = views[tab && tab.kind];
    return modes.indexOf(chosen) >= 0 ? chosen : modes[0] || null;
  }

  function drawTools(tab) {
    var modes = modesOf(tab), mode = modeOf(tab);
    Array.prototype.forEach.call(el.sw.querySelectorAll("[data-view]"), function (b) {
      var can = modes.indexOf(b.dataset.view) >= 0;
      b.setAttribute("aria-disabled", String(!can));
      b.setAttribute("aria-pressed", String(can && b.dataset.view === mode));
    });
    var gh = tab ? E.githubUrl(tab.path, false) : null;
    if (gh) { el.github.href = gh; el.github.removeAttribute("aria-disabled"); }
    else { el.github.removeAttribute("href"); el.github.setAttribute("aria-disabled", "true"); }
  }

  el.sw.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-view]"), tab = find(active);
    if (!b || b.getAttribute("aria-disabled") === "true" || !tab) return;
    views[tab.kind] = b.dataset.view;
    A.store.set(VIEW_KEY, views);
    draw();
  });

  // ------------------------------------------------------------------ the document

  function scroller() { return el.view.querySelector(".doc-scroll, .code-scroll, .pic-scroll"); }

  var slow = null;
  function draw() {
    var tab = find(active);
    drawTools(tab);
    clearTimeout(slow);
    el.view.textContent = "";
    el.view.className = "file-view";
    if (E.state === "not_connected" || (tab && tab.status === "not_connected")) {
      var box = note(E.message || A.errorText("not_connected"));
      if (CAN_MANAGE) box.appendChild(make("p", "dim", t("files.not_connected_manage")));
      return;
    }
    if (!tab) {
      if (E.state === "away") { note(t("files.unavailable")); return; }
      note(t("files.none_open")).classList.add("quiet");
      return;
    }
    if (tab.status === "loading" || tab.status === "idle") {
      // No spinner unless it takes a while; the area keeps its size meanwhile.
      slow = setTimeout(function () { if (find(active) === tab && tab.status === "loading") note(t("files.loading")).classList.add("quiet"); }, SLOW_MS);
      return;
    }
    if (tab.status === "gone") {
      var gone = note(t("files.gone"));
      gone.appendChild(A.button("btn", t("files.close_this"), function () { close(tab.path); }));
      return;
    }
    if (tab.status === "too_large") {
      var big = note(t("files.too_large")), gh = E.githubUrl(tab.path, false);
      if (gh) big.appendChild(outLink(gh, t("files.open_github")));
      return;
    }
    if (tab.status === "unavailable") {
      var away = note(t("files.unavailable"));
      away.appendChild(A.button("btn", t("files.retry"), function () { load(tab); }));
      return;
    }
    if (tab.status === "error") { note(t("files.error", {code: tab.code})); return; }
    var url = A.rawUrl(SLUG, tab.path), mode = modeOf(tab);
    if (tab.kind === "download") {
      var dl = note(t("files.binary")), a = make("a", "btn", t("files.download"));
      a.href = url;
      a.setAttribute("download", nameOf(tab.path));
      dl.appendChild(a);
      return;
    }
    if (tab.kind === "image") {
      var pic = make("div", "pic-scroll"), img = make("img", "pic");
      img.alt = nameOf(tab.path);
      img.src = url;                       // an SVG too: a picture, never inlined, so nothing in it runs
      img.addEventListener("error", function () { tab.status = "idle"; if (find(active) === tab) load(tab); }, {once: true});
      pic.appendChild(img);
      el.view.appendChild(pic);
      el.view.classList.add("wide");
      return;
    }
    if (tab.kind === "pdf") {
      var frame = make("iframe", "pdf-frame");
      frame.title = nameOf(tab.path);
      frame.src = url;
      el.view.appendChild(frame);
      el.view.classList.add("wide");
      return;
    }
    if (mode === "split") {
      var split = make("div", "split");
      split.append(pane(source(tab)), pane(rendered(tab)));
      el.view.appendChild(split);
    } else if (mode === "rendered") {
      el.view.appendChild(rendered(tab));
    } else {
      el.view.appendChild(source(tab));
    }
    var s = scroller();
    if (s && tab.scroll) s.scrollTop = tab.scroll;
  }

  function note(text) {
    var box = make("div", "file-note");
    box.appendChild(make("p", null, text));
    el.view.appendChild(box);
    return box;
  }
  function outLink(href, text) {
    var a = make("a", "btn", text);
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    return a;
  }
  function pane(child) { var p = make("div", "split-pane"); p.appendChild(child); return p; }

  // Source: line numbers beside the text, no wrapping, sideways scroll inside the block.
  function source(tab) {
    var text = tab.text || "", lines = text.split("\n").length - (/\n$/.test(text) ? 1 : 0);
    var nums = [];
    for (var i = 1; i <= Math.max(lines, 1); i++) nums.push(i);
    var wrap = make("div", "code-scroll"), code = make("div", "code");
    var gutter = make("pre", "code-nums", nums.join("\n"));
    gutter.setAttribute("aria-hidden", "true");
    var pre = make("pre", "code-text"), c = make("code");
    c.appendChild(A.highlight ? A.highlight.code(text, A.highlight.language(tab.path)) : document.createTextNode(text));
    pre.appendChild(c);
    pre.tabIndex = 0;
    pre.setAttribute("aria-label", tab.path);
    code.append(gutter, pre);
    wrap.appendChild(code);
    return wrap;
  }

  // A link or picture written relative to the file: the path in the repository it names, or null when it leaves it.
  function relative(from, href) {
    var raw = String(href).split("#")[0].split("?")[0];
    if (!raw) return null;
    try { raw = decodeURIComponent(raw); } catch (err) { return null; }
    var segs = raw.charAt(0) === "/" ? [] : from.split("/").slice(0, -1);
    var parts = raw.split("/");
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i];
      if (p === "" || p === ".") continue;
      if (p === "..") { if (!segs.length) return null; segs.pop(); continue; }
      segs.push(p);
    }
    var path = segs.join("/");
    return A.splitPath(path) ? path : null;
  }

  function rendered(tab) {
    var doc = A.renderDoc(tab.text || "", {
      link: function (href) {
        if (href.indexOf("//") === 0) return null;
        var path = relative(tab.path, href);
        return path ? {href: A.fileHref(SLUG, path), path: path} : null;
      },
      image: function (src) {
        if (src.indexOf("//") === 0) return null;
        var path = relative(tab.path, src);
        return path ? A.rawUrl(SLUG, path) : null;
      }
    });
    var scroll = make("div", "doc-scroll");
    scroll.appendChild(doc);
    // Links to the repository open in a tab here (a folder opens in the tree); only what exists stays a link.
    var links = Array.prototype.slice.call(doc.querySelectorAll("a[data-path]"));
    if (links.length && A.paths) {
      A.paths.resolve(links.map(function (a) { return a.dataset.path; })).then(function (kinds) {
        links.forEach(function (a) {
          var kind = kinds[a.dataset.path];
          if (kind === "dir") a.dataset.kind = "dir";
          else if (kind !== "file" && E.state === "ok") a.replaceWith.apply(a, Array.prototype.slice.call(a.childNodes));
        });
      });
    }
    doc.addEventListener("click", function (ev) {
      var a = ev.target.closest("a[data-path]");
      if (!a || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button !== 0) return;
      ev.preventDefault();
      if (a.dataset.kind === "dir") E.openFolder(a.dataset.path); else V.open(a.dataset.path);
    });
    if (A.paths) A.paths.scan(doc);
    return scroll;
  }

  // ------------------------------------------------------------------ starting

  var kept = A.store.get(TABS_KEY, {}) || {};
  (Array.isArray(kept.tabs) ? kept.tabs : []).forEach(function (p) {
    if (typeof p === "string" && A.splitPath(p) && !find(p)) tabs.push(tabFor(p));
  });
  var wanted = root.dataset.path;
  if (wanted && A.splitPath(wanted) && !find(wanted)) tabs.push(tabFor(wanted));
  var first = wanted || (typeof kept.active === "string" && find(kept.active) ? kept.active : (tabs[0] && tabs[0].path) || null);
  E.start();
  activate(first, false);
})();
