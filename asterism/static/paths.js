// Paths elsewhere become links (Asterism.paths): in rendered messages, task texts and Markdown files, a path that
// names an existing file of the repository opens it in files mode. Nothing is guessed: the candidates are the text
// inside backticks and the bare tokens that contain a "/" or end in a known extension; the server is asked for them
// (POST /api/files/resolve) in one batch per render pass, the answers (misses too) are kept for the session, and only
// what the server confirms becomes a link.
//   A.paths.scan(element)        links what it holds, after the batch is answered
//   A.paths.resolve([paths])     -> Promise of {path: "file" | "dir" | false}
"use strict";
(function () {
  var A = window.Asterism, rail = document.getElementById("rail");
  if (!A || !rail) return;
  var SLUG = rail.dataset.slug, API = "/" + encodeURIComponent(SLUG) + "/api/files/resolve";
  var MOST = 200, RETRY_MS = 30000;
  var EXT = /\.(?:md|markdown|tex|sty|cls|bib|bst|lean|pdf|png|jpe?g|gif|svg|webp|txt|json|toml|ya?ml|py|ipynb|csv|tsv|rs|c|h|cc|cpp|hpp|js|ts|hs|ml|jl|sage|gp|sh|ps1|rst|org|v|agda|thy|coq)$/i;
  var TOKEN = /[^\s`'"<>()\[\]{}，。、；：！？「」『』（）《》【】]+/g;
  var LEAD = /^[.,;:!?*_~]+/, TRAIL = /[.,;:!?*_~]+$/;

  var known = new Map();             // path -> "file" | "dir" | false, for the session
  var waiting = new Map();           // path -> [resolve functions], asked in the next batch
  var timer = null, off = false, pauseUntil = 0;

  function candidate(raw) {
    var s = String(raw).trim().replace(/^\.\//, "");
    if (!s || s.length > 300 || s.indexOf("://") >= 0 || /^[\d\/.,:-]+$/.test(s)) return null;
    if (s.indexOf("/") < 0 && !EXT.test(s)) return null;
    return A.splitPath(s) ? s : null;
  }
  A.paths = {candidate: candidate};

  async function flush() {
    timer = null;
    var batch = Array.from(waiting.keys());
    var hands = waiting;
    waiting = new Map();
    for (var i = 0; i < batch.length; i += MOST) {
      var part = batch.slice(i, i + MOST), found = null;
      if (!off && Date.now() >= pauseUntil) {
        var r = await A.request(API, null, {paths: part});
        if (r.ok) found = r.data.found || {};
        else if (r.data.error === "not_connected" || r.status === 403) off = true;    // nothing to ask this session
        else pauseUntil = Date.now() + RETRY_MS;                                         // GitHub away: later
      }
      part.forEach(function (p) {
        var v = found ? (found[p] || false) : false;
        if (found) known.set(p, v);
        (hands.get(p) || []).forEach(function (fn) { fn(v); });
      });
    }
  }

  function ask(path) {
    if (known.has(path)) return Promise.resolve(known.get(path));
    return new Promise(function (resolve) {
      if (!waiting.has(path)) waiting.set(path, []);
      waiting.get(path).push(resolve);
      if (!timer) timer = setTimeout(flush, 0);
    });
  }

  A.paths.resolve = async function (list) {
    var out = {};
    var answers = await Promise.all(list.map(ask));
    list.forEach(function (p, i) { out[p] = answers[i]; });
    return out;
  };

  function link(path, inner) {
    var a = A.make("a", "path-link");
    a.href = A.fileHref(SLUG, path);
    a.dataset.path = path;              // the file it names (messages.js shows the pictures under a message, 1y)
    a.title = A.t("files.open_hint", {path: path});
    a.appendChild(inner);
    return a;
  }

  function skip(node) {
    return !!(node.parentElement && node.parentElement.closest("a, pre, button, .katex, .path-link, textarea"));
  }

  // The candidates in an element: code elements whose whole text is a path, and the tokens of plain text.
  function collect(root) {
    var codes = [], texts = [], all = new Set();
    Array.prototype.forEach.call(root.querySelectorAll("code"), function (c) {
      if (c.closest("a, pre")) return;
      var p = candidate(c.textContent);
      if (p) { codes.push({el: c, path: p}); all.add(p); }
    });
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), n;
    while ((n = walker.nextNode())) {
      if (skip(n) || (n.parentElement && n.parentElement.closest("code"))) continue;
      var hits = [], m;
      TOKEN.lastIndex = 0;
      while ((m = TOKEN.exec(n.nodeValue))) {
        var raw = m[0], lead = raw.match(LEAD), core = raw.replace(LEAD, "").replace(TRAIL, "");
        var p = candidate(core);
        if (p && p === core) {
          var at = m.index + (lead ? lead[0].length : 0);
          hits.push({at: at, end: at + core.length, path: p});
          all.add(p);
        }
      }
      if (hits.length) texts.push({node: n, text: n.nodeValue, hits: hits});
    }
    return {codes: codes, texts: texts, paths: Array.from(all)};
  }

  A.paths.scan = async function (root) {
    if (!root || off) return;
    var c = collect(root);
    if (!c.paths.length) return;
    var kinds = await A.paths.resolve(c.paths);
    c.codes.forEach(function (x) {
      if (kinds[x.path] !== "file" || !x.el.isConnected || x.el.closest("a")) return;
      var parent = x.el.parentNode, next = x.el.nextSibling;
      parent.insertBefore(link(x.path, x.el), next);
    });
    c.texts.forEach(function (x) {
      var node = x.node;
      if (!node.parentNode || node.nodeValue !== x.text || skip(node)) return;
      var s = node.nodeValue, frag = document.createDocumentFragment(), from = 0, any = false;
      x.hits.forEach(function (h) {
        if (kinds[h.path] !== "file") return;
        any = true;
        frag.appendChild(document.createTextNode(s.slice(from, h.at)));
        frag.appendChild(link(h.path, document.createTextNode(s.slice(h.at, h.end))));
        from = h.end;
      });
      if (!any) return;
      frag.appendChild(document.createTextNode(s.slice(from)));
      node.parentNode.replaceChild(frag, node);
    });
  };
})();
