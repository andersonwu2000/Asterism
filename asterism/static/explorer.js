// Files mode, the explorer (#explorer, Asterism.explorer): two sources of files (the top-left cell's two buttons
// #source-switch: 公共, the project's repository, repo.js; 私人, a folder of the reader's own computer, local.js) and
// the tree of the source shown. Both sources answer the same small interface (see repo.js), so the tree, the keyboard
// and the entry menu are one for both. Each source keeps its own tabs (viewer.js listens to "source" and shows the
// strip and the document of the source shown). A file opens in the current tab, or in a new one (viewer.js): by the
// entry menu's "open in a new tab", a middle click, Ctrl/Cmd+click, or dragging the row onto the tab strip.
// Above the tree, the files menu (#files-menu: for the local source "open folder", "restore access" when the browser
// must be asked again, and "forget folder", two steps in place; for the repository, the repository on GitHub) and the
// search field (#files-search): typing shows, in the tree's place, the paths of the source shown that hold every word,
// the words marked in each (the arrow keys and Enter open one); Escape or emptying the field gives the tree back.
// The local folder, once open, is one folder at the top of its tree, shown and handled like any folder (its name,
// folding, its entry menu). With no folder open the local source is one control (#local-open); a folder kept from an
// earlier visit is one control that restores access (#local-restore); in a browser without the File System Access
// API, one sentence and no control. A new file, a new folder and a rename ask for the name in the tree itself, and a
// refusal is said there.
// The tree is one roving tab stop: arrows move, Right and Left open and close a folder, Enter opens, a letter jumps.
// Every entry has the one menu (A.menu): by right click, by the context-menu key or Shift+F10, and by the small
// control on its row. Each row carries the kind mark of what it is (A.kindMark).
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("files"), box = document.getElementById("explorer");
  var S = A && A.sources;
  if (!A || !root || !box || !S || !S.repo || !S.local) return;
  var t = A.t, make = A.make;
  var SLUG = root.dataset.slug;
  var NOTE_MS = 3000, LOCAL_EVERY_MS = 5000, FIND_MOST = 50, FIND_PAUSE_MS = 150;
  var SOURCE_KEY = "asterism-files-source:" + SLUG;
  var OPEN_KEYS = {repo: "asterism-files-open:" + SLUG, local: "asterism-files-open-local:" + SLUG};
  var R = S.repo, L = S.local;
  var TOP = "";                  // the local folder's own path: the row at the top of its tree

  var el = {tree: document.getElementById("explorer-tree"), note: document.getElementById("explorer-note"),
            ref: document.getElementById("explorer-ref"), status: document.getElementById("explorer-status"),
            sw: document.getElementById("source-switch"),
            menu: document.getElementById("files-menu"), search: document.getElementById("files-search"),
            found: document.getElementById("files-found"), foundStatus: document.getElementById("files-found-status"),
            bar: document.getElementById("local-bar"), unsupported: document.getElementById("local-unsupported"),
            none: document.getElementById("local-none"), open: document.getElementById("local-open"),
            restore: document.getElementById("local-restore"), said: document.getElementById("local-note")};

  var E = A.explorer = {
    shown: S[A.store.get(SOURCE_KEY, "repo")] ? A.store.get(SOURCE_KEY, "repo") : "repo",
    current: null                // {source, path} of the file shown (marked in the tree of its source)
  };
  var opens = {};                // source -> the folders open in its tree ("" is the local folder itself)
  Object.keys(OPEN_KEYS).forEach(function (id) {
    opens[id] = new Set((A.store.get(OPEN_KEYS[id], [TOP]) || []).filter(function (p) { return typeof p === "string"; }));
  });
  var notes = new Map();         // path -> a short note shown on its row for a moment (the source shown)
  var asked = null;              // a name asked for in the tree: {folder | rename, kind, run, refusal, busy}
  var askInput = null, drawing = false;
  var focusPath = null;
  var listeners = {source: []};
  E.on = function (what, fn) { listeners[what].push(fn); };

  function src() { return S[E.shown]; }
  function open() { return opens[E.shown]; }
  function local() { return E.shown === "local"; }
  function parentOf(path) { var i = path.lastIndexOf("/"); return i < 0 ? "" : path.slice(0, i); }
  function nameOf(path) { return path.slice(path.lastIndexOf("/") + 1); }
  function ancestors(path) {
    var out = [], p = parentOf(path);
    while (p) { out.unshift(p); p = parentOf(p); }
    return out;
  }
  function saveOpen(id) { A.store.set(OPEN_KEYS[id], Array.from(opens[id])); }
  // The local folder's top row is a folder like the others: its entry.
  function topEntry() { return {name: L.name || t("files.source_local"), path: TOP, type: "dir", top: true}; }

  // ------------------------------------------------------------------ the two sources

  function showHead() {
    var repo = E.shown === "repo";
    el.ref.hidden = !repo;
    el.ref.textContent = R.headText();
    el.note.hidden = !(repo && R.stale);
    el.note.textContent = repo && R.stale ? t("files.stale") : "";
    Array.prototype.forEach.call(el.sw.querySelectorAll("[data-source]"), function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.source === E.shown));
    });
    var st = L.state;
    el.bar.hidden = repo || (st === "ok" && !el.said.textContent);
    el.unsupported.hidden = st !== "unsupported";
    el.none.hidden = st !== "none";
    el.open.hidden = st !== "none";
    el.restore.hidden = st !== "closed";
    if (st === "closed") el.restore.textContent = t("local.restore", {name: L.name || t("files.source_local")});
  }

  E.show = async function (id) {
    if (!S[id]) return;
    if (E.shown !== id) {
      E.shown = id;
      A.store.set(SOURCE_KEY, id);
      notes.clear();
      asked = null;
      focusPath = null;
      listeners.source.forEach(function (fn) { fn(); });
      if (el.search.value.trim()) find.run();
    }
    showHead();
    draw();
    if (src().state === "ok" || id === "repo") await relistOpen(id, false);
  };

  // The source: two buttons side by side, the one shown pressed.
  el.sw.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("[data-source]");
    if (b) E.show(b.dataset.source);
  });

  function say(text) {
    el.said.textContent = text || "";
    showHead();
  }
  async function openFolder() {
    say("");
    var res = await L.open();
    if (!res.ok) say(res.message);
    else if (!res.cancelled) { opens.local = new Set([TOP]); saveOpen("local"); if (E.shown !== "local") E.show("local"); }
  }
  async function restore() {
    say("");
    var res = await L.restore();
    if (!res.ok) say(res.message);
  }
  el.open.addEventListener("click", openFolder);
  el.restore.addEventListener("click", restore);

  // Forgetting the folder asks in place: an armed button in the local source's bar, a second press forgets it.
  function armForget() {
    var b = A.button("btn local-forget", t("local.forget_folder"));
    el.bar.hidden = false;
    el.bar.appendChild(b);
    b.addEventListener("click", async function () {
      if (!A.twoStep(b, t("local.forget_armed", {name: L.name || t("files.source_local")}))) return;
      b.remove();
      say("");
      await L.forget();
      opens.local = new Set([TOP]);
      saveOpen("local");
    });
    function drop() { setTimeout(function () { if (!b._armed && b.isConnected) { b.remove(); showHead(); } }, 0); }
    b.addEventListener("blur", drop);
    setTimeout(drop, 5200);
    A.twoStep(b, t("local.forget_armed", {name: L.name || t("files.source_local")}));
  }

  // ------------------------------------------------------------------ the files menu

  el.menu.addEventListener("click", function () {
    var items = [];
    if (local() && L.state !== "unsupported") {
      items.push({label: t("local.open"), run: openFolder});
      if (L.state === "closed") items.push({label: t("local.reauth"), run: restore});
      if (L.state === "ok" || L.state === "closed") items.push({label: t("local.forget_folder"), run: armForget});
    }
    var gh = !local() && R.githubUrl("", true);
    if (gh) items.push({label: t("files.open_github"), href: gh, external: true});
    if (!items.length) items.push({label: t("files.menu_none"), disabled: true});
    A.menu({label: t("files.menu"), anchor: el.menu}, items, el.menu);
  });

  R.on("listing", function () { if (E.shown === "repo") { showHead(); draw(); } });
  R.on("state", function () { showHead(); draw(); });
  R.on("changed", function () { relistOpen("repo", false); });
  L.on("listing", function () { if (local()) draw(); });
  L.on("state", function () {
    showHead();
    if (L.state === "ok") relistOpen("local", false); else draw();
  });

  // The folders open in a source's tree, listed (again, when `fresh`); a folder that is gone closes.
  async function relistOpen(id, fresh) {
    var s = S[id], folders = [""].concat(Array.from(opens[id]).filter(Boolean).sort());
    for (var i = 0; i < folders.length; i++) {
      var f = folders[i];
      if (f && !s.listed(parentOf(f))) continue;
      if (fresh || !s.listed(f)) {
        var got = await s.list(f, fresh);
        if (!got && f && s.state === "ok" && !s.failed(f)) { opens[id].delete(f); saveOpen(id); }
      }
    }
    if (id === E.shown) draw();
  }

  // An agent on the same computer may change the folder: what is open in the tree is listed again when the reader
  // comes back to the page and every few seconds while the local tree shows.
  function relistLocal() {
    if (local() && L.state === "ok" && !document.hidden && !asked) relistOpen("local", true);
  }
  setInterval(relistLocal, LOCAL_EVERY_MS);
  window.addEventListener("focus", relistLocal);

  // ------------------------------------------------------------------ revealing

  // Show a path in the tree of its source: its folders open (listed when needed) and, when asked, the row focused.
  E.reveal = async function (id, path, focus) {
    var s = S[id], chain = ancestors(path);
    if (id === "local") opens.local.add(TOP);
    for (var i = 0; i < chain.length; i++) {
      opens[id].add(chain[i]);
      await s.list(chain[i]);
    }
    saveOpen(id);
    if (id !== E.shown) return;
    draw();
    if (focus) focusRow(path);
    var row = rowOf(path);
    if (row) row.scrollIntoView({block: "nearest"});
  };
  // The file shown (the active tab of the source shown, viewer.js), marked in its tree.
  E.setCurrent = function (id, path) {
    E.current = path ? {source: id, path: path} : null;
    if (path) E.reveal(id, path, false); else draw();
  };
  // A folder opened from elsewhere (a link in a document, the file search).
  E.openFolder = async function (id, path) {
    if (id !== E.shown) await E.show(id);
    if (id === "local") opens.local.add(TOP);
    var chain = ancestors(path).concat([path]);
    for (var i = 0; i < chain.length; i++) {
      opens[id].add(chain[i]);
      await S[id].list(chain[i]);
    }
    saveOpen(id);
    draw();
    focusRow(path);
  };

  // ------------------------------------------------------------------ the tree

  // The rows in tree order: {entry, level, setsize, posinset}, {placeholder, level} or {ask, level}. The local
  // folder's own row comes first, and its contents one level under it.
  function rows() {
    var s = src(), out = [], start = 1;
    if (local()) {
      if (L.state !== "ok") return out;
      out.push({entry: topEntry(), level: 1, setsize: 1, posinset: 1});
      if (!open().has(TOP)) return out;
      start = 2;
    }
    (function walk(folder, level) {
      var entries = s.listed(folder);
      if (!entries) {
        if (folder || local()) {
          out.push({placeholder: s.pending(folder) ? "files.loading" : s.failed(folder) ? "files.unlisted" : null, level: level});
        }
        return;
      }
      if (asked && asked.folder === folder) out.push({ask: true, level: level});
      if (!entries.length && !(asked && asked.folder === folder)) {
        out.push({placeholder: local() && !folder ? "local.empty" : folder ? "files.empty_folder" : null, level: level});
      }
      entries.forEach(function (e, i) {
        out.push({entry: e, level: level, setsize: entries.length, posinset: i + 1});
        if (e.type === "dir" && open().has(e.path)) walk(e.path, level + 1);
      });
    })("", start);
    return out.filter(function (r) { return r.entry || r.ask || r.placeholder; });
  }

  function rowOf(path) {
    return el.tree.querySelector('[data-path="' + path.replace(/["\\]/g, "\\$&") + '"]');
  }
  function currentPath() { return E.current && E.current.source === E.shown ? E.current.path : null; }

  var drawn = "";
  function draw() {
    var list = rows();
    var key = JSON.stringify([E.shown, L.name, list.map(function (r) { return r.entry ? r.entry.path + r.entry.type : r.ask ? "?" : r.placeholder; }),
                              Array.from(open()), currentPath(), focusPath, Array.from(notes.entries()),
                              asked && [asked.folder, asked.rename, asked.refusal, asked.busy]]);
    if (key === drawn) return;
    drawn = key;
    var hadFocus = el.tree.contains(document.activeElement);
    var typing = askInput && document.activeElement === askInput;
    var range = typing ? [askInput.selectionStart, askInput.selectionEnd] : null;
    var paths = list.filter(function (r) { return r.entry; }).map(function (r) { return r.entry.path; });
    if (paths.indexOf(focusPath) < 0) focusPath = paths.indexOf(currentPath()) >= 0 ? currentPath() : paths.length ? paths[0] : null;
    var frag = document.createDocumentFragment();
    list.forEach(function (r) {
      if (r.ask) { frag.appendChild(askRow(r.level)); return; }
      if (!r.entry) {
        var li = make("li", "tree-row placeholder", t(r.placeholder));
        li.setAttribute("role", "none");
        li.style.setProperty("--level", r.level);
        frag.appendChild(li);
        return;
      }
      frag.appendChild(row(r));
    });
    drawing = true;
    el.tree.textContent = "";
    el.tree.appendChild(frag);
    if (typing && askInput.isConnected) {
      askInput.focus({preventScroll: true});
      askInput.setSelectionRange(range[0], range[1]);
    } else if (hadFocus && focusPath !== null && !(asked && askInput && askInput.isConnected)) focusRow(focusPath);
    drawing = false;
  }

  function row(r) {
    var e = r.entry, li = make("li", "tree-row " + e.type + (e.top ? " top" : ""));
    li.setAttribute("role", "treeitem");
    li.dataset.path = e.path;
    li.setAttribute("aria-level", String(r.level));
    li.setAttribute("aria-setsize", String(r.setsize));
    li.setAttribute("aria-posinset", String(r.posinset));
    li.style.setProperty("--level", r.level);
    li.tabIndex = e.path === focusPath ? 0 : -1;
    li.title = e.top ? e.name : e.path;
    if (e.type === "file") li.draggable = true;
    if (e.type === "dir") {
      var expanded = open().has(e.path);
      li.setAttribute("aria-expanded", String(expanded));
      li.appendChild(make("span", "twisty" + (expanded ? " open" : "")));
    } else {
      li.appendChild(make("span", "twisty none"));
    }
    li.firstChild.setAttribute("aria-hidden", "true");
    if (e.type === "file") li.setAttribute("aria-selected", String(e.path === currentPath()));
    if (e.type === "other") li.setAttribute("aria-disabled", "true");
    li.appendChild(A.kindMark(e.path, e.type === "dir"));
    if (asked && asked.rename === e.path && !e.top) {
      li.appendChild(askField());
    } else {
      li.appendChild(make("span", "tree-name", e.name));
    }
    var note = asked && asked.rename === e.path ? asked.refusal : notes.get(e.path);
    if (note) li.appendChild(make("span", "row-note", note));
    if (e.type !== "other" && !(asked && asked.rename === e.path)) {
      // For the pointer and touch; the keyboard has the context-menu key and Shift+F10.
      var acts = A.button("row-acts" + (e.top ? " shown" : ""), null, function (ev) {
        ev.stopPropagation();
        menuFor(e, {anchor: acts}, acts);
      });
      acts.tabIndex = -1;
      acts.setAttribute("aria-hidden", "true");
      acts.appendChild(make("span", "dots"));
      li.appendChild(acts);
    }
    return li;
  }

  function focusRow(path) {
    var r = rowOf(path);
    if (!r) return;
    focusPath = path;
    Array.prototype.forEach.call(el.tree.querySelectorAll("[role=treeitem]"), function (x) { x.tabIndex = x === r ? 0 : -1; });
    r.focus({preventScroll: true});
    r.scrollIntoView({block: "nearest"});
  }

  function entryOf(path) {
    if (local() && path === TOP) return topEntry();
    var entries = src().listed(parentOf(path)) || [];
    for (var i = 0; i < entries.length; i++) if (entries[i].path === path) return entries[i];
    return null;
  }

  async function toggle(path, want) {
    var on = want === undefined ? !open().has(path) : want, id = E.shown;
    if (on) opens[id].add(path); else opens[id].delete(path);
    saveOpen(id);
    draw();
    if (on) await S[id].list(path);
  }

  // `newTab`: the file opens in a tab of its own (else in the current tab, unless that one has unsaved changes).
  function activate(e, newTab) {
    if (e.type === "dir") { toggle(e.path); return; }
    if (e.type !== "file") return;
    if (A.viewer) A.viewer.open(E.shown, e.path, {newTab: !!newTab});
    el.status.textContent = t("files.opened", {name: e.name});
    if (A.rail && A.rail.isDrawer()) {                 // below 900 px: the file is what the reader wanted to see
      A.rail.closeDrawer(false);
      document.getElementById("file-view").focus({preventScroll: true});
    }
  }

  // The row one level up: the folder holding it (in the local tree, the folder itself for its top entries).
  function upOf(path) {
    if (local()) return path === TOP ? null : parentOf(path);
    return parentOf(path) || null;
  }

  el.tree.addEventListener("click", function (ev) {
    if (ev.target.closest(".ask-field")) return;
    var li = ev.target.closest("[role=treeitem]");
    if (!li) return;
    var e = entryOf(li.dataset.path);
    focusRow(li.dataset.path);
    if (e) activate(e, ev.ctrlKey || ev.metaKey);
  });
  // A middle click opens a file in a new tab (and does not start the browser's scrolling).
  el.tree.addEventListener("mousedown", function (ev) { if (ev.button === 1 && ev.target.closest("[role=treeitem]")) ev.preventDefault(); });
  el.tree.addEventListener("auxclick", function (ev) {
    var li = ev.button === 1 && ev.target.closest("[role=treeitem]");
    var e = li && entryOf(li.dataset.path);
    if (!e || e.type !== "file") return;
    ev.preventDefault();
    focusRow(li.dataset.path);
    activate(e, true);
  });
  // A file dragged onto the tab strip opens there in a new tab (viewer.js takes the drop).
  el.tree.addEventListener("dragstart", function (ev) {
    var li = ev.target.closest && ev.target.closest("[role=treeitem]");
    var e = li && entryOf(li.dataset.path);
    if (!e || e.type !== "file") { ev.preventDefault(); return; }
    E.dragging = {source: E.shown, path: e.path};
    ev.dataTransfer.effectAllowed = "copy";
    try { ev.dataTransfer.setData("text/plain", e.path); } catch (err) { /* the path is kept above */ }
  });
  el.tree.addEventListener("dragend", function () { E.dragging = null; });
  el.tree.addEventListener("contextmenu", function (ev) {
    if (ev.target.closest(".ask-field")) return;
    var li = ev.target.closest("[role=treeitem]");
    if (!li) return;
    var e = entryOf(li.dataset.path);
    if (!e || e.type === "other") return;
    ev.preventDefault();
    focusRow(li.dataset.path);
    menuFor(e, ev.clientX || ev.clientY ? {x: ev.clientX, y: ev.clientY} : {anchor: li}, li);
  });
  el.tree.addEventListener("keydown", function (ev) {
    if (ev.target.closest(".ask-field")) return;
    var li = ev.target.closest("[role=treeitem]");
    if (!li) return;
    var items = Array.prototype.slice.call(el.tree.querySelectorAll("[role=treeitem]"));
    var i = items.indexOf(li), e = entryOf(li.dataset.path);
    function go(j) { if (items[j]) { ev.preventDefault(); focusRow(items[j].dataset.path); } }
    if (ev.key === "ArrowDown") go(i + 1);
    else if (ev.key === "ArrowUp") go(i - 1);
    else if (ev.key === "Home") go(0);
    else if (ev.key === "End") go(items.length - 1);
    else if (ev.key === "ArrowRight" && e && e.type === "dir") {
      ev.preventDefault();
      if (li.getAttribute("aria-expanded") !== "true") toggle(e.path, true);
      else if (items[i + 1] && upOf(items[i + 1].dataset.path) === e.path) go(i + 1);
    } else if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      var up = upOf(li.dataset.path);
      if (e && e.type === "dir" && li.getAttribute("aria-expanded") === "true") toggle(e.path, false);
      else if (up !== null) focusRow(up);
    } else if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      if (e) activate(e, ev.ctrlKey || ev.metaKey);
    } else if (ev.key === "ContextMenu" || (ev.key === "F10" && ev.shiftKey)) {
      ev.preventDefault();
      if (e && e.type !== "other") menuFor(e, {anchor: li}, li);
    } else if (ev.key.length === 1 && /\S/.test(ev.key) && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
      var k = ev.key.toLowerCase();
      for (var j = 1; j <= items.length; j++) {
        var x = items[(i + j) % items.length], name = x.dataset.path === TOP && local() ? (L.name || "") : nameOf(x.dataset.path);
        if (name.toLowerCase().indexOf(k) === 0) { go((i + j) % items.length); break; }
      }
    }
  });

  // ------------------------------------------------------------------ a name asked for in the tree

  // opts: {folder, kind: "file" | "dir", run(name) -> Promise of {ok, path, message}} for a new entry in `folder`, or
  // {rename: path, run} for a new name. Enter does it, Escape or leaving the field gives up; a refusal stays on the row.
  function ask(opts) {
    if (!local()) return;
    asked = {folder: opts.folder, rename: opts.rename, kind: opts.kind, run: opts.run, refusal: "", busy: false};
    askInput = make("input", "ask-input");
    askInput.type = "text";
    askInput.autocomplete = "off";
    askInput.spellcheck = false;
    askInput.setAttribute("autocapitalize", "off");
    askInput.setAttribute("aria-label", opts.rename ? t("local.rename_label", {name: nameOf(opts.rename)})
      : t(opts.kind === "dir" ? "local.new_folder_label" : "local.new_file_label"));
    if (opts.rename) askInput.value = nameOf(opts.rename);
    askInput.addEventListener("keydown", function (ev) {
      ev.stopPropagation();
      if (ev.key === "Enter") { ev.preventDefault(); commit(); }
      else if (ev.key === "Escape") { ev.preventDefault(); giveUp(true); }
    });
    askInput.addEventListener("blur", function () {
      if (!drawing && asked && !asked.busy) setTimeout(function () { if (asked && document.activeElement !== askInput && !asked.busy) giveUp(false); }, 0);
    });
    var ready = opts.folder !== undefined ? toggle(opts.folder, true) : Promise.resolve();
    ready.then(function () {
      draw();
      askInput.focus();
      var dot = askInput.value.lastIndexOf(".");
      askInput.setSelectionRange(0, dot > 0 ? dot : askInput.value.length);
    });
  }

  function askField() {
    var wrap = make("span", "ask-field");
    wrap.appendChild(askInput);
    return wrap;
  }
  function askRow(level) {
    var li = make("li", "tree-row asking " + (asked.kind === "dir" ? "dir" : "file"));
    li.setAttribute("role", "none");
    li.style.setProperty("--level", level);
    li.appendChild(make("span", "twisty" + (asked.kind === "dir" ? "" : " none")));
    li.firstChild.setAttribute("aria-hidden", "true");
    li.appendChild(askField());
    if (asked.refusal) li.appendChild(make("span", "row-note", asked.refusal));
    return li;
  }

  function giveUp(refocus) {
    var was = asked;
    asked = null;
    askInput = null;
    draw();
    if (refocus && was) focusRow(was.rename !== undefined ? was.rename : was.folder !== undefined ? was.folder : focusPath || "");
  }

  async function commit() {
    if (!asked || asked.busy) return;
    var name = askInput.value.trim(), was = asked;
    if (L.badName(name)) {
      was.refusal = t("error.local_bad_name");
      el.status.textContent = was.refusal;
      draw();
      return;
    }
    was.busy = true;
    was.refusal = "";
    draw();
    var res = await was.run(name);
    was.busy = false;
    if (asked !== was) return;
    if (!res.ok) {
      was.refusal = res.message;
      el.status.textContent = res.message;
      draw();
      if (askInput) askInput.focus();
      return;
    }
    asked = null;
    askInput = null;
    draw();
    focusRow(res.path);
    if (!was.rename && was.kind === "file" && A.viewer) A.viewer.open("local", res.path);
    note(res.path, t(was.rename ? "local.renamed" : "local.created"));
  }

  // ------------------------------------------------------------------ the menu of an entry

  function note(path, text) {
    notes.set(path, text);
    el.status.textContent = text;
    draw();
    setTimeout(function () { if (notes.get(path) === text) { notes.delete(path); draw(); } }, NOTE_MS);
  }

  // What the explorer lends to a source's menu.
  var ui = {
    say: note,
    ask: ask,
    // After an entry is gone: its folder's row (redrawn meanwhile), else the row that had the focus.
    focus: function (path) {
      if (rowOf(path)) focusRow(path);
      else if (focusPath !== null) focusRow(focusPath);
    },
    opener: function (path) { return rowOf(path) || el.tree; },
    copyItem: function (path) {
      return {label: t("files.copy"), run: async function () {
        var ok = false;
        try { ok = await A.copy(path); } catch (err) { ok = false; }
        note(path, t(ok ? "files.copied" : "files.copy_failed"));
      }};
    },
    mentionItem: function (path) {
      // The path goes into the chat's composer, unsent: only the reader's own press sends it.
      return {label: t("files.mention"), run: function () {
        A.store.set(A.rail.mentionKey, "`" + path + "`");
        window.location.href = A.rail.chatHref();
      }};
    }
  };

  // The acts on a file or a folder of a source. Shared with the tab strip (viewer.js).
  E.menuItems = function (id, path, folder) {
    return S[id].menuItems({path: path, name: nameOf(path), type: folder ? "dir" : "file"}, ui);
  };

  function menuFor(e, where, opener) {
    where.label = t("files.acts", {name: e.name});
    var items = src().menuItems(e, ui), id = E.shown;
    if (e.type === "file") {
      items = [{label: t("files.open_new_tab"), run: function () { if (A.viewer) A.viewer.open(id, e.path, {newTab: true}); }},
               {separator: true}].concat(items);
    }
    if (e.top) items = items.concat([{separator: true}, {label: t("local.forget_folder"), run: armForget}]);
    A.menu(where, items, opener);
  }

  // ------------------------------------------------------------------ finding files by path
  //
  // The field above the tree (a combobox): the paths of the source shown that hold every word typed, without regard to
  // case, the shortest first, in the tree's place. The repository is asked (GET /api/files/find); the local folder is
  // walked here, in the browser (local.js), and nothing of it is sent anywhere. The arrow keys move, Enter opens a
  // file (Ctrl/Cmd+Enter in a new tab) or a folder in the tree; Escape, or emptying the field, gives the tree back.

  var find = (function () {
    var found = [], active = -1, timer = null, asked = 0;

    function setActive(i) {
      active = i;
      Array.prototype.forEach.call(el.found.children, function (li, j) { li.setAttribute("aria-selected", String(j === i)); });
      if (i >= 0 && el.found.children[i]) {
        el.search.setAttribute("aria-activedescendant", el.found.children[i].id);
        el.found.children[i].scrollIntoView({block: "nearest"});
      } else el.search.removeAttribute("aria-activedescendant");
    }

    function searching(on) {
      el.tree.hidden = on;
      el.found.hidden = !on;
      el.foundStatus.hidden = !on || !el.foundStatus.textContent;
      el.search.setAttribute("aria-expanded", String(on && found.length > 0));
    }

    // The path with every place a word typed occurs in it (without regard to case) marked.
    function marked(path, typed) {
      var low = path.toLowerCase(), hit = new Array(path.length).fill(false);
      typed.forEach(function (w) {
        for (var at = low.indexOf(w); at >= 0; at = low.indexOf(w, at + 1)) {
          for (var k = at; k < at + w.length; k++) hit[k] = true;
        }
      });
      var span = make("span", "find-path"), i = 0;
      while (i < path.length) {
        var j = i;
        while (j < path.length && hit[j] === hit[i]) j++;
        if (hit[i]) span.appendChild(make("mark", null, path.slice(i, j)));
        else span.appendChild(document.createTextNode(path.slice(i, j)));
        i = j;
      }
      return span;
    }

    function show(paths, sentence, q) {
      var typed = words(q || "");
      found = paths;
      el.found.textContent = "";
      paths.forEach(function (p, i) {
        var li = make("li", "found-option");
        li.id = "found-" + i;
        li.setAttribute("role", "option");
        li.title = p.path;
        li.appendChild(A.kindMark(p.path, p.type === "dir"));
        li.appendChild(marked(p.path, typed));
        li.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
        li.addEventListener("click", function (ev) { choose(i, ev.ctrlKey || ev.metaKey); });
        li.addEventListener("auxclick", function (ev) { if (ev.button === 1) { ev.preventDefault(); choose(i, true); } });
        el.found.appendChild(li);
      });
      el.foundStatus.textContent = sentence || "";
      searching(true);
      setActive(paths.length ? 0 : -1);
    }

    function words(q) { return q.toLowerCase().split(/\s+/).filter(Boolean); }

    async function run() {
      var q = el.search.value.trim(), mine = ++asked, source = E.shown;
      if (!q) { clear(false); return; }
      el.foundStatus.textContent = t("files.find_searching");
      searching(true);
      if (source === "repo") {
        var r = await A.request("/" + encodeURIComponent(SLUG) + "/api/files/find", {q: q, limit: FIND_MOST});
        if (mine !== asked) return;
        if (!r.ok) { show([], A.errorText(r.data.error)); return; }
        var paths = r.data.paths || [], said = [];
        if (!paths.length) said.push(t("files.find_none"));
        else if (paths.length >= FIND_MOST) said.push(t("files.find_more", {n: FIND_MOST}));
        if (r.data.complete === false) said.push(t("files.find_partial"));
        show(paths, said.join(" "), q);
        return;
      }
      if (L.state !== "ok") { show([], t("files.find_no_folder")); return; }
      var walked = await L.walk(false);
      if (mine !== asked) return;
      if (!walked) { show([], t("local.closed")); return; }
      var w = words(q);
      var hits = walked.entries.filter(function (e) {
        var low = e.path.toLowerCase();
        return w.every(function (x) { return low.indexOf(x) >= 0; });
      }).sort(function (a, b) { return a.path.length - b.path.length || (a.path < b.path ? -1 : a.path > b.path ? 1 : 0); });
      var notes = [];
      if (!hits.length) notes.push(t("files.find_none"));
      else if (hits.length > FIND_MOST) notes.push(t("files.find_more", {n: FIND_MOST}));
      if (walked.cut) notes.push(t("files.find_cut"));
      show(hits.slice(0, FIND_MOST), notes.join(" "), q);
    }

    // The tree again; `empty` also empties the field.
    function clear(empty) {
      clearTimeout(timer);
      asked++;
      if (empty) el.search.value = "";
      found = [];
      el.found.textContent = "";
      el.foundStatus.textContent = "";
      setActive(-1);
      searching(false);
    }

    function choose(i, newTab) {
      var p = found[i];
      if (!p) return;
      var source = E.shown;
      if (p.type === "dir") { clear(true); E.openFolder(source, p.path); return; }
      if (A.viewer) A.viewer.open(source, p.path, {newTab: !!newTab});
      el.status.textContent = t("files.opened", {name: nameOf(p.path)});
    }

    el.search.addEventListener("input", function () {
      clearTimeout(timer);
      if (!el.search.value.trim()) { clear(false); return; }
      timer = setTimeout(run, FIND_PAUSE_MS);
    });
    el.search.addEventListener("focus", function () {
      if (local() && L.state === "ok") L.walk(false);           // the walk starts while the reader types
    });
    el.search.addEventListener("keydown", function (ev) {
      var n = found.length;
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        if (n) setActive(active < 0 ? 0 : (active + (ev.key === "ArrowDown" ? 1 : n - 1)) % n);
      } else if (ev.key === "Enter" && !ev.isComposing && ev.keyCode !== 229) {
        ev.preventDefault();
        clearTimeout(timer);
        if (active >= 0) choose(active, ev.ctrlKey || ev.metaKey); else run();
      } else if (ev.key === "Escape") {
        if (!el.search.value && el.found.hidden) return;
        ev.preventDefault();
        ev.stopPropagation();
        clear(true);
      }
    });

    return {run: run, clear: clear};
  })();

  // ------------------------------------------------------------------ starting

  E.start = async function () {
    showHead();
    var both = [relistOpen("repo", false), L.start()];
    await Promise.all(both);
    showHead();
    draw();
  };
})();
