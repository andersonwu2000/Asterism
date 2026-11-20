// Files mode, the project's repository as a source of files (Asterism.sources.repo), read through the server; a
// member whose GitHub account may push saves a text file from the page, deletes or renames a file, each committed in
// their own name (can-write, save, delete, rename): with their own GitHub authorization, or by the computer they chose
// (then can-write names it, `writer`).
// Folders are listed on demand (GET /api/files/list, one call per folder, kept for the session) and listed again
// when the head commit changes. Nothing is asked by itself to notice a push: the reader asks for the newest head by
// hand (the files menu's 重新整理, refresh()). A file is read from GET /api/files/raw/<path>. Entries of type "other" recede and cannot be opened.
// The explorer (explorer.js) and the tab strip (viewer.js) speak to it, and to a local folder (local.js), through one
// small interface:
//   id, state, on(what, fn)               what: "listing" (redraw the tree), "state", "changed" (a push), "moved"
//                                         ({from, to}: a file renamed here), "removed" ({path}: a file deleted here)
//   listed(folder) -> entries | undefined, pending(folder), failed(folder), list(folder, fresh) -> Promise
//   read(path) -> Promise of a document {status, kind, text, url, code, why}, release(doc)
//   menuItems(entry, ui) -> the acts of an entry's menu; refresh() -> Promise (the repository only)
// and, for saving (the repository only): canWrite / writeReason / writer (told by "write"), refused(reason),
// recheck(), save(path, doc, text, base, message), rename(path, name), remove(path), newFile(folder, name), wrote() (a
// write moved the server's head: listed again), badName(name), refusal(act, data), afterRefusal(code).
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
    writeReason: null,           // why not: no_token | reauth | no_push | computer_offline | computer_cannot_push |
                                 // computer_not_here; null
                                 // when they may, or when it is unknown
    writer: null                 // the computer that writes for them ({credential, label}), or null: the server
  };
  A.sources = A.sources || {};
  A.sources.repo = R;

  var listings = new Map();      // folder ("" is the root) -> its entries, as the server ordered them
  var asking = new Map();        // folder -> the pending answer
  var failed = new Set();        // folders GitHub could not list this time
  var listeners = {listing: [], state: [], changed: [], write: [], moved: [], removed: []};
  R.on = function (what, fn) { listeners[what].push(fn); };
  function emit(what, arg) { listeners[what].forEach(function (fn) { fn(arg); }); }

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
    R.writer = r.ok && r.data.writer ? r.data.writer : null;
    emit("write");
  }
  R.recheck = checkWrite;
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

  // ------------------------------------------------------------------ deleting and renaming

  // A refusal of a write in the page's words (A.refusal), with what the chosen computer said when it could not write.
  R.refusal = function (act, data) {
    var said = A.refusal(act, data);
    return data && data.error === "computer_failed" && data.detail ? said + " " + t("files.computer_said", {detail: data.detail}) : said;
  };

  // After a refused write: what it says of writing here from now on (a sign-in needed, no push; the chosen computer
  // gone or unable: asked again), and a conflict or a file gone lists the repository again, so the reader sees it.
  R.afterRefusal = function (code) {
    if (code === "github_reauth") R.refused("reauth");
    else if (code === "forbidden") R.refused("no_push");
    else if (/^computer_(offline|cannot_push|not_here)$/.test(code || "")) checkWrite();
    if (code === "conflict" || code === "not_found") R.wrote();
  };

  // The hash of the file as the server has it now: the version a delete or a rename starts from. Asked with
  // If-None-Match: *, which the server answers with the ETag alone (304), whatever the file's size.
  async function baseOf(path) {
    var r;
    try {
      r = await fetch(A.rawUrl(SLUG, path), {method: "HEAD", credentials: "same-origin", cache: "no-store",
                                             headers: {"If-None-Match": "*"}});
    } catch (err) {
      return {error: "network"};
    }
    if (r.status === 404) return {error: "not_found"};
    if (r.status === 409) return {error: "not_connected"};
    var sha = (r.headers.get("etag") || "").replace(/^W\//, "").replace(/"/g, "");
    return sha ? {sha: sha} : {error: "github_unavailable"};
  }

  // A file renamed in its folder, one commit (POST /api/files/rename). Answers as the explorer's name field expects:
  // {ok, path, said} or {ok: false, message}.
  R.rename = async function (path, name) {
    var slash = path.lastIndexOf("/"), folder = slash < 0 ? "" : path.slice(0, slash);
    if (name === path.slice(slash + 1)) return {ok: true, path: path};
    if (R.badName(name)) return {ok: false, message: A.errorText("local_bad_name")};
    var to = folder ? folder + "/" + name : name;
    var entries = await R.list(folder);
    if (entries && entries.some(function (x) { return x.name === name; })) return {ok: false, message: t("local.exists", {name: name})};
    var base = await baseOf(path);
    if (base.error) { R.afterRefusal(base.error); return {ok: false, message: R.refusal("files.rename", {error: base.error})}; }
    var r = await A.request(API + "files/rename", null, {path: path, to: to, base: base.sha});
    if (!r.ok) {
      var code = r.data && r.data.error;
      R.afterRefusal(code);
      // A conflict while the file is still what was read: the new name is taken on GitHub.
      if (code === "conflict" && r.data.current === base.sha) return {ok: false, message: t("files.rename.exists", {name: name})};
      return {ok: false, message: R.refusal("files.rename", r.data)};
    }
    emit("moved", {from: path, to: to});
    await R.wrote();
    return {ok: true, path: to, said: t("files.renamed_github")};
  };

  // A file deleted, one commit (POST /api/files/delete). Answers as A.gone expects: {ok} or {ok: false, data}.
  R.remove = async function (path) {
    var base = await baseOf(path);
    if (base.error) { R.afterRefusal(base.error); return {ok: false, data: {error: base.error}}; }
    var r = await A.request(API + "files/delete", null, {path: path, base: base.sha});
    if (!r.ok) { R.afterRefusal(r.data && r.data.error); return r; }
    emit("removed", {path: path});
    await R.wrote();
    return {ok: true};
  };

  // ------------------------------------------------------------------ the menu of an entry

  R.menuItems = function (entry, ui) {
    var path = entry.path, folder = entry.type === "dir", items = [];
    if (folder && R.canWrite) {
      items.push({label: t("files.new_file"), run: function () {
        ui.ask({folder: path, kind: "file", run: function (name) { return R.newFile(path, name); }});
      }}, {separator: true});
    }
    // A file, for who may write here: renamed in place, deleted with its name typed. Folders are not renamed or
    // deleted as such.
    if (!folder && path && R.canWrite) {
      items.push({label: t("files.rename"), run: function () {
        ui.ask({rename: path, run: function (name) { return R.rename(path, name); }});
      }}, {label: t("files.delete"), run: function () {
        var slash = path.lastIndexOf("/");
        A.gone({title: t("gone.repo_file.title", {name: entry.name}), text: t("gone.repo_file.text", {name: entry.name}),
                name: entry.name, button: t("gone.repo.button"), opener: ui.opener(path),
                refusal: function (data) { return R.refusal("files.delete", data); },
                run: function () { return R.remove(path); },
                done: function () { ui.focus(slash < 0 ? "" : path.slice(0, slash)); }});
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
