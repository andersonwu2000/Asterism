// Files mode, the project's repository as a source of files (Asterism.sources.repo), read-only through the server.
// Folders are listed on demand (GET /api/files/list, one call per folder, kept for the session) and listed again
// when the head commit changes. Nothing is asked by itself to notice a push: the reader asks for the newest head by
// hand (the files menu's 重新整理, refresh()). A file is read from GET /api/files/raw/<path>. Entries of type "other" recede and cannot be opened.
// The explorer (explorer.js) and the tab strip (viewer.js) speak to it, and to a local folder (local.js), through one
// small interface:
//   id, state, on(what, fn)               what: "listing" (redraw the tree), "state", "changed" (a push)
//   listed(folder) -> entries | undefined, pending(folder), failed(folder), list(folder, fresh) -> Promise
//   read(path) -> Promise of a document {status, kind, text, url, code, why}, release(doc)
//   menuItems(entry, ui) -> the acts of an entry's menu; refresh() -> Promise (the repository only)
"use strict";
(function () {
  var A = window.Asterism, root = document.getElementById("files");
  if (!A || !root) return;
  var t = A.t;
  var SLUG = root.dataset.slug, REPO = root.dataset.repo;
  var API = "/" + encodeURIComponent(SLUG) + "/api/";
  var MAX_BYTES = Number(root.dataset.maxBytes) || Infinity;
  var PICTURES = /\.(?:png|jpe?g|gif|webp|svg)$/i, MARKDOWN = /\.(?:md|markdown)$/i, PDF = /\.pdf$/i;

  var R = {
    id: "repo",
    ref: null, commit: null, stale: false,
    state: "loading"             // loading | ok | not_connected | away (nothing could be listed)
  };
  A.sources = A.sources || {};
  A.sources.repo = R;

  var listings = new Map();      // folder ("" is the root) -> its entries, as the server ordered them
  var asking = new Map();        // folder -> the pending answer
  var failed = new Set();        // folders GitHub could not list this time
  var listeners = {listing: [], state: [], changed: []};
  R.on = function (what, fn) { listeners[what].push(fn); };
  function emit(what) { listeners[what].forEach(function (fn) { fn(); }); }

  function setState(state) {
    if (R.state === state) return;
    R.state = state;
    emit("state");
  }

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
    // The ETag is the file's hash: a file read again after a push is the same file when it has the same one.
    var ctype = (r.headers.get("content-type") || "").toLowerCase(), doc = {status: "ok", url: url, etag: r.headers.get("etag")};
    if (ctype.indexOf("text/plain") === 0) {
      doc.kind = byName === "markdown" ? "markdown" : "text";
      doc.text = (await r.text()).replace(/^﻿/, "").replace(/\r\n?/g, "\n");
    } else {
      ctl.abort();
      doc.kind = ctype.indexOf("image/") === 0 ? "image" : ctype === "application/pdf" ? "pdf" : "download";
    }
    return doc;
  };
  R.release = function () { /* the server's addresses need no releasing */ };

  // ------------------------------------------------------------------ the menu of an entry

  R.menuItems = function (entry, ui) {
    var path = entry.path, folder = entry.type === "dir", items = [ui.copyItem(path)];
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
