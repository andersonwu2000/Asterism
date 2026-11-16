// Files mode, a folder of the reader's own computer as a source of files (Asterism.sources.local), through the File
// System Access API (Chromium browsers only).
//
// NOTHING OF A LOCAL FILE EVER REACHES THE SERVER: not its content, not its name or path, not the folder's name.
// This module makes no request at all. Whatever it hands to the rest of the page (names, paths, text, object URLs)
// must not be put into a request, an address the server sees, or a log. A local tab has no address of its own.
//
// What it owns:
// - permission: the folder is opened for reading (#local-open); writing is asked for at the first save or change.
//   The folder's handle is kept in IndexedDB per project; on a later visit one press (#local-restore) asks for
//   access again (the browser decides whether it asks the reader), and #local-forget forgets the folder;
// - listing: a folder is listed when it is opened, folders first, by name without regard to case, never `.git`;
// - reading: a file is shown by the same kinds as one of the repository; pictures and PDFs through object URLs;
//   text that is valid UTF-8 and at most 5 MB is editable, its line ending (LF or CRLF) and byte-order mark kept;
// - writing: saving first compares the disk with what was loaded (time and size, then the bytes) and writes nothing
//   when they differ; new file, new folder, rename, delete;
// - watching: `changed()` tells whether the disk moved away from what was loaded (the viewer asks on focus and on a
//   rhythm while a file shows);
// - finding: `walk()` lists the whole folder (never `.git`), at most WALK_MOST entries, for the file search.
// The explorer (explorer.js) and the tab strip (viewer.js) speak to it through the interface the repository has
// (repo.js): id, state, on, listed, pending, failed, list, read, menuItems.
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("files");
  if (!A || !root) return;
  var t = A.t, SLUG = root.dataset.slug;
  var EDIT_MAX = 5 * 1024 * 1024, SHOW_MAX = 20 * 1024 * 1024, SNIFF = 8000, WALK_MOST = 20000, WALK_KEEP_MS = 30000;
  var PICTURES = {png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", gif: "image/gif", webp: "image/webp", svg: "image/svg+xml"};
  var DB = "asterism-local", STORE = "folders";

  var L = {
    id: "local",
    supported: typeof window.showDirectoryPicker === "function",
    state: "none",               // unsupported | none (no folder) | closed (known, access to restore) | ok
    name: "",                    // the folder's own name: shown on this page only
    message: ""
  };
  A.sources = A.sources || {};
  A.sources.local = L;

  var dir = null;                // the folder's handle
  var listings = new Map(), asking = new Map(), failed = new Set();
  var listeners = {listing: [], state: [], moved: [], removed: []};
  L.on = function (what, fn) { listeners[what].push(fn); };
  function emit(what, arg) { listeners[what].forEach(function (fn) { fn(arg); }); }

  function parentOf(path) { var i = path.lastIndexOf("/"); return i < 0 ? "" : path.slice(0, i); }
  function nameOf(path) { return path.slice(path.lastIndexOf("/") + 1); }
  function join(folder, name) { return folder ? folder + "/" + name : name; }
  function setState(state) { L.state = state; emit("state"); }

  // ------------------------------------------------------------------ the handle, kept in IndexedDB per project

  function db() {
    return new Promise(function (resolve, reject) {
      var r = indexedDB.open(DB, 1);
      r.onupgradeneeded = function () { r.result.createObjectStore(STORE); };
      r.onsuccess = function () { resolve(r.result); };
      r.onerror = function () { reject(r.error); };
    });
  }
  async function kept(op, value) {
    var d = await db();
    try {
      return await new Promise(function (resolve, reject) {
        var tx = d.transaction(STORE, op === "get" ? "readonly" : "readwrite"), s = tx.objectStore(STORE);
        var r = op === "get" ? s.get(SLUG) : op === "put" ? s.put(value, SLUG) : s.delete(SLUG);
        tx.oncomplete = function () { resolve(r.result); };
        tx.onerror = tx.onabort = function () { reject(tx.error); };
      });
    } finally { d.close(); }
  }

  async function permitted(handle, mode, ask) {
    var opts = {mode: mode};
    if (typeof handle.queryPermission === "function" && await handle.queryPermission(opts) === "granted") return true;
    if (!ask || typeof handle.requestPermission !== "function") return false;
    return await handle.requestPermission(opts) === "granted";
  }

  function reset() {
    listings.clear();
    asking.clear();
    failed.clear();
    walked = null;
  }

  L.start = async function () {
    if (!L.supported) { setState("unsupported"); return; }
    var handle = null;
    try { handle = await kept("get"); } catch (err) { handle = null; }
    if (!handle) { setState("none"); return; }
    dir = handle;
    L.name = handle.name;
    var granted = false;
    try { granted = await permitted(handle, "read", false); } catch (err) { granted = false; }
    if (granted) { setState("ok"); await L.list(""); } else setState("closed");
  };

  // #local-open: the reader picks a folder (read only).
  L.open = async function () {
    var handle;
    try {
      handle = await window.showDirectoryPicker({mode: "read"});
    } catch (err) {
      return err && err.name === "AbortError" ? {ok: true, cancelled: true} : refusal(err);
    }
    try { await kept("put", handle); } catch (err) { /* this visit only */ }
    dir = handle;
    L.name = handle.name;
    reset();
    setState("ok");
    await L.list("");
    return {ok: true};
  };

  // #local-restore: one press, and the browser decides whether to ask the reader.
  L.restore = async function () {
    if (!dir) return {ok: false, message: t("local.gone")};
    var granted = false;
    try { granted = await permitted(dir, "read", true); } catch (err) { return refusal(err); }
    if (!granted) return {ok: false, message: t("local.denied")};
    reset();
    setState("ok");
    await L.list("");
    return {ok: true};
  };

  L.forget = async function () {
    try { await kept("delete"); } catch (err) { /* nothing kept */ }
    dir = null;
    L.name = "";
    reset();
    setState("none");
  };

  function refusal(err) {
    var name = err && err.name;
    var key = name === "NotAllowedError" || name === "SecurityError" ? "local.denied"
      : name === "NotFoundError" ? "local.gone"
      : name === "InvalidModificationError" ? "local.not_empty"
      : name === "TypeError" ? "local.bad_name"
      : name === "QuotaExceededError" ? "local.full"
      : null;
    return {ok: false, message: key ? t(key) : t("local.failed", {code: name || "?"})};
  }

  // ------------------------------------------------------------------ walking the folder

  async function folderHandle(path) {
    var h = dir;
    if (!h) throw new DOMException("", "NotFoundError");
    if (!path) return h;
    var segs = path.split("/");
    for (var i = 0; i < segs.length; i++) h = await h.getDirectoryHandle(segs[i]);
    return h;
  }
  async function fileHandle(path) {
    return (await folderHandle(parentOf(path))).getFileHandle(nameOf(path));
  }
  // "file", "dir" or null.
  L.kindOf = async function (path) {
    if (!A.splitPath(path)) return null;
    var parent;
    try { parent = await folderHandle(parentOf(path)); } catch (err) { return null; }
    try { await parent.getFileHandle(nameOf(path)); return "file"; } catch (err) { /* not a file */ }
    try { await parent.getDirectoryHandle(nameOf(path)); return "dir"; } catch (err) { return null; }
  };

  // ------------------------------------------------------------------ listing

  L.listed = function (folder) { return listings.get(folder); };
  L.pending = function (folder) { return asking.has(folder); };
  L.failed = function (folder) { return failed.has(folder); };

  function order(a, b) {
    if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
    var x = a.name.toLowerCase(), y = b.name.toLowerCase();
    return x < y ? -1 : x > y ? 1 : a.name < b.name ? -1 : a.name > b.name ? 1 : 0;
  }

  L.list = function (folder, fresh) {
    if (L.state !== "ok") return Promise.resolve(null);
    if (!fresh && listings.has(folder)) return Promise.resolve(listings.get(folder));
    if (asking.has(folder)) return asking.get(folder);
    var p = (async function () {
      var out = [];
      try {
        var h = await folderHandle(folder);
        for await (var pair of h.entries()) {
          var name = pair[0], kind = pair[1].kind;
          if (name === ".git") continue;                 // never the repository's own folder
          out.push({name: name, path: join(folder, name), type: kind === "directory" ? "dir" : "file"});
        }
        out.sort(order);
        failed.delete(folder);
        listings.set(folder, out);
      } catch (err) {
        listings.delete(folder);
        if (err && err.name === "NotAllowedError") { asking.delete(folder); setState("closed"); return null; }
        if (err && err.name !== "NotFoundError") failed.add(folder);
        out = null;
      }
      asking.delete(folder);
      emit("listing");
      return out;
    })();
    asking.set(folder, p);
    emit("listing");
    return p;
  };

  // The folders listed so far, again (the reader came back, or a few seconds passed): an agent may have changed them.
  L.relist = async function (folders) {
    if (L.state !== "ok") return;
    for (var i = 0; i < folders.length; i++) {
      if (listings.has(folders[i])) await L.list(folders[i], true);
    }
  };

  // ------------------------------------------------------------------ the whole folder, for the file search

  var walked = null;             // {at, entries: [{path, type}], cut} of the last walk, kept a little while

  // Every file and folder under the folder, breadth first, never `.git`; `cut` when it stopped at WALK_MOST.
  L.walk = async function (fresh) {
    if (!dir || L.state !== "ok") return null;
    if (!fresh && walked && Date.now() - walked.at < WALK_KEEP_MS) return walked;
    var out = [], cut = false, todo = [["", dir]];
    try {
      while (todo.length && !cut) {
        var next = todo.shift(), prefix = next[0];
        for await (var pair of next[1].entries()) {
          if (pair[0] === ".git") continue;
          if (out.length >= WALK_MOST) { cut = true; break; }
          var path = join(prefix, pair[0]), folder = pair[1].kind === "directory";
          out.push({path: path, type: folder ? "dir" : "file"});
          if (folder) todo.push([path, pair[1]]);
        }
      }
    } catch (err) {
      if (err && err.name === "NotAllowedError") setState("closed");
      return null;
    }
    walked = {at: Date.now(), entries: out, cut: cut};
    return walked;
  };

  // ------------------------------------------------------------------ reading

  function extension(path) { var m = /\.([A-Za-z0-9]+)$/.exec(path); return m ? m[1].toLowerCase() : ""; }

  function eolOf(text) {
    var crlf = (text.match(/\r\n/g) || []).length, lf = (text.match(/\n/g) || []).length - crlf;
    return crlf > lf ? "\r\n" : "\n";
  }

  // What the page knows of the file as it was read or last written: its time, size and bytes.
  function stampOf(file) { return {lastModified: file.lastModified, size: file.size}; }

  function decode(bytes) {
    var bom = bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf;
    var text = new TextDecoder("utf-8", {fatal: true}).decode(bom ? bytes.subarray(3) : bytes);
    return {bom: bom, eol: eolOf(text), text: text.replace(/\r\n?/g, "\n")};
  }

  // A document for the viewer: {status, kind, text, editable, why, url, stamp, bytes, bom, eol}. Pictures, PDFs and
  // downloads carry an object URL; `release(doc)` revokes it.
  L.read = async function (path) {
    var file;
    try { file = await (await fileHandle(path)).getFile(); } catch (err) {
      if (err && err.name === "NotAllowedError") { setState("closed"); return {status: "closed"}; }
      return {status: err && err.name === "NotFoundError" || err && err.name === "TypeMismatchError" ? "gone" : "error",
              code: err && err.name};
    }
    var ext = extension(path), doc = {status: "ok", stamp: stampOf(file)};
    if (PICTURES[ext] || ext === "pdf") {
      doc.kind = ext === "pdf" ? "pdf" : "image";
      // The type is set here, from the name: an SVG is shown as a picture (nothing in it runs), never as a page.
      doc.url = URL.createObjectURL(new Blob([file], {type: ext === "pdf" ? "application/pdf" : PICTURES[ext]}));
      return doc;
    }
    if (file.size > SHOW_MAX) return download(doc, file, "local.too_large_show");
    var bytes = new Uint8Array(await file.arrayBuffer());
    var head = bytes.subarray(0, SNIFF);
    if (head.indexOf(0) >= 0) return download(doc, file, null);
    var d;
    try { d = decode(bytes); } catch (err) { return download(doc, file, "local.not_utf8"); }
    doc.kind = /^(?:md|markdown)$/.test(ext) ? "markdown" : "text";
    doc.text = d.text;
    doc.bom = d.bom;
    doc.eol = d.eol;
    doc.bytes = bytes;
    doc.editable = file.size <= EDIT_MAX;
    if (!doc.editable) doc.why = t("local.read_only_large");
    return doc;
  };

  function download(doc, file, why) {
    doc.kind = "download";
    doc.why = why ? t(why) : "";
    doc.url = URL.createObjectURL(new Blob([file], {type: "application/octet-stream"}));
    return doc;
  }

  L.release = function (doc) { if (doc && doc.url) { URL.revokeObjectURL(doc.url); doc.url = null; } };

  // A picture a local Markdown file points to: an object URL (the caller revokes it), or null.
  L.pictureUrl = async function (path) {
    var type = PICTURES[extension(path)];
    if (!type) return null;
    try {
      var file = await (await fileHandle(path)).getFile();
      return URL.createObjectURL(new Blob([file], {type: type}));
    } catch (err) { return null; }
  };

  function sameBytes(a, b) {
    if (!a || !b || a.length !== b.length) return false;
    for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
    return true;
  }

  // Did the disk move away from `doc`? null when it did not (a new time with the same bytes only updates the
  // stamp); else {doc} with what is on disk now, or {gone: true}.
  L.changed = async function (path, doc) {
    var file;
    try { file = await (await fileHandle(path)).getFile(); } catch (err) {
      return err && err.name === "NotFoundError" ? {gone: true} : null;
    }
    if (file.lastModified === doc.stamp.lastModified && file.size === doc.stamp.size) return null;
    var bytes = new Uint8Array(await file.arrayBuffer());
    if (sameBytes(bytes, doc.bytes)) { doc.stamp = stampOf(file); return null; }
    return {doc: await L.read(path)};
  };

  // ------------------------------------------------------------------ writing

  async function writable() {
    if (!dir) return false;
    return permitted(dir, "readwrite", true);
  }

  function encode(text, doc) {
    var body = new TextEncoder().encode(doc.eol === "\r\n" ? text.replace(/\n/g, "\r\n") : text);
    if (!doc.bom) return body;
    var out = new Uint8Array(body.length + 3);
    out.set([0xef, 0xbb, 0xbf], 0);
    out.set(body, 3);
    return out;
  }

  // Save `text` (lines joined by "\n") over the file `doc` was read from. Unless `force`, the disk is compared with
  // `doc` first and nothing is written when it changed: {conflict: true}. On success `doc` describes the disk again.
  L.save = async function (path, text, doc, force) {
    try {
      if (!await writable()) return {ok: false, message: t("local.denied_write")};
      if (!force) {
        var moved = await L.changed(path, doc);
        if (moved) return moved.gone ? {ok: false, gone: true, message: t("local.gone")} : {ok: false, conflict: true};
      }
      var bytes = encode(text, doc), h = await fileHandle(path);
      var w = await h.createWritable({keepExistingData: false});
      await w.write(bytes);
      await w.close();
      var file = await h.getFile();
      doc.stamp = stampOf(file);
      doc.bytes = bytes;
      doc.text = text;
      return {ok: true};
    } catch (err) {
      return refusal(err);
    }
  };

  // A name for a new entry or a rename: like a path of the repository, one name.
  L.badName = function (name) {
    return !name || name === "." || name === ".." || /[\/\\\u0000-\u001f\u007f-\u009f]/.test(name);
  };

  async function exists(folder, name) {
    var h = await folderHandle(folder);
    try { await h.getFileHandle(name); return true; } catch (err) { /* not a file */ }
    try { await h.getDirectoryHandle(name); return true; } catch (err) { return false; }
  }

  async function change(folder, name, work) {
    if (L.badName(name)) return {ok: false, message: t("local.bad_name")};
    try {
      if (!await writable()) return {ok: false, message: t("local.denied_write")};
      if (await exists(folder, name)) return {ok: false, message: t("local.exists", {name: name})};
      await work(await folderHandle(folder));
    } catch (err) {
      return refusal(err);
    }
    await L.list(folder, true);
    return {ok: true, path: join(folder, name)};
  }

  L.createFile = function (folder, name) {
    return change(folder, name, function (h) { return h.getFileHandle(name, {create: true}); });
  };
  L.createFolder = function (folder, name) {
    return change(folder, name, function (h) { return h.getDirectoryHandle(name, {create: true}); });
  };

  L.rename = async function (path, name) {
    var folder = parentOf(path);
    if (name === nameOf(path)) return {ok: true, path: path};
    var res = await change(folder, name, async function (h) {
      var from = await h.getFileHandle(nameOf(path));
      if (typeof from.move === "function") {
        try { await from.move(name); return; } catch (err) { if (err && err.name !== "NotSupportedError") throw err; }
      }
      // Without move(): the bytes into a new file, then the old one away.
      var data = await (await from.getFile()).arrayBuffer();
      var to = await h.getFileHandle(name, {create: true});
      var w = await to.createWritable({keepExistingData: false});
      await w.write(data);
      await w.close();
      await h.removeEntry(nameOf(path));
    });
    if (res.ok) emit("moved", {from: path, to: res.path});
    return res;
  };

  // A file, or a folder that is empty. Answers as A.gone expects: {ok} or {ok: false, data: {message}}.
  L.remove = async function (path, isFolder) {
    var folder = parentOf(path);
    try {
      if (!await writable()) return {ok: false, data: {message: t("local.denied_write")}};
      var parent = await folderHandle(folder);
      if (isFolder) {
        var h = await parent.getDirectoryHandle(nameOf(path));
        for await (var x of h.keys()) { if (x !== undefined) return {ok: false, data: {message: t("local.not_empty")}}; }
      }
      await parent.removeEntry(nameOf(path));
    } catch (err) {
      return {ok: false, data: {message: refusal(err).message}};
    }
    listings.delete(path);
    await L.list(folder, true);
    emit("removed", {path: path, folder: !!isFolder});
    return {ok: true};
  };

  // ------------------------------------------------------------------ the menu of an entry

  // `ui`: what the explorer lends (say on a row, ask for a name in the tree, the shared copy and mention items).
  L.menuItems = function (entry, ui) {
    var path = entry.path, folder = entry.type === "dir", items = [];
    if (folder) {
      items.push({label: t("local.new_file"), run: function () {
        ui.ask({folder: path, kind: "file", run: function (name) { return L.createFile(path, name); }});
      }});
      items.push({label: t("local.new_folder"), run: function () {
        ui.ask({folder: path, kind: "dir", run: function (name) { return L.createFolder(path, name); }});
      }});
    } else {
      items.push({label: t("local.rename"), run: function () {
        ui.ask({rename: path, run: function (name) { return L.rename(path, name); }});
      }});
    }
    if (path) {
      items.push({label: t("local.delete"), run: function () {
        A.gone({title: t(folder ? "gone.local_folder.title" : "gone.local_file.title", {name: entry.name}),
                text: t(folder ? "gone.local_folder.text" : "gone.local_file.text", {name: entry.name}),
                name: entry.name, button: t("gone.local.button"), opener: ui.opener(path),
                run: function () { return L.remove(path, folder); },
                done: function () { ui.focus(parentOf(path)); }});
      }});
      items.push({separator: true}, ui.copyItem(path));
      if (!folder) items.push(ui.mentionItem(path));
    }
    return items;
  };
})();
