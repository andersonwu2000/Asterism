// Files mode, the tab strip (#file-tabs) and the document (#file-view), Asterism.viewer.
// The strip says what is open; the explorer chooses. Tabs are per source (the repository, repo.js, or the local
// folder, local.js): the same path can be open from both, and a local tab carries a mark saying so. One tab per open
// file (its name, the full path as its title, a close control; a middle click also closes); it scrolls sideways and
// never wraps; the arrow keys move between tabs and Delete closes one. A tab with unsaved changes carries a filled
// disc after its name and says so in its name for assistive technology; closing it, or leaving the page, asks first.
// At the strip's far right: the view switch (#view-switch: rendered, source, or source on the left with the
// rendering on the right; what makes no sense for the file is disabled) and one more control: "open on GitHub"
// (#file-github) for a file of the repository, save (#file-save, also Ctrl+S / Cmd+S) for a local one.
// The tabs, the active one and the view chosen per kind of file are kept in localStorage; the address names the
// active file of the repository (a local tab has no address: nothing of it reaches the server). Local tabs come back
// when access to the folder is restored.
// A document is shown by its kind: Markdown rendered (render.js) in a reading column, pictures as pictures (an SVG
// too, never inlined), a PDF in the browser's own viewer in a frame, anything else as one sentence and a link. The
// source view is the editor (editor.js) for both sources: read only for the repository, editable for a local text
// file. A local file that is open and unchanged follows the disk by itself; with unsaved changes it is never
// overwritten silently: saving compares first, and the reader chooses in place.
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
            save: document.getElementById("file-save"), status: document.getElementById("explorer-status")};
  var MODES = {markdown: ["rendered", "source", "split"], text: ["source"], image: ["rendered"], pdf: ["rendered"]};

  var V = A.viewer = {};
  // {source, path, key, status: idle|loading|ok|gone|too_large|unavailable|not_connected|error|closed, doc, editor,
  //  dirty, conflict, said, snap, scroll, pics: Map(path -> object URL)}
  var tabs = [];
  var active = null;             // the key of the active tab
  var waiting = [], waitingActive = null;      // local tabs of an earlier visit, until access returns
  var views = A.store.get(VIEW_KEY, {}) || {};

  function keyOf(source, path) { return source + ":" + path; }
  function nameOf(path) { return path.slice(path.lastIndexOf("/") + 1); }
  function find(key) { for (var i = 0; i < tabs.length; i++) if (tabs[i].key === key) return tabs[i]; return null; }
  function tabFor(source, path) {
    return {source: source, path: path, key: keyOf(source, path), status: "idle", doc: null, editor: null, dirty: false,
            conflict: false, said: "", pics: new Map()};
  }
  function save() {
    A.store.set(TABS_KEY, {tabs: tabs.map(function (x) { return {s: x.source, p: x.path}; }).concat(waiting),
                           active: active || waitingActive});
  }
  function editable(tab) { return !!(tab && tab.source === "local" && tab.status === "ok" && tab.doc && tab.doc.editable); }

  // ------------------------------------------------------------------ opening and closing

  V.open = function (source, path) {
    if (!S[source] || !A.splitPath(path)) return;
    if (!find(keyOf(source, path))) tabs.push(tabFor(source, path));
    activate(keyOf(source, path), true, true);
  };

  // `chosen`: the reader chose this tab (or it is the one restored), so the explorer shows its source too.
  function activate(key, focusTab, chosen) {
    var tab = find(key);
    active = tab ? key : null;
    save();
    var where = tab && tab.source === "repo" ? A.fileHref(SLUG, tab.path) : A.fileHref(SLUG, "").replace(/\/$/, "");
    if (window.location.pathname !== where || window.location.hash) history.replaceState(null, "", where);
    E.setCurrent(tab ? tab.source : E.shown, tab ? tab.path : null, !!chosen);
    drawTabs(focusTab);
    if (tab && tab.status === "idle") load(tab);
    else { draw(); follow(tab); }
  }

  function release(tab) {
    if (tab.doc) S[tab.source].release(tab.doc);
    tab.pics.forEach(function (url) { URL.revokeObjectURL(url); });
    tab.pics.clear();
    if (tab.editor) { tab.editor.destroy(); tab.editor = null; }
    clearTimeout(tab.renderTimer);
  }

  function close(key) {
    var tab = find(key), i = tabs.indexOf(tab);
    if (i < 0) return;
    if (shownTab === tab) shownTab = null;
    release(tab);
    tabs.splice(i, 1);
    var next = key === active ? (tabs[i] || tabs[i - 1] || null) : find(active);
    var hadFocus = el.tabs.contains(document.activeElement);
    activate(next ? next.key : null, false);
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

  var SVG = "http://www.w3.org/2000/svg";
  function localGlyph() {
    var svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("class", "tab-source");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    var p = document.createElementNS(SVG, "path");
    p.setAttribute("d", "M5 5h14v10H5zM3 19h18");
    svg.appendChild(p);
    return svg;
  }

  function drawTabs(focusTab) {
    var hadFocus = el.tabs.contains(document.activeElement);
    el.tabs.textContent = "";
    tabs.forEach(function (x, i) {
      var name = nameOf(x.path), local = x.source === "local";
      var wrap = make("div", "tab" + (x.status === "gone" ? " gone" : "") + (local ? " local" : "") + (x.dirty ? " dirty" : ""));
      wrap.dataset.key = x.key;
      wrap.setAttribute("role", "presentation");
      var b = A.button("tab-btn", null, function () { activate(x.key, true, true); });
      b.setAttribute("role", "tab");
      b.id = "tab-" + i;
      b.setAttribute("aria-selected", String(x.key === active));
      b.setAttribute("aria-keyshortcuts", "Delete");
      b.tabIndex = x.key === active ? 0 : -1;
      var shown = x.status === "gone" ? t("files.tab_gone", {name: name}) : name;
      var said = local ? t(x.dirty ? "files.tab_local_unsaved" : "files.tab_local", {name: shown})
                       : x.dirty ? t("files.tab_unsaved", {name: shown}) : null;
      b.title = (local ? t("files.local_path", {path: x.path}) : x.path) + (x.dirty ? " · " + t("files.unsaved") : "");
      if (said) b.setAttribute("aria-label", said);
      if (local) b.appendChild(localGlyph());
      b.appendChild(make("span", "tab-name", shown));
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
      el.tabs.appendChild(wrap);
    });
    var cur = active && tabButton(active);
    if (cur) {
      el.view.setAttribute("aria-labelledby", cur.id);
      cur.parentNode.scrollIntoView({block: "nearest", inline: "nearest"});
      if (focusTab && hadFocus) cur.focus();
    } else {
      el.view.removeAttribute("aria-labelledby");
    }
  }

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
    activate(to, false, true);
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
    if (tab.key === active) { draw(true); follow(tab); }
  }

  // After a push: the active file of the repository is read again, the other tabs of the repository when they are
  // next shown, and a file that is gone says so on its tab. Only the repository's paths are asked about.
  R.on("changed", async function () {
    var mine = tabs.filter(function (x) { return x.source === "repo"; });
    mine.forEach(function (x) { if (x.status !== "loading") x.status = "idle"; });
    var paths = mine.map(function (x) { return x.path; });
    if (paths.length) {
      var r = await A.request("/" + encodeURIComponent(SLUG) + "/api/files/resolve", null, {paths: paths.slice(0, 200)});
      if (r.ok) mine.forEach(function (x) { if ((r.data.found || {})[x.path] !== "file") x.status = "gone"; });
    }
    drawTabs(false);
    var cur = find(active);
    if (cur && cur.status === "idle") load(cur); else draw(true);
  });
  R.on("state", function () { draw(true); });

  // The local folder: its tabs come back when access does, and go when it is forgotten.
  L.on("state", function () {
    if (L.state === "ok" && waiting.length) {
      waiting.forEach(function (x) { if (!find(keyOf("local", x.p))) tabs.push(tabFor("local", x.p)); });
      waiting = [];
      var back = waitingActive;
      waitingActive = null;
      if (back && find(back) && (!active || !find(active))) activate(back, false, true); else { drawTabs(false); save(); }
    } else if (L.state === "none") {
      waiting = [];
      waitingActive = null;
      var before = active;
      tabs.filter(function (x) { return x.source === "local"; }).forEach(function (x) {
        if (shownTab === x) shownTab = null;
        release(x);
        tabs.splice(tabs.indexOf(x), 1);
      });
      if (before && !find(before)) activate(tabs[0] ? tabs[0].key : null, false); else { drawTabs(false); save(); draw(); }
    }
  });
  L.on("moved", function (m) {
    var tab = find(keyOf("local", m.from));
    if (!tab || find(keyOf("local", m.to))) return;
    var was = tab.key;
    tab.path = m.to;
    tab.key = keyOf("local", m.to);
    if (active === was) { active = tab.key; E.setCurrent("local", m.to); }
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
      if (!moved || find(tab.key) !== tab || tab.dirty) return;
      if (moved.gone) {
        release(tab);
        tab.doc = null;
        tab.status = "gone";
        drawTabs(false);
        if (tab.key === active) draw(true);
        return;
      }
      var doc = moved.doc, old = tab.doc;
      if (tab.editor && doc.status === "ok" && doc.kind === old.kind && !!doc.editable === !!old.editable &&
          (doc.kind === "text" || doc.kind === "markdown")) {
        tab.doc = doc;
        tab.editor.setText(doc.text);
        settle(tab);
        if (tab.key === active && modeOf(tab) !== "source") refreshRendering(tab);
        return;
      }
      L.release(old);
      if (tab.editor) { tab.editor.destroy(); tab.editor = null; }
      tab.doc = doc;
      tab.status = doc.status;
      if (tab.key === active) draw(true);
    } finally {
      tab.following = false;
    }
  }
  setInterval(function () { if (!document.hidden) follow(find(active)); }, WATCH_MS);
  window.addEventListener("focus", function () { follow(find(active)); });

  // The editor holds what the disk holds now: nothing is unsaved.
  function settle(tab) {
    tab.editor.markSaved();
    if (tab.dirty) { tab.dirty = false; drawTabs(false); drawTools(tab); }
  }

  // ------------------------------------------------------------------ saving (local files)

  async function saveTab(tab, force) {
    if (!editable(tab) || !tab.editor || tab.saving) return;
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

  el.save.addEventListener("click", function () {
    if (el.save.getAttribute("aria-disabled") === "true") return;
    saveTab(find(active));
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.defaultPrevented || !(ev.ctrlKey || ev.metaKey) || ev.altKey || (ev.key !== "s" && ev.key !== "S")) return;
    var tab = find(active);
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
    var modes = modesOf(tab), chosen = views[tab && tab.doc && tab.doc.kind];
    return modes.indexOf(chosen) >= 0 ? chosen : modes[0] || null;
  }

  function drawTools(tab) {
    var modes = modesOf(tab), mode = modeOf(tab);
    Array.prototype.forEach.call(el.sw.querySelectorAll("[data-view]"), function (b) {
      var can = modes.indexOf(b.dataset.view) >= 0;
      b.setAttribute("aria-disabled", String(!can));
      b.setAttribute("aria-pressed", String(can && b.dataset.view === mode));
    });
    var local = tab ? tab.source === "local" : E.shown === "local";
    el.github.hidden = local;
    el.save.hidden = !local;
    var gh = tab && !local ? R.githubUrl(tab.path, false) : null;
    if (gh) { el.github.href = gh; el.github.removeAttribute("aria-disabled"); }
    else { el.github.removeAttribute("href"); el.github.setAttribute("aria-disabled", "true"); }
    el.save.setAttribute("aria-disabled", String(!(editable(tab) && (tab.dirty || tab.conflict))));
  }
  E.on("source", function () { drawTools(find(active)); });

  el.sw.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-view]"), tab = find(active);
    if (!b || b.getAttribute("aria-disabled") === "true" || !tab) return;
    views[tab.doc.kind] = b.dataset.view;
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
    var tab = find(active), mode = modeOf(tab);
    drawTools(tab);
    var key = JSON.stringify([tab ? tab.key : E.shown, tab && tab.status, tab && tab.doc && tab.doc.kind, mode,
                              tab && tab.conflict, tab && tab.said, R.state]);
    if (!force && key === drawn) return;
    drawn = key;
    keepPlace();
    clearTimeout(slow);
    el.view.textContent = "";
    el.view.className = "file-view";
    shownTab = tab;
    var repoSide = tab ? tab.source === "repo" : E.shown === "repo";
    if (repoSide && (R.state === "not_connected" || (tab && tab.status === "not_connected"))) {
      var box = note(R.message || A.errorText("not_connected"));
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
      slow = setTimeout(function () { if (find(active) === tab && tab.status === "loading") note(t("files.loading")).classList.add("quiet"); }, SLOW_MS);
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
        img.addEventListener("error", function () { tab.status = "idle"; if (find(active) === tab) load(tab); }, {once: true});
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

  // The source view: the tab's own editor, kept while the tab is open (its undo history, cursor and scroll with it).
  function editorPane(tab) {
    if (!tab.editor) {
      tab.editor = A.editor.create({
        path: tab.path, text: tab.doc.text || "", readOnly: !editable(tab), label: t("files.source_of", {name: nameOf(tab.path)}),
        onChange: function (ed) {
          var was = tab.dirty;
          tab.dirty = editable(tab) && ed.dirty();
          if (was !== tab.dirty) { drawTabs(false); drawTools(tab); }
          if (tab.key === active && modeOf(tab) === "split") {
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
    if (tab.key !== active || shownTab !== tab) return;
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
  var keptActive = typeof kept.active === "string" ? kept.active : null;
  if (keptActive && keptActive.indexOf("local:") === 0 && !wanted) waitingActive = keptActive;
  var first = wanted ? keyOf("repo", wanted) : keptActive && find(keptActive) ? keptActive : waitingActive ? null : (tabs[0] && tabs[0].key) || null;
  E.start();
  activate(first, false, true);
})();
