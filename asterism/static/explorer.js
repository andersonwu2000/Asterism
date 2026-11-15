// Files mode, the explorer (#explorer, Asterism.explorer): the repository's name and branch, a filter over the names
// already loaded, and the tree. Folders are listed on demand (GET /api/files/list, one call per folder, kept for the
// session) and listed again when the head commit changes; the root is looked at again every few seconds to notice a
// push. Files open in a tab (viewer.js). Entries of type "other" recede and cannot be opened.
// The tree is one roving tab stop: arrows move, Right and Left open and close a folder, Enter opens, a letter jumps.
// Every entry has the one menu (A.menu): by right click, by the context-menu key or Shift+F10, and by the small
// control on its row.
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("files"), box = document.getElementById("explorer");
  if (!A || !root || !box) return;
  var t = A.t, make = A.make;
  var SLUG = root.dataset.slug, REPO = root.dataset.repo, CAN_PIN = !!root.dataset.canPin;
  var API = "/" + encodeURIComponent(SLUG) + "/api/";
  var HEAD_EVERY_MS = 10000, NOTE_MS = 3000;
  var OPEN_KEY = "asterism-files-open:" + SLUG;

  var el = {tree: document.getElementById("explorer-tree"), filter: document.getElementById("explorer-filter"),
            note: document.getElementById("explorer-note"), ref: document.getElementById("explorer-ref"),
            status: document.getElementById("explorer-status")};

  var E = A.explorer = {
    ref: null, commit: null, stale: false,
    state: "loading",            // loading | ok | not_connected | away (nothing could be listed)
    message: "",                 // the server's sentence for not_connected / away
    current: null                // the file shown (marked in the tree)
  };
  var listings = new Map();      // folder ("" is the root) -> its entries, as the server ordered them
  var asking = new Map();        // folder -> the pending answer
  var open = new Set((A.store.get(OPEN_KEY, []) || []).filter(function (p) { return typeof p === "string"; }));
  var notes = new Map();         // path -> a short note shown on its row for a moment
  var failed = new Set();        // folders GitHub could not list this time
  var focusPath = null, query = "";
  var listeners = {commit: [], state: []};
  E.on = function (what, fn) { listeners[what].push(fn); };
  function emit(what) { listeners[what].forEach(function (fn) { fn(); }); }

  function parentOf(path) { var i = path.lastIndexOf("/"); return i < 0 ? "" : path.slice(0, i); }
  function nameOf(path) { return path.slice(path.lastIndexOf("/") + 1); }
  function ancestors(path) {
    var out = [], p = parentOf(path);
    while (p) { out.unshift(p); p = parentOf(p); }
    return out;
  }
  function saveOpen() { A.store.set(OPEN_KEY, Array.from(open)); }

  E.githubUrl = function (path, folder) { return A.githubUrl(REPO, E.ref, path, folder); };

  // ------------------------------------------------------------------ listing

  function setState(state, message) {
    if (E.state === state && E.message === (message || "")) return;
    E.state = state;
    E.message = message || "";
    emit("state");
  }

  function showHead() {
    el.ref.textContent = A.githubUrl(REPO, null, "") ? REPO.replace(/^https:\/\/github\.com\//i, "").replace(/\/+$/, "")
      .replace(/\.git$/, "") + (E.ref ? " · " + E.ref : "") : REPO;
    el.note.hidden = !E.stale;
    el.note.textContent = E.stale ? t("files.stale") : "";
  }

  // The listing of a folder: kept for the session; `fresh` asks again (the head, or after a push).
  E.list = function (folder, fresh) {
    if (!fresh && listings.has(folder)) return Promise.resolve(listings.get(folder));
    if (asking.has(folder)) return asking.get(folder);
    var p = (async function () {
      var r = await A.request(API + "files/list", {dir: folder});
      asking.delete(folder);
      if (r.ok) failed.delete(folder);
      else if (r.status !== 404 && r.data.error !== "not_connected") failed.add(folder);
      if (r.ok) {
        var d = r.data;
        E.ref = d.ref;
        E.stale = !!d.stale;
        setState("ok");
        if (E.commit && d.commit !== E.commit) {          // a push: everything listed may have changed
          E.commit = d.commit;
          listings.clear();
          listings.set(folder, d.entries || []);
          showHead();
          await relistOpen();
          emit("commit");
          return listings.get(folder);
        }
        E.commit = d.commit;
        listings.set(folder, d.entries || []);
        showHead();
        draw();
        return listings.get(folder);
      }
      if (r.data.error === "not_connected") {
        listings.clear();
        setState("not_connected", r.data.message);
      } else if (r.status === 404) {                     // the folder is gone
        listings.delete(folder);
        open.delete(folder);
        saveOpen();
      } else if (r.data.error === "github_unavailable" || !r.ok) {
        E.stale = true;
        if (!listings.size) setState("away", r.data.message);
      }
      showHead();
      draw();
      return null;
    })();
    asking.set(folder, p);
    draw();
    return p;
  };

  async function relistOpen() {
    var folders = [""].concat(Array.from(open).sort());
    for (var i = 0; i < folders.length; i++) {
      if (folders[i] && !listings.has(parentOf(folders[i]))) continue;
      if (!listings.has(folders[i])) await E.list(folders[i], true);
    }
    draw();
  }

  // Show a path in the tree: its folders open (listed when needed) and, when asked, the row focused.
  E.reveal = async function (path, focus) {
    var chain = ancestors(path);
    for (var i = 0; i < chain.length; i++) {
      open.add(chain[i]);
      await E.list(chain[i]);
    }
    saveOpen();
    draw();
    if (focus) focusRow(path);
    var row = rowOf(path);
    if (row) row.scrollIntoView({block: "nearest"});
  };
  E.setCurrent = function (path) {
    E.current = path;
    if (path) E.reveal(path, false); else draw();
  };
  // A folder opened from elsewhere (a link in a document).
  E.openFolder = async function (path) {
    var chain = ancestors(path).concat([path]);
    for (var i = 0; i < chain.length; i++) {
      open.add(chain[i]);
      await E.list(chain[i]);
    }
    saveOpen();
    draw();
    focusRow(path);
  };

  // ------------------------------------------------------------------ the tree

  // The rows in tree order: {entry, level, setsize, posinset} or {placeholder, level}.
  function rows() {
    var out = [], filter = query.toLowerCase(), keep = null;
    if (filter) {
      keep = new Set();
      listings.forEach(function (entries) {
        entries.forEach(function (e) {
          if (e.name.toLowerCase().indexOf(filter) < 0) return;
          keep.add(e.path);
          ancestors(e.path).forEach(function (a) { keep.add(a); });
        });
      });
    }
    (function walk(folder, level) {
      var entries = listings.get(folder);
      if (!entries) {
        if (folder && !keep) {
          out.push({placeholder: asking.has(folder) ? "files.loading" : failed.has(folder) ? "files.unlisted" : null, level: level});
        }
        return;
      }
      var shown = keep ? entries.filter(function (e) { return keep.has(e.path); }) : entries;
      if (!shown.length && folder && !keep) out.push({placeholder: "files.empty_folder", level: level});
      shown.forEach(function (e, i) {
        out.push({entry: e, level: level, setsize: shown.length, posinset: i + 1});
        if (e.type === "dir" && (keep ? keep.has(e.path) && listings.has(e.path) : open.has(e.path))) walk(e.path, level + 1);
      });
    })("", 1);
    return out;
  }

  function rowOf(path) {
    return el.tree.querySelector('[data-path="' + path.replace(/["\\]/g, "\\$&") + '"]');
  }

  var drawn = "";
  function draw() {
    var list = rows();
    var key = JSON.stringify([list.map(function (r) { return r.entry ? r.entry.path + r.entry.type : r.placeholder; }),
                              Array.from(open), E.current, focusPath, query, Array.from(notes.entries())]);
    if (key === drawn) return;
    drawn = key;
    var hadFocus = el.tree.contains(document.activeElement);
    var paths = list.filter(function (r) { return r.entry; }).map(function (r) { return r.entry.path; });
    if (paths.indexOf(focusPath) < 0) focusPath = paths.indexOf(E.current) >= 0 ? E.current : paths[0] || null;
    var frag = document.createDocumentFragment();
    list.forEach(function (r) {
      if (!r.entry) {
        var li = make("li", "tree-row placeholder", r.placeholder ? t(r.placeholder) : "");
        li.setAttribute("role", "none");
        li.style.setProperty("--level", r.level);
        frag.appendChild(li);
        return;
      }
      frag.appendChild(row(r));
    });
    el.tree.textContent = "";
    el.tree.appendChild(frag);
    if (query && !paths.length) {
      var none = make("li", "tree-row placeholder", t("files.no_match", {q: query}));
      none.setAttribute("role", "none");
      el.tree.appendChild(none);
    }
    if (hadFocus && focusPath) focusRow(focusPath);
  }

  function row(r) {
    var e = r.entry, li = make("li", "tree-row " + e.type);
    li.setAttribute("role", "treeitem");
    li.dataset.path = e.path;
    li.setAttribute("aria-level", String(r.level));
    li.setAttribute("aria-setsize", String(r.setsize));
    li.setAttribute("aria-posinset", String(r.posinset));
    li.style.setProperty("--level", r.level);
    li.tabIndex = e.path === focusPath ? 0 : -1;
    li.title = e.path;
    if (e.type === "dir") {
      var expanded = query ? listings.has(e.path) : open.has(e.path);
      li.setAttribute("aria-expanded", String(expanded));
      li.appendChild(make("span", "twisty" + (expanded ? " open" : "")));
      li.firstChild.setAttribute("aria-hidden", "true");
    } else {
      li.appendChild(make("span", "twisty none"));
      li.firstChild.setAttribute("aria-hidden", "true");
    }
    if (e.type === "file") li.setAttribute("aria-selected", String(e.path === E.current));
    if (e.type === "other") li.setAttribute("aria-disabled", "true");
    li.appendChild(make("span", "tree-name", e.name));
    var note = notes.get(e.path);
    if (note) li.appendChild(make("span", "row-note", note));
    if (e.type !== "other") {
      // For the pointer and touch; the keyboard has the context-menu key and Shift+F10.
      var acts = A.button("row-acts", null, function (ev) {
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
    var entries = listings.get(parentOf(path)) || [];
    for (var i = 0; i < entries.length; i++) if (entries[i].path === path) return entries[i];
    return null;
  }

  async function toggle(path, want) {
    var on = want === undefined ? !open.has(path) : want;
    if (on) open.add(path); else open.delete(path);
    saveOpen();
    draw();
    if (on) await E.list(path);
  }

  function activate(e) {
    if (e.type === "dir") { toggle(e.path); return; }
    if (e.type !== "file") return;
    if (A.viewer) A.viewer.open(e.path);
    el.status.textContent = t("files.opened", {name: e.name});
    if (A.rail && A.rail.isDrawer()) {                 // below 900 px: the file is what the reader wanted to see
      A.rail.closeDrawer(false);
      document.getElementById("file-view").focus({preventScroll: true});
    }
  }

  el.tree.addEventListener("click", function (ev) {
    var li = ev.target.closest("[role=treeitem]");
    if (!li) return;
    var e = entryOf(li.dataset.path);
    focusRow(li.dataset.path);
    if (e) activate(e);
  });
  el.tree.addEventListener("contextmenu", function (ev) {
    var li = ev.target.closest("[role=treeitem]");
    if (!li) return;
    var e = entryOf(li.dataset.path);
    if (!e || e.type === "other") return;
    ev.preventDefault();
    focusRow(li.dataset.path);
    menuFor(e, ev.clientX || ev.clientY ? {x: ev.clientX, y: ev.clientY} : {anchor: li}, li);
  });
  el.tree.addEventListener("keydown", function (ev) {
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
      else if (items[i + 1] && parentOf(items[i + 1].dataset.path) === e.path) go(i + 1);
    } else if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      if (e && e.type === "dir" && li.getAttribute("aria-expanded") === "true" && !query) toggle(e.path, false);
      else if (parentOf(li.dataset.path)) focusRow(parentOf(li.dataset.path));
    } else if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      if (e) activate(e);
    } else if (ev.key === "ContextMenu" || (ev.key === "F10" && ev.shiftKey)) {
      ev.preventDefault();
      if (e && e.type !== "other") menuFor(e, {anchor: li}, li);
    } else if (ev.key.length === 1 && /\S/.test(ev.key) && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
      var k = ev.key.toLowerCase();
      for (var j = 1; j <= items.length; j++) {
        var x = items[(i + j) % items.length];
        if (nameOf(x.dataset.path).toLowerCase().indexOf(k) === 0) { go((i + j) % items.length); break; }
      }
    }
  });

  // ------------------------------------------------------------------ the filter

  el.filter.addEventListener("input", function () {
    query = el.filter.value.trim();
    draw();
  });
  el.filter.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && el.filter.value) { ev.preventDefault(); ev.stopPropagation(); el.filter.value = ""; query = ""; draw(); }
    else if (ev.key === "ArrowDown" && focusPath) { ev.preventDefault(); focusRow(focusPath); }
  });

  // ------------------------------------------------------------------ the menu of an entry

  function note(path, text) {
    notes.set(path, text);
    el.status.textContent = text;
    draw();
    setTimeout(function () { if (notes.get(path) === text) { notes.delete(path); draw(); } }, NOTE_MS);
  }

  function channels() {
    var places = A.side && A.side.places;
    return places ? places.channels.map(function (c) { return c.name; }) : [];
  }

  async function pin(path, channel) {
    var r = await A.request(API + "channels/" + encodeURIComponent(channel) + "/pins", null, {path: path});
    note(path, r.ok ? t("files.pinned", {name: channel}) : A.refusal("files.pin_refused", r.data));
    if (r.ok && A.side) A.side.refresh();
  }

  // The acts on a file or a folder. Shared with the tab strip (viewer.js).
  E.menuItems = function (path, folder) {
    var items = [{label: t("files.copy"), run: async function () {
      var ok = false;
      try { ok = await A.copy(path); } catch (err) { ok = false; }
      note(path, t(ok ? "files.copied" : "files.copy_failed"));
    }}];
    if (!folder && CAN_PIN) {
      var names = channels();
      items.push({label: t("files.pin"), disabled: !names.length, items: names.map(function (n) {
        return {label: t("files.pin_to", {name: n}), run: function () { pin(path, n); }};
      })});
    }
    if (!folder) {
      items.push({label: t("files.mention"), run: function () {
        A.store.set(A.rail.mentionKey, "`" + path + "`");
        window.location.href = A.rail.chatHref();
      }});
    }
    var gh = E.githubUrl(path, folder);
    if (gh) items.push({separator: true}, {label: t("files.open_github"), href: gh, external: true});
    return items;
  };

  function menuFor(e, where, opener) {
    where.label = t("files.acts", {name: e.name});
    A.menu(where, E.menuItems(e.path, e.type === "dir"), opener);
  }

  // ------------------------------------------------------------------ starting

  E.start = async function () {
    showHead();
    await E.list("");
    if (E.state !== "ok") return;
    var chain = Array.from(open).sort();
    for (var i = 0; i < chain.length; i++) {
      if (listings.has(parentOf(chain[i]))) await E.list(chain[i]);
    }
    draw();
  };
  // A push shows up: the root is asked again on the page's rhythm (the server keeps the head for its refresh time).
  setInterval(function () { if (!document.hidden) E.list("", true); }, HEAD_EVERY_MS);
})();
