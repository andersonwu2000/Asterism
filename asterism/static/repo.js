// Files mode, the project's repository as a source of files (Asterism.sources.repo), read through the server; a
// member whose GitHub account may push saves a text file from the page, committed in their own name (can-write, save).
// Folders are listed on demand (GET /api/files/list, one call per folder, kept for the session) and listed again
// when the head commit changes. Nothing is asked by itself to notice a push: the reader asks for the newest head by
// hand (the files menu's 重新整理, refresh()). A file is read from GET /api/files/raw/<path>. Entries of type "other" recede and cannot be opened.
// The explorer (explorer.js) and the tab strip (viewer.js) speak to it, and to a local folder (local.js), through one
// small interface:
//   id, state, on(what, fn)               what: "listing" (redraw the tree), "state", "changed" (a push)
//   listed(folder) -> entries | undefined, pending(folder), failed(folder), list(folder, fresh) -> Promise
//   read(path) -> Promise of a document {status, kind, text, url, code, why}, release(doc)
//   menuItems(entry, ui) -> the acts of an entry's menu; refresh() -> Promise (the repository only)
// and, for saving (the repository only): canWrite / writeReason (told by "write"), refused(reason), save(path, doc,
// text, base, message), newFile(folder, name), wrote() (a save moved the server's head: listed again), badName(name).
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("files");
  if (!A || !root) return;
  var t = A.t;
  var SLUG = root.dataset.slug, REPO = root.dataset.repo;
  var API = "/" + encodeURIComponent(SLUG) + "/api/";
  var MAX_BYTES = Number(root.dataset.maxBytes) || Infinity;
  var PICTURES = /\.(?:png|jpe?g|gif|webp|svg)$/i, MARKDOWN = /\.(?:md|markdown)$/i, PDF = /\.pdf$/i;
  var EDIT_MAX = 5 * 1024 * 1024;                // the server saves at most this many bytes

  var R = {
    id: "repo",
    ref: null, commit: null, stale: false,
    state: "loading",            // loading | ok | not_connected | away (nothing could be listed)
    canWrite: false,             // the reader may save here, in their own GitHub name
    writeReason: null            // why not: no_token | reauth | no_push; null when they may, or when it is unknown
  };
  A.sources = A.sources || {};
  A.sources.repo = R;

  var listings = new Map();      // folder ("" is the root) -> its entries, as the server ordered them
  var asking = new Map();        // folder -> the pending answer
  var failed = new Set();        // folders GitHub could not list this time
  var listeners = {listing: [], state: [], changed: [], write: []};
  R.on = function (what, fn) { listeners[what].push(fn); };
  function emit(what) { listeners[what].forEach(function (fn) { fn(); }); }

  function setState(state) {
    if (R.state === state) return;
    R.state = state;
    if (state === "ok" && !writeAsked) checkWrite();
    emit("state");
  }

  // Whether the reader may save files here (GET /api/files/can-write): asked once the repository has been read.
  var writeAsked = false;
  async function checkWrite() {
    writeAsked = true;
    var r = await A.request(API + "files/can-write");
    R.canWrite = !!(r.ok && r.data.can_write);
    R.writeReason = r.ok ? r.data.reason || null : null;
    emit("write");
  }
  // A save was refused for want of authorization or permission: no more saving here until the page is opened again.
  R.refused = function (reason) {
    R.canWrite = false;
    R.writeReason = reason;
    emit("write");
  };

  R.githubUrl = function (path, folder) { return A.githubUrl(REPO, R.ref, path, folder); };
  // The repository's name and branch, for the explorer's head.
  R.headText = function () {
    return A.githubUrl(REPO, null, "") ? REPO.replace(/^https:\/\/github\.com\//i, "").replace(/\/+$/, "")
      .replace(/\.git$/, "") + (R.ref ? " · " + R.ref : "") : REPO;
  };

  R.listed = function (folder) { return listings.get(folder); };
  R.pending = function (folder) { return asking.has(folder); };
  R.failed = function (folder) { return failed.has(folder); };

  // The listing of a folder: kept for the session; `fresh` asks again (the head, or after a push).
  R.list = function (folder, fresh) {
    if (!fresh && listings.has(folder)) return Promise.resolve(listings.get(folder));
    if (asking.has(folder)) return asking.get(folder);
    var p = (async function () {
      var r = await A.request(API + "files/list", {dir: folder});
      asking.delete(folder);
      if (r.ok) failed.delete(folder);
      else if (r.status !== 404 && r.data.error !== "not_connected") failed.add(folder);
      if (r.ok) {
        var d = r.data;
        R.ref = d.ref;
        R.stale = !!d.stale;
        setState("ok");
        if (R.commit && d.commit !== R.commit) {          // a push: everything listed may have changed
          R.commit = d.commit;
          listings.clear();
          listings.set(folder, d.entries || []);
          emit("listing");
          emit("changed");
          return listings.get(folder);
        }
        R.commit = d.commit;
        listings.set(folder, d.entries || []);
        emit("listing");
        return listings.get(folder);
      }
      if (r.data.error === "not_connected") {
        listings.clear();
        setState("not_connected");
      } else if (r.status === 404) {                     // the folder is gone
        listings.delete(folder);
      } else {
        R.stale = true;
        if (!listings.size) setState("away");
      }
      emit("listing");
      return null;
    })();
    asking.set(folder, p);
    emit("listing");
    return p;
  };

  function kindByName(path) {
    if (MARKDOWN.test(path)) return "markdown";
    if (PICTURES.test(path)) return "image";
    if (PDF.test(path)) return "pdf";
    return null;
  }

  R.read = async function (path) {
    // What the listing already says needs no request: a file that is not there, or one too large to be fetched.
    var slash = path.lastIndexOf("/"), entries = await R.list(slash < 0 ? "" : path.slice(0, slash));
    if (entries) {
      var entry = entries.filter(function (x) { return x.path === path; })[0];
      var known = !entry || entry.type !== "file" ? "gone" : entry.size > MAX_BYTES ? "too_large" : null;
      if (known) return {status: known};
    }
    var url = A.rawUrl(SLUG, path), byName = kindByName(path), r;
    var ctl = new AbortController();
    try {
      // Pictures and PDFs are shown by the browser from the same address; only their state is asked here.
      r = await fetch(url, {method: byName === "image" || byName === "pdf" ? "HEAD" : "GET", credentials: "same-origin",
                            signal: ctl.signal, cache: "no-cache"});
    } catch (err) {
      return {status: "unavailable"};
    }
    if (r.status === 404) return {status: "gone"};
    if (r.status === 413) return {status: "too_large"};
    if (r.status === 502) return {status: "unavailable"};
    if (r.status === 409) return {status: "not_connected"};
    if (!r.ok) return {status: "error", code: String(r.status)};
    // The ETag is the file's hash: a file read again after a push is the same file when it has the same one, and a save
    // names it (sha) as the version the change started from.
    var ctype = (r.headers.get("content-type") || "").toLowerCase(), doc = {status: "ok", url: url, etag: r.headers.get("etag")};
    doc.sha = (doc.etag || "").replace(/^W\//, "").replace(/"/g, "") || null;
    if (ctype.indexOf("text/plain") === 0) {
      doc.kind = byName === "markdown" ? "markdown" : "text";
      // Its line ending and byte-order mark are kept, so that a save changes only what was edited. Only UTF-8 text of
      // at most 5 MB is editable (what the server saves); anything else is shown as it decodes.
      var bytes = new Uint8Array(await r.arrayBuffer()), text;
      doc.bom = bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf;
      try {
        text = new TextDecoder("utf-8", {fatal: true}).decode(bytes);
        doc.editable = bytes.length <= EDIT_MAX;
        if (!doc.editable) doc.lock = t("local.read_only_large");
      } catch (err) {
        text = new TextDecoder("utf-8").decode(bytes);
        doc.editable = false;
        doc.lock = t("files.read_only_utf8");
      }
      var crlf = (text.match(/\r\n/g) || []).length, lf = (text.match(/\n/g) || []).length - crlf;
      doc.eol = crlf > lf ? "\r\n" : "\n";
      doc.text = text.replace(/\r\n?/g, "\n");
    } else {
      ctl.abort();
      doc.kind = ctype.indexOf("image/") === 0 ? "image" : ctype === "application/pdf" ? "pdf" : "download";
    }
    return doc;
  };
  R.release = function () { /* the server's addresses need no releasing */ };

  // ------------------------------------------------------------------ saving

  // A name for a new file: as a local one (one name), and never `.git`.
  R.badName = function (name) {
    return !name || name === "." || name === ".." || name.toLowerCase() === ".git" || /[\/\\\u0000-\u001f\u007f-\u009f]/.test(name);
  };

  // `text` (lines joined by "\n") in the line ending and with the byte-order mark `doc` was read with.
  function encode(text, doc) {
    var out = doc && doc.eol === "\r\n" ? text.replace(/\n/g, "\r\n") : text;
    return doc && doc.bom ? "﻿" + out : out;
  }

  // One file, one commit, in the reader's own GitHub name (POST /api/files/save). `base`: the hash the change started
  // from, null for a new file. Answers {ok, status, data} as the request did.
  R.save = function (path, doc, text, base, message) {
    return A.request(API + "files/save", null, {path: path, content: encode(text, doc), base: base || null, message: message});
  };

  // The server follows its own save at once: the root is listed again, which notices the new head and tells the tree
  // and the tabs ("changed"), as after 重新整理.
  R.wrote = function () { return R.list("", true); };

  // A new file in `folder`: the name checked as a local one is, and against what the folder holds; an empty editor tab
  // opens for it (viewer.js). It reaches GitHub only when it is saved. Answers as a local creation does.
  R.newFile = async function (folder, name) {
    if (R.badName(name)) return {ok: false, message: A.errorText("local_bad_name")};
    var path = folder ? folder + "/" + name : name, kind = kindByName(path);
    if (kind && kind !== "markdown") return {ok: false, message: t("files.new_not_text")};
    var entries = await R.list(folder);
    if (entries && entries.some(function (x) { return x.name === name; })) return {ok: false, message: t("local.exists", {name: name})};
    if (!A.viewer) return {ok: false, message: A.errorText("")};
    A.viewer.create("repo", path);
    return {ok: true, path: path, opened: true, said: t("files.new_unsaved")};
  };

  // ------------------------------------------------------------------ the menu of an entry

  R.menuItems = function (entry, ui) {
    var path = entry.path, folder = entry.type === "dir", items = [];
    if (folder && R.canWrite) {
      items.push({label: t("files.new_file"), run: function () {
        ui.ask({folder: path, kind: "file", run: function (name) { return R.newFile(path, name); }});
      }}, {separator: true});
    }
    items.push(ui.copyItem(path));
    if (!folder) items.push(ui.mentionItem(path));
    var gh = R.githubUrl(path, folder);
    if (gh) items.push({separator: true}, {label: t("files.open_github"), href: gh, external: true});
    return items;
  };

  // 重新整理: the server asks GitHub for the head now; the root is then listed again, which notices a new head (also
  // one another reader's refresh brought) and tells the explorer and the tabs ("changed"). Not connected or away:
  // the listing says so again. Answers {ok, data} as the request did.
  R.refresh = async function () {
    var r = await A.request(API + "files/refresh", null, {});
    if (r.ok || r.data.error === "not_connected" || r.data.error === "github_unavailable") await R.list("", true);
    return r;
  };
})();
