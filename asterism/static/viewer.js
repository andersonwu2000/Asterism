// Files mode, the tab strip (#file-tabs) and the document (#file-view), Asterism.viewer.
// The strip says what is open; the explorer chooses. Each source (the repository, repo.js, or the local folder,
// local.js) keeps its own tabs and its own active tab: the strip and the document show those of the source the
// explorer shows, and switching the source switches them (a file opened from the other source turns the explorer
// to it). One tab per open file (its name, the full path as its title, a close control; a middle click also
// closes); two tabs of the same name also show, quietly after it, as much of their folder as tells them apart. The
// strip scrolls sideways (the wheel scrolls it too) and never wraps; an edge with more tabs beyond it fades out. The
// arrow keys move between tabs and Delete closes one. A tab with unsaved changes carries a filled disc after its name
// and says so in its name for assistive technology; closing it, or leaving the page, asks first.
// Opening a file shows it in the current tab (a preview: what was there goes) unless that tab has unsaved changes,
// or the file is asked for in a new tab (the explorer's "open in a new tab", a middle click, Ctrl/Cmd+click, a row
// dragged onto the strip, dropped where its marker shows); a file already open only has its tab chosen. Tabs are
// moved by dragging them along the strip.
// At the strip's far right: for a .tex file next to a PDF of the same name, "open PDF" (#file-pdf, in a new tab);
// the view switch (#view-switch: rendered, source, or source on the left with the rendering on the right; what makes
// no sense for the file is disabled) and one more control: "open on GitHub" (#file-github) for a file of the
// repository, save (#file-save, also Ctrl+S / Cmd+S) for a local one and for a file of the repository being edited.
// Before them, for a text file of the repository: 編輯 (#file-edit, pressed while editing) for a reader who may save
// there in their own GitHub name (repo.js canWrite), or a quiet link to their settings (#file-auth) when that needs
// their GitHub authorization.
// Below 900 px, while the source shown has no tab, the explorer is drawn in the page instead of the drawer, so the
// page is the tree, not an empty page; it goes back into the drawer when a file opens.
// The tabs, each source's active one and the view chosen per kind of file are kept in localStorage; the address
// names the active file of the repository while the repository is shown (a local tab has no address: nothing of it
// reaches the server). Local tabs come back when access to the folder is restored.
// A document is shown by its kind: Markdown rendered (render.js) in a reading column, pictures as pictures (an SVG
// too, never inlined), a PDF in the browser's own viewer in a frame, anything else as one sentence and a link. The
// source view is the editor (editor.js) for both sources: editable for a local text file; read only for the
// repository until 編輯, which makes it editable in place (a rendered-only view turns to the source). A local file that
// is open and unchanged follows the disk by itself; with unsaved changes it is never overwritten silently: saving
// compares first, and the reader chooses in place. Saving a file of the repository asks in place for a one-line commit
// message (prefilled), then commits it in the reader's own name with the version it started from (repo.js save); when
// GitHub has a newer one nothing is written and the reader chooses in place, as for a local file. A file of the
// repository with unsaved changes is never replaced by a push. A new file of the repository (repo.js newFile) is an
// empty tab being edited, saved as a new file. A file read again (the disk moved, or
// the repository has a new head) replaces what is shown only when it differs (apply): the same bytes redraw nothing,
// new text goes into the open editor and the rendering in place, keeping the scroll and the selection.
// Each tab carries the kind mark of its file (A.kindMark).
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("files"), E = A && A.explorer, S = A && A.sources;
  if (!A || !root || !E || !S) return;
  var t = A.t, make = A.make;
  var SLUG = root.dataset.slug, CAN_MANAGE = !!root.dataset.canManage;
  var TABS_KEY = "asterism-files:" + SLUG, VIEW_KEY = "asterism-files-view";
  var SLOW_MS = 500, RENDER_PAUSE_MS = 300, WATCH_MS = 3000;
  var R = S.repo, L = S.local;
  var el = {tabs: document.getElementById("file-tabs"), view: document.getElementById("file-view"),
            sw: document.getElementById("view-switch"), github: document.getElementById("file-github"),
            save: document.getElementById("file-save"), pdf: document.getElementById("file-pdf"),
            edit: document.getElementById("file-edit"), auth: document.getElementById("file-auth"),
            status: document.getElementById("explorer-status"), explorer: document.getElementById("explorer"),
            nav: document.getElementById("nav")};
  var MODES = {markdown: ["rendered", "source", "split"], text: ["source"], image: ["rendered"], pdf: ["rendered"]};

  var V = A.viewer = {};
  // {source, path, key, status: idle|loading|ok|gone|too_large|unavailable|not_connected|error|closed, doc, editor,
  //  dirty, conflict, said, snap, scroll, pics: Map(path -> object URL)}; a tab of the repository also has editing,
  //  view (the view it shows, over the one chosen for its kind), asking (the commit message is asked for), message,
  //  saving, current (after a conflict: the hash GitHub has now, null when the file is gone there)
  var tabs = [];                 // the tabs of both sources; the strip shows those of the source shown (E.shown)
  var actives = {repo: null, local: null};     // the key of each source's active tab
  var waiting = [], waitingActive = null;      // local tabs of an earlier visit, until access returns
  var views = A.store.get(VIEW_KEY, {}) || {};
  var turning = false;           // this script turns the explorer to another source (it draws the strip itself)
  var narrow = window.matchMedia("(max-width: 899.98px)");

  function keyOf(source, path) { return source + ":" + path; }
  function nameOf(path) { return path.slice(path.lastIndexOf("/") + 1); }
  function find(key) { for (var i = 0; i < tabs.length; i++) if (tabs[i].key === key) return tabs[i]; return null; }
  function strip(source) { return tabs.filter(function (x) { return x.source === source; }); }
  function current() { return find(actives[E.shown]); }
  function tabFor(source, path) {
    return {source: source, path: path, key: keyOf(source, path), status: "idle", doc: null, editor: null, dirty: false,
            conflict: false, said: "", pics: new Map(), editing: false, view: null, asking: false, message: null,
            saving: false};
  }
  // A new file of the repository not saved yet: nothing of it is on GitHub, so it is neither kept nor read again.
  function fresh(tab) { return !!(tab && tab.doc && tab.doc.fresh); }
  function save() {
    A.store.set(TABS_KEY, {tabs: tabs.filter(function (x) { return !fresh(x); })
                                     .map(function (x) { return {s: x.source, p: x.path}; }).concat(waiting),
                           actives: {repo: actives.repo, local: actives.local || waitingActive}});
  }
  // The editor takes typing: a local text file, or a file of the repository being edited.
  function editable(tab) {
    if (!tab || tab.status !== "ok" || !tab.doc || !tab.doc.editable) return false;
    return tab.source === "local" || (tab.source === "repo" && tab.editing);
  }

  // ------------------------------------------------------------------ opening and closing

  // opts: {newTab: true} for a tab of its own; {at: index} where a new tab (or the file's open tab) goes in the strip.
  V.open = function (source, path, opts) {
    opts = opts || {};
    if (!S[source] || !A.splitPath(path)) return;
    var key = keyOf(source, path), cur = find(actives[source]), at = typeof opts.at === "number" ? opts.at : null;
    if (find(key)) {
      if (at !== null) move(key, at);
    } else if (!opts.newTab && at === null && cur && !cur.dirty && !fresh(cur)) {
      if (shownTab === cur) shownTab = null;               // the current tab shows the file instead
      release(cur);
      tabs.splice(tabs.indexOf(cur), 1, tabFor(source, path));
    } else {
      var list = strip(source);
      place(source, at !== null ? at : cur ? list.indexOf(cur) + 1 : list.length, tabFor(source, path));
    }
    activate(source, key, true);
  };

  // A new file of the repository (repo.js newFile): an empty tab, being edited, after the current one. Saved, it becomes
  // a file like the others.
  V.create = function (source, path) {
    var key = keyOf(source, path);
    if (!find(key)) {
      var tab = tabFor(source, path), cur = find(actives[source]), list = strip(source);
      tab.status = "ok";
      tab.doc = {status: "ok", kind: /\.(?:md|markdown)$/i.test(path) ? "markdown" : "text", text: "", editable: true,
                 fresh: true, sha: null, eol: "\n", bom: false};
      tab.editing = true;
      if (modeOf(tab) === "rendered") tab.view = "source";
      tab.hadFocus = true;
      place(source, cur ? list.indexOf(cur) + 1 : list.length, tab);
    }
    activate(source, key, true);
  };

  // A tab put at the place `i` of its source's strip.
  function place(source, i, tab) {
    var list = strip(source);
    i = Math.max(0, Math.min(i, list.length));
    var at = i < list.length ? tabs.indexOf(list[i]) : list.length ? tabs.indexOf(list[list.length - 1]) + 1 : tabs.length;
    tabs.splice(at, 0, tab);
  }

  // A tab moved to the place `to` (an index of its strip before the move).
  function move(key, to) {
    var tab = find(key);
    if (!tab) return;
    var from = strip(tab.source).indexOf(tab);
    tabs.splice(tabs.indexOf(tab), 1);
    if (to > from) to -= 1;
    place(tab.source, to, tab);
    save();
    drawTabs(false);
  }

  // `key` (or null) becomes the active tab of `source`, and that source is shown.
  function activate(source, key, focusTab) {
    actives[source] = find(key) ? key : null;
    if (source !== E.shown) {
      turning = true;
      try { E.show(source); } finally { turning = false; }
    }
    showSource(focusTab);
  }

  // The strip and the document of the source shown, with its active tab (the explorer has turned to it).
  function showSource(focusTab) {
    var tab = current();
    save();
    var where = tab && tab.source === "repo" ? A.fileHref(SLUG, tab.path) : A.fileHref(SLUG, "").replace(/\/$/, "");
    if (window.location.pathname !== where || window.location.hash) history.replaceState(null, "", where);
    E.setCurrent(E.shown, tab ? tab.path : null);
    drawTabs(focusTab);
    placeExplorer();
    if (tab && tab.status === "idle") load(tab);
    else { draw(); follow(tab); if (tab && tab.stale) refresh(tab); }
  }
  E.on("source", function () { if (!turning) showSource(false); });

  function release(tab) {
    if (tab.doc) S[tab.source].release(tab.doc);
    tab.pics.forEach(function (url) { URL.revokeObjectURL(url); });
    tab.pics.clear();
    if (tab.editor) { tab.editor.destroy(); tab.editor = null; }
    clearTimeout(tab.renderTimer);
  }

  function close(key) {
    var tab = find(key);
    if (!tab) return;
    var source = tab.source, list = strip(source), i = list.indexOf(tab);
    if (shownTab === tab) shownTab = null;
    release(tab);
    tabs.splice(tabs.indexOf(tab), 1);
    var next = key === actives[source] ? (list[i + 1] || list[i - 1] || null) : find(actives[source]);
    var hadFocus = el.tabs.contains(document.activeElement);
    activate(source, next ? next.key : null, false);
    if (hadFocus) {
      var b = next && tabButton(next.key);
      (b || el.view).focus();
    }
  }

  // A tab with unsaved changes closes on a second press of its close control, which says so first.
  function askClose(tab, control) {
    if (tab.dirty && !A.twoStep(control, t("files.close_unsaved", {name: nameOf(tab.path)}))) return;
    close(tab.key);
  }

  // ------------------------------------------------------------------ the strip

  function tabButton(key) {
    var w = el.tabs.querySelector('.tab[data-key="' + key.replace(/["\\]/g, "\\$&") + '"]');
    return w && w.querySelector("[role=tab]");
  }

  // Tabs of the same name told apart: for each, the end of its folder, one segment more until they all differ (a
  // file at the top has none). key -> the words shown after the name.
  function hints(list) {
    var out = new Map(), byName = new Map();
    list.forEach(function (x) {
      var n = nameOf(x.path);
      if (!byName.has(n)) byName.set(n, []);
      byName.get(n).push(x);
    });
    byName.forEach(function (same) {
      if (same.length < 2) return;
      var folders = same.map(function (x) { return x.path.split("/").slice(0, -1); });
      var deepest = Math.max.apply(null, folders.map(function (f) { return f.length; }));
      function tail(f, k) { return f.slice(Math.max(0, f.length - k)).join("/"); }
      var k = 1;
      while (k < deepest && new Set(folders.map(function (f) { return tail(f, k); })).size < same.length) k += 1;
      same.forEach(function (x, i) { var h = tail(folders[i], k); if (h) out.set(x.key, h); });
    });
    return out;
  }

  function drawTabs(focusTab) {
    var hadFocus = el.tabs.contains(document.activeElement);
    var list = strip(E.shown), active = actives[E.shown], told = hints(list);
    el.tabs.textContent = "";
    list.forEach(function (x, i) {
      var name = nameOf(x.path), local = x.source === "local", hint = told.get(x.key);
      var wrap = make("div", "tab" + (x.status === "gone" ? " gone" : "") + (local ? " local" : "") + (x.dirty ? " dirty" : ""));
      wrap.dataset.key = x.key;
      wrap.setAttribute("role", "presentation");
      var b = A.button("tab-btn", null, function () { activate(x.source, x.key, true); });
      b.setAttribute("role", "tab");
      b.id = "tab-" + i;
      b.setAttribute("aria-selected", String(x.key === active));
      b.setAttribute("aria-keyshortcuts", "Delete");
      b.tabIndex = x.key === active ? 0 : -1;
      var shown = x.status === "gone" ? t("files.tab_gone", {name: name}) : name;
      var said = local ? t(x.dirty ? "files.tab_local_unsaved" : "files.tab_local", {name: shown})
                       : x.dirty ? t("files.tab_unsaved", {name: shown}) : null;
      b.title = (local ? t("files.local_path", {path: x.path}) : x.path) + (x.dirty ? " · " + t("files.unsaved") : "");
      if (said) b.setAttribute("aria-label", said + (hint ? " " + hint : ""));
      b.appendChild(A.kindMark(x.path, false));
      b.appendChild(make("span", "tab-name", shown));
      if (hint) b.appendChild(make("span", "tab-hint", hint));
      if (x.dirty) {
        var dot = make("span", "tab-dirty");
        dot.setAttribute("aria-hidden", "true");
        b.appendChild(dot);
      }
      var c = A.button("tab-close", null, function (ev) { ev.stopPropagation(); askClose(x, c); });
      c.tabIndex = -1;
      c.setAttribute("aria-label", t("files.close_tab", {name: name}));
      c.title = t("files.close_tab", {name: name});
      c.appendChild(make("span", "cross"));
      c.firstChild.setAttribute("aria-hidden", "true");
      wrap.append(b, c);
      // A middle click closes, as in every tab strip.
      wrap.addEventListener("mousedown", function (ev) { if (ev.button === 1) ev.preventDefault(); });
      wrap.addEventListener("auxclick", function (ev) { if (ev.button === 1) { ev.preventDefault(); askClose(x, c); } });
      wrap.addEventListener("contextmenu", function (ev) {
        ev.preventDefault();
        A.menu({x: ev.clientX, y: ev.clientY, label: t("files.acts", {name: name})}, E.menuItems(x.source, x.path, false), b);
      });
      wrap.draggable = true;
      wrap.addEventListener("dragstart", function (ev) {
        dragKey = x.key;
        wrap.classList.add("dragging");
        ev.dataTransfer.effectAllowed = "move";
        try { ev.dataTransfer.setData("text/plain", x.path); } catch (err) { /* the key is kept above */ }
      });
      wrap.addEventListener("dragend", function () { dragKey = null; wrap.classList.remove("dragging"); unmark(); });
      el.tabs.appendChild(wrap);
    });
    var cur = active && tabButton(active);
    if (cur) {
      el.view.setAttribute("aria-labelledby", cur.id);
      if (focusTab && hadFocus) cur.focus({preventScroll: true});
    } else {
      el.view.removeAttribute("aria-labelledby");
    }
    reveal();
  }

  // ------------------------------------------------------------------ an overflowing strip
  //
  // An edge with more tabs beyond it fades out (only while there are); the wheel scrolls the strip sideways. The
  // current tab is kept in view clear of a faded edge (when the strip is drawn or changes its width).

  var FADE_PX = 40;              // as wide as the fade in the stylesheet
  function edges() {
    var s = el.tabs, beyond = s.scrollWidth - s.clientWidth - s.scrollLeft;
    s.classList.toggle("fade-start", s.scrollLeft > 1);
    s.classList.toggle("fade-end", beyond > 1);
  }
  function reveal() {
    var s = el.tabs, b = actives[E.shown] && tabButton(actives[E.shown]);
    if (b && s.scrollWidth > s.clientWidth) {
      var r = b.parentNode.getBoundingClientRect(), box = s.getBoundingClientRect();
      var room = Math.min(FADE_PX, Math.max(0, (box.width - r.width) / 2));
      if (r.left < box.left + room) s.scrollLeft -= box.left + room - r.left;
      else if (r.right > box.right - room) s.scrollLeft += r.right - (box.right - room);
    }
    edges();
  }
  el.tabs.addEventListener("scroll", edges, {passive: true});
  if (typeof ResizeObserver === "function") new ResizeObserver(reveal).observe(el.tabs);
  else window.addEventListener("resize", reveal);
  el.tabs.addEventListener("wheel", function (ev) {
    var s = el.tabs;
    if (ev.ctrlKey || s.scrollWidth <= s.clientWidth || Math.abs(ev.deltaX) >= Math.abs(ev.deltaY)) return;
    var unit = ev.deltaMode === 1 ? 16 : ev.deltaMode === 2 ? s.clientWidth : 1;
    var before = s.scrollLeft;
    s.scrollLeft += ev.deltaY * unit;
    if (s.scrollLeft !== before) ev.preventDefault();
  }, {passive: false});

  // ------------------------------------------------------------------ dropping on the strip
  //
  // A tab dragged along the strip, or a file dragged from the tree (E.dragging): it goes before the first tab whose
  // middle is right of the pointer, else at the end; a line marks the place while it is over the strip.

  var dragKey = null;
  function unmark() {
    el.tabs.classList.remove("drop-end");
    Array.prototype.forEach.call(el.tabs.querySelectorAll(".drop-before"), function (w) { w.classList.remove("drop-before"); });
  }
  function dropIndex(x) {
    var wraps = el.tabs.querySelectorAll(".tab");
    for (var i = 0; i < wraps.length; i++) {
      var r = wraps[i].getBoundingClientRect();
      if (x < r.left + r.width / 2) return i;
    }
    return wraps.length;
  }
  el.tabs.addEventListener("dragover", function (ev) {
    if (!dragKey && !E.dragging) return;
    ev.preventDefault();
    ev.dataTransfer.dropEffect = dragKey ? "move" : "copy";
    var i = dropIndex(ev.clientX), wraps = el.tabs.querySelectorAll(".tab");
    unmark();
    if (i < wraps.length) wraps[i].classList.add("drop-before"); else el.tabs.classList.add("drop-end");
  });
  el.tabs.addEventListener("dragleave", function (ev) {
    if (!ev.relatedTarget || !el.tabs.contains(ev.relatedTarget)) unmark();
  });
  el.tabs.addEventListener("drop", function (ev) {
    if (!dragKey && !E.dragging) return;
    ev.preventDefault();
    var i = dropIndex(ev.clientX);
    unmark();
    if (dragKey) { move(dragKey, i); dragKey = null; return; }
    var f = E.dragging;
    E.dragging = null;
    V.open(f.source, f.path, {newTab: true, at: i});
  });

  el.tabs.addEventListener("keydown", function (ev) {
    var b = ev.target.closest("[role=tab]");
    if (!b) return;
    var list = Array.prototype.slice.call(el.tabs.querySelectorAll("[role=tab]")), i = list.indexOf(b), j = null;
    var key = b.parentNode.dataset.key, tab = find(key);
    if (ev.key === "ArrowRight") j = (i + 1) % list.length;
    else if (ev.key === "ArrowLeft") j = (i - 1 + list.length) % list.length;
    else if (ev.key === "Home") j = 0;
    else if (ev.key === "End") j = list.length - 1;
    else if (ev.key === "Delete") {
      ev.preventDefault();
      if (tab && tab.dirty) askClose(tab, b.parentNode.querySelector(".tab-close")); else close(key);
      return;
    } else if (ev.key === "ContextMenu" || (ev.key === "F10" && ev.shiftKey)) {
      ev.preventDefault();
      if (tab) A.menu({anchor: b, label: t("files.acts", {name: nameOf(tab.path)})}, E.menuItems(tab.source, tab.path, false), b);
      return;
    }
    if (j === null) return;
    ev.preventDefault();
    var to = list[j].parentNode.dataset.key;
    activate(E.shown, to, false);
    var again = tabButton(to);
    if (again) again.focus();
  });

  // ------------------------------------------------------------------ reading a file

  async function load(tab) {
    tab.status = "loading";
    draw();
    var doc = await S[tab.source].read(tab.path);
    if (find(tab.key) !== tab) { S[tab.source].release(doc); return; }     // closed meanwhile
    if (tab.doc) S[tab.source].release(tab.doc);
    tab.doc = doc;
    tab.status = doc.status;
    if (tab.editor) {
      if (doc.status === "ok" && (doc.kind === "text" || doc.kind === "markdown")) {
        tab.editor.setText(doc.text);
        settle(tab);
      } else {
        tab.editor.destroy();
        tab.editor = null;
      }
    }
    if (tab.status === "gone") drawTabs(false);
    if (current() === tab) { draw(true); follow(tab); }
  }

  // After a push: a file of the repository that is gone says so on its tab; the others are read again quietly, the
  // active one now and the rest when they are next shown, and redrawn only when they changed. Only the repository's
  // paths are asked about; a local file shown is not touched (a push to the repository does not change it). A tab
  // with unsaved changes keeps them (its save will find the push), and a new file not saved yet is not on GitHub.
  R.on("changed", async function () {
    var mine = tabs.filter(function (x) { return x.source === "repo" && !fresh(x); });
    var paths = mine.map(function (x) { return x.path; }), found = null;
    if (paths.length) {
      var r = await A.request("/" + encodeURIComponent(SLUG) + "/api/files/resolve", null, {paths: paths.slice(0, 200)});
      if (r.ok) found = r.data.found || {};
    }
    mine.forEach(function (x) {
      if (x.dirty) {
        x.stale = true;
      } else if (found && found[x.path] !== "file") {
        if (shownTab === x) shownTab = null;
        release(x);
        x.doc = null;
        x.status = "gone";
      } else if (x.status === "ok") {
        x.stale = true;
      } else if (x.status !== "loading") {
        x.status = "idle";
      }
    });
    drawTabs(false);
    var cur = current();
    if (!cur || cur.source !== "repo") return;
    if (cur.status === "gone") draw(true);
    else if (cur.status === "idle") load(cur);
    else if (cur.stale) refresh(cur);
  });
  R.on("state", function () { draw(); });

  // The local folder: its tabs come back when access does, and go when it is forgotten.
  L.on("state", function () {
    if (L.state === "ok" && waiting.length) {
      waiting.forEach(function (x) { if (!find(keyOf("local", x.p))) tabs.push(tabFor("local", x.p)); });
      waiting = [];
      var back = waitingActive;
      waitingActive = null;
      if (!find(actives.local)) actives.local = back && find(back) ? back : null;
      if (E.shown === "local") showSource(false); else save();
    } else if (L.state === "none") {
      waiting = [];
      waitingActive = null;
      actives.local = null;
      strip("local").forEach(function (x) {
        if (shownTab === x) shownTab = null;
        release(x);
        tabs.splice(tabs.indexOf(x), 1);
      });
      if (E.shown === "local") showSource(false); else save();
    }
  });
  L.on("moved", function (m) {
    var tab = find(keyOf("local", m.from));
    if (!tab || find(keyOf("local", m.to))) return;
    var was = tab.key;
    tab.path = m.to;
    tab.key = keyOf("local", m.to);
    if (actives.local === was) { actives.local = tab.key; if (E.shown === "local") E.setCurrent("local", m.to); }
    save();
    drawTabs(false);
  });
  L.on("removed", function (m) {
    tabs.forEach(function (x) {
      if (x.source !== "local" || !(x.path === m.path || x.path.indexOf(m.path + "/") === 0)) return;
      if (shownTab === x) shownTab = null;
      release(x);
      x.doc = null;
      x.dirty = false;
      x.status = "gone";
    });
    drawTabs(false);
    draw(true);
  });

  // ------------------------------------------------------------------ following the disk (local files)

  // The file shown, if local, open and unchanged in the editor, follows the disk: checked when its tab or the window
  // gets focus and every few seconds while it shows. With unsaved changes nothing is touched here: saving compares.
  async function follow(tab) {
    if (!tab || tab.source !== "local" || tab.status !== "ok" || !tab.doc || !tab.doc.stamp || tab.following || tab.saving) return;
    tab.following = true;
    try {
      var moved = await L.changed(tab.path, tab.doc);
      if (!moved || find(tab.key) !== tab || tab.dirty) { if (moved && moved.doc) L.release(moved.doc); return; }
      if (moved.gone) {
        release(tab);
        tab.doc = null;
        tab.status = "gone";
        drawTabs(false);
        if (current() === tab) draw(true);
        return;
      }
      apply(tab, moved.doc);
    } finally {
      tab.following = false;
    }
  }

  // A file of the repository read again after a push, quietly: the view stays as it is while it is read.
  async function refresh(tab) {
    if (!tab || tab.refreshing || tab.dirty || fresh(tab)) return;
    tab.refreshing = true;
    try {
      var doc = await S[tab.source].read(tab.path);
      if (find(tab.key) !== tab) { S[tab.source].release(doc); return; }
      tab.stale = false;
      apply(tab, doc);
    } finally {
      tab.refreshing = false;
    }
  }

  // The same document twice: the same kind and the same text, or (a picture, a PDF, a download of the repository)
  // the same hash.
  function same(a, b) {
    if (!a || !b || a.kind !== b.kind || !!a.editable !== !!b.editable) return false;
    if (typeof a.text === "string" || typeof b.text === "string") return a.text === b.text;
    return !!a.etag && a.etag === b.etag;
  }

  // What was read again takes the place of what the tab holds, redrawing only what changed: the same document
  // redraws nothing; new text of the same kind goes into the open editor (its selection and scroll kept) and the
  // rendering is replaced where the reader had scrolled to; anything else is drawn anew.
  function apply(tab, doc) {
    var old = tab.doc, src = S[tab.source];
    if (tab.dirty || fresh(tab)) { src.release(doc); return; }    // typed meanwhile: never replaced from here
    if (tab.status === "ok" && doc.status === "ok" && same(old, doc)) {
      if (doc.stamp) old.stamp = doc.stamp;
      if (doc.bytes) old.bytes = doc.bytes;
      // The same text in other bytes (a line ending): a save starts from what is there now.
      ["etag", "sha", "eol", "bom"].forEach(function (k) { if (k in doc) old[k] = doc[k]; });
      src.release(doc);
      return;
    }
    if (tab.status === "ok" && doc.status === "ok" && old && doc.kind === old.kind && !!doc.editable === !!old.editable &&
        (doc.kind === "text" || doc.kind === "markdown")) {
      src.release(old);
      tab.doc = doc;
      if (tab.editor) { tab.editor.setText(doc.text); settle(tab); }
      if (current() === tab && shownTab === tab && modeOf(tab) !== "source") refreshRendering(tab);
      return;
    }
    src.release(old);
    if (tab.editor) { tab.editor.destroy(); tab.editor = null; }
    tab.doc = doc;
    tab.status = doc.status;
    if (tab.status === "gone") drawTabs(false);
    if (current() === tab) draw(true);
  }
  setInterval(function () { if (!document.hidden) follow(current()); }, WATCH_MS);
  window.addEventListener("focus", function () { follow(current()); });

  // The editor holds what the disk holds now: nothing is unsaved.
  function settle(tab) {
    tab.editor.markSaved();
    if (tab.dirty) { tab.dirty = false; drawTabs(false); drawTools(tab); }
  }

  // ------------------------------------------------------------------ saving (local files)

  async function saveTab(tab, force) {
    if (!editable(tab) || !tab.editor || tab.saving) return;
    if (tab.source === "repo") { askCommit(tab); return; }
    if (!tab.dirty && !force) { el.status.textContent = t("files.nothing_to_save"); return; }
    tab.saving = true;
    var at = tab.editor.at();
    var res = await L.save(tab.path, at.toString(), tab.doc, !!force);
    tab.saving = false;
    if (find(tab.key) !== tab) return;
    if (res.ok) {
      tab.editor.markSaved(at);
      tab.dirty = tab.editor.dirty();
      tab.conflict = false;
      tab.said = "";
      el.status.textContent = t("files.saved", {name: nameOf(tab.path)});
    } else if (res.conflict) {
      tab.conflict = true;
      tab.said = "";
      el.status.textContent = t("files.conflict");
    } else {
      tab.said = res.message;
      el.status.textContent = res.message;
    }
    drawTabs(false);
    draw(true);
  }

  // The reader chose the disk's version: their changes are gone, the undo history with them.
  async function takeDisk(tab) {
    var doc = await L.read(tab.path);
    if (find(tab.key) !== tab) { L.release(doc); return; }
    if (tab.editor) { tab.editor.destroy(); tab.editor = null; }
    L.release(tab.doc);
    tab.doc = doc;
    tab.status = doc.status;
    tab.dirty = false;
    tab.conflict = false;
    tab.said = "";
    drawTabs(false);
    draw(true);
  }

  // ------------------------------------------------------------------ editing and saving (files of the repository)

  // 編輯: the read-only editor becomes editable in place (a rendered-only view turns to the source).
  function startEdit(tab) {
    if (!R.canWrite || !tab.doc || !tab.doc.editable) return;
    tab.editing = true;
    if (modeOf(tab) === "rendered") tab.view = "source";
    if (tab.editor) tab.editor.setReadOnly(false);
    tab.hadFocus = true;
    drawTabs(false);
    draw(true);
    if (tab.editor) tab.editor.focus();
  }

  // Editing ends: unsaved changes are dropped (the press that does it said so first). A new file goes with its tab.
  function stopEdit(tab) {
    if (fresh(tab)) { close(tab.key); return; }
    if (tab.editor) {
      if (tab.dirty) tab.editor.setText(tab.doc.text);
      tab.editor.markSaved();
      tab.editor.setReadOnly(true);
    }
    tab.editing = tab.dirty = tab.asking = tab.conflict = false;
    tab.said = "";
    tab.message = null;
    drawTabs(false);
    draw(true);
  }

  if (el.edit) {
    el.edit.addEventListener("click", function () {
      var tab = current();
      if (!tab || tab.source !== "repo" || tab.status !== "ok" || tab.saving) return;
      if (!tab.editing) { startEdit(tab); return; }
      if ((tab.dirty || fresh(tab)) && !A.twoStep(el.edit, t(fresh(tab) ? "files.edit_drop_new_armed" : "files.edit_discard_armed"))) return;
      stopEdit(tab);
    });
  }

  function defaultMessage(tab) { return (fresh(tab) ? "Add " : "Edit ") + tab.path + " via Asterism"; }

  // Saving asks in place for the commit message, one line, prefilled; it is sent from there (commit).
  function askCommit(tab) {
    if (!tab.dirty && !fresh(tab) && !tab.conflict) { el.status.textContent = t("files.nothing_to_save"); return; }
    if (tab.conflict) return;                         // the choices over the document say what can be done
    if (tab.asking) { focusAsk(); return; }
    tab.asking = true;
    if (tab.message === null) tab.message = defaultMessage(tab);
    tab.said = "";
    draw(true);
    focusAsk();
  }
  function focusAsk() {
    var input = el.view.querySelector(".commit-ask input");
    if (input) { input.focus(); input.select(); }
  }

  // One commit of what the editor holds now, from `base` (the hash the change started from; null for a new file, or
  // when the reader writes over a file deleted on GitHub meanwhile).
  async function commit(tab, base, message) {
    if (tab.saving) return;
    tab.saving = true;
    tab.asking = false;
    tab.said = "";
    draw(true);
    var at = tab.editor.at(), text = at.toString();
    var r = await R.save(tab.path, tab.doc, text, base, message);
    tab.saving = false;
    if (find(tab.key) !== tab) return;
    if (r.ok) {
      tab.editor.markSaved(at);
      tab.dirty = tab.editor.dirty();
      tab.doc.text = text;
      tab.doc.sha = r.data.sha;
      tab.doc.etag = '"' + r.data.sha + '"';
      tab.doc.url = A.rawUrl(SLUG, tab.path);
      delete tab.doc.fresh;
      tab.conflict = false;
      tab.current = undefined;
      tab.message = null;
      if (!tab.dirty) { tab.editing = false; tab.editor.setReadOnly(true); }
      el.status.textContent = t("files.saved_github", {name: nameOf(tab.path)});
      save();
      drawTabs(false);
      draw(true);
      R.wrote();                                      // the tree and the other tabs follow, as after 重新整理
      return;
    }
    var code = r.data && r.data.error;
    if (code === "conflict") {
      tab.conflict = true;
      tab.current = typeof r.data.current === "string" ? r.data.current : null;
      tab.message = message;
      el.status.textContent = t("files.conflict_repo");
    } else {
      if (code === "github_reauth") R.refused("reauth");
      else if (code === "forbidden") R.refused("no_push");
      tab.said = A.refusal("files.save", r.data);
      tab.message = message;
      el.status.textContent = tab.said;
    }
    drawTabs(false);
    draw(true);
  }

  // After a conflict, the reader chose GitHub's version: their changes are gone, and so is editing.
  async function takeRemote(tab) {
    await R.wrote();
    var doc = await R.read(tab.path);
    if (find(tab.key) !== tab) return;
    if (tab.editor) { tab.editor.destroy(); tab.editor = null; }
    tab.doc = doc;
    tab.status = doc.status;
    tab.dirty = tab.conflict = tab.editing = tab.stale = false;
    tab.said = "";
    tab.message = null;
    tab.current = undefined;
    drawTabs(false);
    draw(true);
  }

  el.save.addEventListener("click", function () {
    if (el.save.getAttribute("aria-disabled") === "true") return;
    saveTab(current());
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.defaultPrevented || !(ev.ctrlKey || ev.metaKey) || ev.altKey || (ev.key !== "s" && ev.key !== "S")) return;
    var tab = current();
    if (!editable(tab)) return;
    ev.preventDefault();
    saveTab(tab);
  });
  window.addEventListener("beforeunload", function (ev) {
    if (!tabs.some(function (x) { return x.dirty; })) return;
    ev.preventDefault();
    ev.returnValue = "";
  });

  // ------------------------------------------------------------------ the view switch and the control beside it

  function modesOf(tab) { return tab && tab.status === "ok" && tab.doc ? (MODES[tab.doc.kind] || []) : []; }
  function modeOf(tab) {
    var modes = modesOf(tab), chosen = (tab && tab.view) || views[tab && tab.doc && tab.doc.kind];
    return modes.indexOf(chosen) >= 0 ? chosen : modes[0] || null;
  }

  function drawTools(tab) {
    var modes = modesOf(tab), mode = modeOf(tab);
    Array.prototype.forEach.call(el.sw.querySelectorAll("[data-view]"), function (b) {
      var can = modes.indexOf(b.dataset.view) >= 0;
      b.setAttribute("aria-disabled", String(!can));
      b.setAttribute("aria-pressed", String(can && b.dataset.view === mode));
    });
    var local = E.shown === "local", writing = !local && editable(tab);
    // 編輯, for a text file of the repository that the reader may save (or is editing); else, when saving needs their
    // GitHub authorization, the quiet way to it.
    var text = !local && tab && tab.status === "ok" && tab.doc && (tab.doc.kind === "text" || tab.doc.kind === "markdown");
    if (el.edit) {
      el.edit.hidden = !(text && (tab.editing || (R.canWrite && tab.doc.editable)));
      el.edit.setAttribute("aria-pressed", String(!!(text && tab.editing)));
    }
    if (el.auth) el.auth.hidden = !(text && !tab.editing && !R.canWrite && /^(no_token|reauth)$/.test(R.writeReason || ""));
    el.github.hidden = local || writing;
    el.save.hidden = !(local || writing);
    var gh = tab && !local ? R.githubUrl(tab.path, false) : null;
    if (gh) { el.github.href = gh; el.github.removeAttribute("aria-disabled"); }
    else { el.github.removeAttribute("href"); el.github.setAttribute("aria-disabled", "true"); }
    el.save.setAttribute("aria-disabled", String(!(editable(tab) && !tab.saving && (tab.dirty || tab.conflict || fresh(tab)))));
    var pdf = pdfOf(tab);
    if (el.pdf) {
      el.pdf.hidden = !pdf;
      el.pdf.title = pdf ? t("files.open_pdf_title", {name: nameOf(pdf)}) : "";
    }
  }

  // The PDF of the same name next to a .tex file, as its folder is listed (asked for when it is not), or null.
  function pdfOf(tab) {
    if (!tab || !/\.tex$/i.test(tab.path)) return null;
    var slash = tab.path.lastIndexOf("/"), folder = slash < 0 ? "" : tab.path.slice(0, slash), s = S[tab.source];
    var want = tab.path.slice(0, -4) + ".pdf", entries = s.listed(folder);
    if (!entries) {
      if (!tab.askedFolder && !s.pending(folder)) { tab.askedFolder = true; s.list(folder); }   // once per tab
      return null;
    }
    var same = entries.filter(function (x) { return x.type === "file" && x.path.toLowerCase() === want.toLowerCase(); });
    var exact = same.filter(function (x) { return x.path === want; })[0] || same[0];
    return exact ? exact.path : null;
  }
  if (el.pdf) {
    el.pdf.addEventListener("click", function () {
      var tab = current(), pdf = pdfOf(tab);
      if (pdf) V.open(tab.source, pdf, {newTab: true});
    });
  }
  R.on("listing", function () { if (E.shown === "repo") drawTools(current()); });
  R.on("write", function () { if (E.shown === "repo") draw(); });
  L.on("listing", function () { if (E.shown === "local") drawTools(current()); });

  el.sw.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-view]"), tab = current();
    if (!b || b.getAttribute("aria-disabled") === "true" || !tab) return;
    views[tab.doc.kind] = b.dataset.view;
    tab.view = null;
    A.store.set(VIEW_KEY, views);
    draw();
  });

  // ------------------------------------------------------------------ the document

  var slow = null, drawn = "", shownTab = null;

  // Where the reader was in what is shown now, kept on its tab before the view is drawn again.
  function keepPlace() {
    var tab = shownTab;
    if (!tab || find(tab.key) !== tab) return;
    if (tab.editor && el.view.contains(tab.editor.dom)) {
      tab.snap = tab.editor.snapshot();
      tab.hadFocus = tab.editor.view.hasFocus;
    }
    var docs = el.view.querySelector(".doc-scroll, .pic-scroll");
    if (docs) tab.scroll = docs.scrollTop;
  }

  function draw(force) {
    var tab = current(), mode = modeOf(tab);
    drawTools(tab);
    var repoSide = E.shown === "repo";
    var key = JSON.stringify([tab ? tab.key : E.shown, tab && tab.status, tab && tab.doc && tab.doc.kind, mode,
                              tab && tab.conflict, tab && tab.said, repoSide ? R.state : "", tab && tab.editing,
                              tab && tab.asking, tab && tab.saving, repoSide && R.canWrite]);
    if (!force && key === drawn) return;
    drawn = key;
    keepPlace();
    clearTimeout(slow);
    el.view.textContent = "";
    el.view.className = "file-view";
    shownTab = tab;
    if (repoSide && (R.state === "not_connected" || (tab && tab.status === "not_connected"))) {
      var box = note(A.errorText("not_connected"));
      if (CAN_MANAGE) box.appendChild(make("p", "dim", t("files.not_connected_manage")));
      return;
    }
    if (!tab) {
      if (repoSide && R.state === "away") { note(t("files.unavailable")); return; }
      note(t("files.none_open")).classList.add("quiet");
      return;
    }
    if (tab.status === "loading" || tab.status === "idle") {
      // No spinner unless it takes a while; the area keeps its size meanwhile.
      slow = setTimeout(function () { if (current() === tab && tab.status === "loading") note(t("files.loading")).classList.add("quiet"); }, SLOW_MS);
      return;
    }
    if (tab.status === "gone") {
      var gone = note(t(tab.source === "local" ? "local.file_gone" : "files.gone"));
      gone.appendChild(A.button("btn", t("files.close_this"), function () { close(tab.key); }));
      return;
    }
    if (tab.status === "closed") { note(t("local.closed")); return; }
    if (tab.status === "too_large") {
      var big = note(t("files.too_large")), gh = R.githubUrl(tab.path, false);
      if (gh) big.appendChild(outLink(gh, t("files.open_github")));
      return;
    }
    if (tab.status === "unavailable") {
      var away = note(t("files.unavailable"));
      away.appendChild(A.button("btn", t("files.retry"), function () { load(tab); }));
      return;
    }
    if (tab.status === "error") { note(t("files.error", {code: tab.doc && tab.doc.code})); return; }
    var doc = tab.doc;
    if (doc.kind === "download") {
      var dl = note(doc.why || t("files.binary")), a = make("a", "btn", t("files.download"));
      a.href = doc.url;
      a.setAttribute("download", nameOf(tab.path));
      dl.appendChild(a);
      return;
    }
    if (doc.kind === "image") {
      var pic = make("div", "pic-scroll"), img = make("img", "pic");
      img.alt = nameOf(tab.path);
      img.src = doc.url;                   // an SVG too: a picture, never inlined, so nothing in it runs
      if (tab.source === "repo") {
        img.addEventListener("error", function () { tab.status = "idle"; if (current() === tab) load(tab); }, {once: true});
      }
      pic.appendChild(img);
      el.view.appendChild(pic);
      el.view.classList.add("wide");
      return;
    }
    if (doc.kind === "pdf") {
      var frame = make("iframe", "pdf-frame");
      frame.title = nameOf(tab.path);
      frame.src = doc.url;
      el.view.appendChild(frame);
      el.view.classList.add("wide");
      return;
    }
    var said = docNote(tab);
    if (said) el.view.appendChild(said);
    if (mode === "split") {
      var split = make("div", "split");
      split.append(pane(editorPane(tab)), pane(rendered(tab)));
      el.view.appendChild(split);
    } else if (mode === "rendered") {
      el.view.appendChild(rendered(tab));
    } else {
      el.view.appendChild(editorPane(tab));
    }
    if (tab.editor && el.view.contains(tab.editor.dom)) {
      tab.editor.restore(tab.snap);
      if (tab.hadFocus) tab.editor.focus();
    }
    var s = el.view.querySelector(".doc-scroll");
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

  // One sentence over the document, with what can be done about it: the file changed on disk while it has unsaved
  // changes (the reader chooses, each choice in two steps), a save that was refused, or why it is read only.
  function docNote(tab) {
    var box = make("div", "doc-note");
    if (tab.source === "repo") {
      var repoNote = repoDocNote(tab, box);
      if (repoNote !== undefined) return repoNote;
    }
    if (tab.conflict) {
      box.setAttribute("role", "alert");
      box.appendChild(make("p", null, t("files.conflict")));
      var row = make("div", "row");
      var disk = A.button("btn", t("files.take_disk"), function () {
        if (!A.twoStep(disk, t("files.take_disk_armed"))) return;
        takeDisk(tab);
      });
      var mine = A.button("btn", t("files.keep_mine"), function () {
        if (!A.twoStep(mine, t("files.keep_mine_armed"))) return;
        saveTab(tab, true);
      });
      row.append(disk, mine);
      box.appendChild(row);
      return box;
    }
    if (tab.said) { box.setAttribute("role", "alert"); box.appendChild(make("p", null, tab.said)); return box; }
    if (tab.doc && tab.doc.why) { box.appendChild(make("p", null, tab.doc.why)); return box; }
    return null;
  }

  // The note of a file of the repository, or undefined when it has none of its own: saving (the commit message asked
  // for, the save under way), GitHub has another version (the reader chooses, each choice in two steps), or why a text
  // file cannot be edited by a reader who could otherwise.
  function repoDocNote(tab, box) {
    if (tab.saving) {
      box.setAttribute("role", "status");
      box.appendChild(make("p", "dim", t("files.saving")));
      return box;
    }
    if (tab.asking) {
      var form = make("form", "commit-ask"), label = make("label", "commit-field");
      var input = make("input");
      input.type = "text";
      input.maxLength = 200;
      input.autocomplete = "off";
      input.spellcheck = false;
      input.value = tab.message === null ? defaultMessage(tab) : tab.message;
      input.addEventListener("input", function () { tab.message = input.value; });
      input.addEventListener("keydown", function (ev) {
        if (ev.key === "Escape") { ev.preventDefault(); cancelAsk(tab); }
      });
      label.append(make("span", null, t("files.commit_message")), input);
      var go = make("button", "btn primary", t("files.commit_save"));
      go.type = "submit";
      var no = A.button("btn", t("files.commit_cancel"), function () { cancelAsk(tab); });
      var row = make("div", "row");
      row.append(go, no);
      form.append(label, row);
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var message = input.value.replace(/\s+/g, " ").trim();
        commit(tab, fresh(tab) ? null : tab.doc.sha, message || defaultMessage(tab));
      });
      box.appendChild(form);
      return box;
    }
    if (tab.conflict) {
      box.setAttribute("role", "alert");
      var gone = tab.current === null;
      box.appendChild(make("p", null, t(fresh(tab) ? "files.conflict_repo_exists" : gone ? "files.conflict_repo_gone"
                                                                                     : "files.conflict_repo")));
      var choices = make("div", "row");
      if (!gone) {
        var theirs = A.button("btn", t("files.take_github"), function () {
          if (!A.twoStep(theirs, t("files.take_github_armed"))) return;
          takeRemote(tab);
        });
        choices.appendChild(theirs);
      }
      var mine = A.button("btn", t(fresh(tab) ? "files.keep_mine_new" : "files.keep_mine"), function () {
        if (!A.twoStep(mine, t(gone ? "files.keep_mine_gone_armed" : "files.keep_mine_github_armed"))) return;
        commit(tab, tab.current, tab.message || defaultMessage(tab));
      });
      choices.appendChild(mine);
      box.appendChild(choices);
      return box;
    }
    if (!tab.said && fresh(tab)) {
      box.appendChild(make("p", "dim", t("files.new_unsaved")));
      return box;
    }
    if (!tab.said && !tab.editing && R.canWrite && tab.doc && tab.doc.lock) {
      box.appendChild(make("p", null, tab.doc.lock));
      return box;
    }
    return undefined;
  }

  function cancelAsk(tab) {
    tab.asking = false;
    draw(true);
    if (tab.editor) tab.editor.focus();
  }

  // The source view: the tab's own editor, kept while the tab is open (its undo history, cursor and scroll with it).
  function editorPane(tab) {
    if (!tab.editor) {
      tab.editor = A.editor.create({
        path: tab.path, text: tab.doc.text || "", readOnly: !editable(tab), label: t("files.source_of", {name: nameOf(tab.path)}),
        onChange: function (ed) {
          var was = tab.dirty;
          tab.dirty = editable(tab) && ed.dirty();
          if (was !== tab.dirty) { drawTabs(false); drawTools(tab); }
          if (current() === tab && modeOf(tab) === "split") {
            clearTimeout(tab.renderTimer);
            tab.renderTimer = setTimeout(function () { refreshRendering(tab); }, RENDER_PAUSE_MS);
          }
        },
        onSave: function () { saveTab(tab); }
      });
    }
    var wrap = make("div", "editor-wrap");
    wrap.appendChild(tab.editor.dom);
    return wrap;
  }

  // The rendering beside the editor (or alone) follows the text: the new one takes the old one's place, where the
  // reader had scrolled to, and the focus stays where it is.
  function refreshRendering(tab) {
    if (current() !== tab || shownTab !== tab) return;
    var scroll = el.view.querySelector(".doc-scroll");
    if (!scroll) return;
    var top = scroll.scrollTop, fresh = renderDoc(tab);
    scroll.replaceChild(fresh, scroll.firstChild);
    scroll.scrollTop = top;
  }

  // A link or picture written relative to the file: the path in the same source it names, or null when it leaves it.
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
    var scroll = make("div", "doc-scroll");
    scroll.appendChild(renderDoc(tab));
    return scroll;
  }

  function renderDoc(tab) {
    var local = tab.source === "local";
    var doc = A.renderDoc(tab.editor ? tab.editor.text() : tab.doc.text || "", {
      link: function (href) {
        if (href.indexOf("//") === 0) return null;
        var path = relative(tab.path, href);
        if (!path) return null;
        // A local file has no address: its link is opened here, never sent anywhere.
        return {href: local ? "#" : A.fileHref(SLUG, path), path: path};
      },
      image: function (src) {
        if (src.indexOf("//") === 0) return null;
        var path = relative(tab.path, src);
        return !path ? null : local ? {local: path} : A.rawUrl(SLUG, path);
      }
    });
    if (local) {
      // Pictures of the folder, through object URLs kept on the tab (released when it closes).
      Array.prototype.forEach.call(doc.querySelectorAll("img[data-local]"), function (img) {
        var path = img.getAttribute("data-local");
        img.removeAttribute("data-local");
        var known = tab.pics.get(path);
        if (known) { img.src = known; return; }
        L.pictureUrl(path).then(function (url) {
          if (!url) { img.replaceWith(document.createTextNode(img.alt)); return; }
          if (find(tab.key) !== tab) { URL.revokeObjectURL(url); return; }
          if (tab.pics.has(path)) { URL.revokeObjectURL(url); url = tab.pics.get(path); } else tab.pics.set(path, url);
          img.src = url;
        });
      });
      doc.addEventListener("click", function (ev) {
        var a = ev.target.closest("a[data-path]");
        if (!a) return;
        ev.preventDefault();
        var path = a.dataset.path;
        L.kindOf(path).then(function (kind) {
          if (kind === "dir") E.openFolder("local", path); else if (kind === "file") V.open("local", path);
        });
      });
      return doc;
    }
    // Links to the repository open in a tab here (a folder opens in the tree); only what exists stays a link.
    var links = Array.prototype.slice.call(doc.querySelectorAll("a[data-path]"));
    if (links.length && A.paths) {
      A.paths.resolve(links.map(function (a) { return a.dataset.path; })).then(function (kinds) {
        links.forEach(function (a) {
          var kind = kinds[a.dataset.path];
          if (kind === "dir") a.dataset.kind = "dir";
          else if (kind !== "file" && R.state === "ok") a.replaceWith.apply(a, Array.prototype.slice.call(a.childNodes));
        });
      });
    }
    doc.addEventListener("click", function (ev) {
      var a = ev.target.closest("a[data-path]");
      if (!a || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button !== 0) return;
      ev.preventDefault();
      if (a.dataset.kind === "dir") E.openFolder("repo", a.dataset.path); else V.open("repo", a.dataset.path);
    });
    if (A.paths) A.paths.scan(doc);
    return doc;
  }

  // ------------------------------------------------------------------ starting

  var kept = A.store.get(TABS_KEY, {}) || {};
  (Array.isArray(kept.tabs) ? kept.tabs : []).forEach(function (x) {
    var source = typeof x === "string" ? "repo" : x && x.s, path = typeof x === "string" ? x : x && x.p;
    if (!S[source] || typeof path !== "string" || !A.splitPath(path)) return;
    if (source === "local") { if (!waiting.some(function (w) { return w.p === path; })) waiting.push({s: "local", p: path}); }
    else if (!find(keyOf(source, path))) tabs.push(tabFor(source, path));
  });
  var wanted = root.dataset.path;
  if (wanted && A.splitPath(wanted) && !find(keyOf("repo", wanted))) tabs.push(tabFor("repo", wanted));
  var keptActives = kept.actives && typeof kept.actives === "object" ? kept.actives : {};
  if (typeof kept.active === "string") {                  // a page of before kept one active tab for both sources
    keptActives[kept.active.indexOf("local:") === 0 ? "local" : "repo"] = kept.active;
  }
  if (typeof keptActives.local === "string" && keptActives.local.indexOf("local:") === 0) waitingActive = keptActives.local;
  var firstRepo = strip("repo")[0];
  actives.repo = wanted ? keyOf("repo", wanted)
    : typeof keptActives.repo === "string" && find(keptActives.repo) ? keptActives.repo : firstRepo ? firstRepo.key : null;
  E.start();
  activate(wanted ? "repo" : E.shown, actives[wanted ? "repo" : E.shown], false);

  // ------------------------------------------------------------------ below 900 px: the tree when nothing is open
  //
  // While the source shown has no tab (and the document has nothing else to say), the explorer is drawn in the page
  // (before the document, which is hidden), so files mode is never an empty page; a file opened goes back to the
  // drawer. The drawer then holds the rail only.

  function placeExplorer() {
    if (!el.explorer || !el.nav) return;
    var away = E.shown === "repo" && (R.state === "not_connected" || R.state === "away");
    var here = narrow.matches && !current() && !away;
    if ((el.explorer.parentNode === root) === here) return;
    var hadFocus = el.explorer.contains(document.activeElement);
    if (here) root.insertBefore(el.explorer, el.view); else el.nav.appendChild(el.explorer);
    root.classList.toggle("tree-here", here);
    if (hadFocus && !here) el.view.focus({preventScroll: true});
  }
  if (narrow.addEventListener) narrow.addEventListener("change", placeExplorer);
  R.on("state", placeExplorer);
  placeExplorer();
})();
