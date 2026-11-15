// Rendering text safely: a message's text (Asterism.renderText) and a Markdown file of the repository or of a local
// folder (Asterism.renderDoc).
//
// Both are hostile input. They are rendered as Markdown with these rules: raw HTML is shown as text, and the HTML
// that Markdown produces goes through DOMPurify with a strict allow-list (no scripts, no event attributes, no
// iframes/objects/forms, only http(s) and mailto links, which open with rel="noopener noreferrer"). Mathematics
// ($...$, $$...$$) is taken out before Markdown sees it and drawn by KaTeX (trust off) into elements this script
// creates.
// - In a message, images become plain links and nothing is loaded.
// - In a file, links and images may also be relative: while DOMPurify still holds the document in its own inert
//   copy, `opts.link(href)` turns a relative link into {href, path} (a file of the repository: no new tab, data-path
//   marks it) or null (the link is dropped, its text stays), and `opts.image(src)` gives the address to load a
//   relative picture from (the raw endpoint) or null (the picture becomes its alternative text). Nothing that is not
//   rewritten so is ever loaded. For a file of a local folder, `opts.image(src)` answers {local: path} instead: the
//   picture is left without an address and marked data-local for the caller, and `opts.link` gives "#" addresses.
"use strict";
(function () {
  var A = window.Asterism;
  if (!A || !window.marked || !window.DOMPurify || !window.katex) return;

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }
  function rawHtml(html, block) {                  // raw HTML is shown, never interpreted
    var text = escapeHtml(typeof html === "string" ? html : (html && (html.raw || html.text)) || "");
    // A block of it is a paragraph of its own, not loose text between the document's blocks.
    return (html && typeof html === "object" ? html.block : block) ? "<p>" + text + "</p>" : text;
  }
  var md = new window.marked.Marked();
  md.use({
    gfm: true, breaks: true,
    renderer: {
      html: rawHtml,
      image: function (href, title, text) {      // never load an image: show it as a link
        if (href && typeof href === "object") { text = href.text; href = href.href; }
        return '<a href="' + escapeHtml(href || "") + '">' + escapeHtml(text || href || "") + "</a>";
      }
    }
  });
  var doc = new window.marked.Marked();
  doc.use({
    gfm: true, breaks: false,
    renderer: {
      html: rawHtml,
      image: function (href, title, text) {
        if (href && typeof href === "object") { text = href.text; href = href.href; }
        return '<img src="' + escapeHtml(href || "") + '" alt="' + escapeHtml(text || "") + '">';
      }
    }
  });
  var TAGS = ["p", "br", "hr", "em", "strong", "del", "s", "code", "pre", "blockquote", "ul", "ol", "li",
              "h1", "h2", "h3", "h4", "h5", "h6", "a", "table", "thead", "tbody", "tr", "th", "td"];
  var PURIFY = {
    ALLOWED_TAGS: TAGS,
    ALLOWED_ATTR: ["href", "title", "start", "align"],
    ALLOWED_URI_REGEXP: /^(?:https?:|mailto:)/i,
    ALLOW_DATA_ATTR: false,
    RETURN_DOM_FRAGMENT: true
  };
  var PURIFY_DOC = {
    ALLOWED_TAGS: TAGS.concat(["img"]),
    ALLOWED_ATTR: ["href", "title", "start", "align", "src", "alt"],
    // http(s), mailto, or no scheme at all (relative); the hook below decides what a relative one becomes.
    ALLOWED_URI_REGEXP: /^(?:https?:|mailto:|(?![a-z][a-z0-9+.\-]*:))/i,
    ALLOW_DATA_ATTR: false,
    RETURN_DOM_FRAGMENT: true
  };
  function external(v) { return /^(?:https?:|mailto:)/i.test(v); }

  var rewrite = null;                            // the file's rules while a file is rendered, else null
  window.DOMPurify.addHook("afterSanitizeAttributes", function (node) {
    if (node.tagName === "A" && node.hasAttribute("href")) {
      var href = node.getAttribute("href");
      if (rewrite && !external(href)) {
        var to = href.charAt(0) === "#" ? {href: href} : rewrite.link(href);
        if (!to) { node.removeAttribute("href"); return; }
        node.setAttribute("href", to.href);
        if (to.path) node.setAttribute("data-path", to.path);
        return;
      }
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer");
    }
    if (node.tagName === "IMG") {
      var src = node.getAttribute("src") || "", at = rewrite && !external(src) ? rewrite.image(src) : null;
      if (at && typeof at === "object") {
        // A picture of a local folder: the caller loads it itself (data-local names it) and nothing is loaded here.
        node.removeAttribute("src");
        node.setAttribute("data-local", at.local);
      } else if (at) {
        node.setAttribute("src", at);
        node.setAttribute("loading", "lazy");
      } else {
        // Never loaded: a picture elsewhere becomes a link to it, anything else its alternative text.
        var alt = node.getAttribute("alt") || src;
        var stand = node.ownerDocument.createElement(/^https?:/i.test(src) ? "a" : "span");
        stand.textContent = alt;
        if (stand.tagName === "A") {
          stand.setAttribute("href", src);
          stand.setAttribute("target", "_blank");
          stand.setAttribute("rel", "noopener noreferrer");
        }
        node.replaceWith(stand);
      }
    }
  });
  // Code first, so that a $ inside code stays code; then display and inline mathematics.
  var MATH_RE = /(```[\s\S]*?```|`[^`\n]*`)|\$\$([\s\S]+?)\$\$|\$(?![\s$])([^$\n]*?[^\s$\\])\$/g;
  var MARK_OPEN = "", MARK_CLOSE = "";     // private-use characters: never in a message's own text

  function render(text, parser, config, cls) {
    var maths = [];
    var src = String(text).replace(MATH_RE, function (all, code, display, inline) {
      if (code) return all;
      maths.push({tex: display !== undefined ? display : inline, display: display !== undefined});
      return MARK_OPEN + (maths.length - 1) + MARK_CLOSE;
    });
    var box = document.createElement("div");
    box.className = cls;
    box.appendChild(window.DOMPurify.sanitize(parser.parse(src, {async: false}), config));
    if (maths.length) drawMaths(box, maths);
    markPictures(box);
    return box;
  }

  A.renderText = function (text) { return render(text, md, PURIFY, "text"); };

  A.renderDoc = function (text, opts) {
    rewrite = opts;
    try { return render(text, doc, PURIFY_DOC, "text doc"); } finally { rewrite = null; }
  };

  // A paragraph that is one picture and nothing else may leave the reading column (app.css: p.picture); a picture
  // inside a sentence stays with its text.
  function markPictures(box) {
    Array.prototype.forEach.call(box.querySelectorAll(":scope > p"), function (p) {
      var img = p.children.length === 1 && p.firstElementChild.tagName === "IMG";
      if (img && !p.textContent.trim()) p.classList.add("picture");
    });
  }

  function drawMaths(box, maths) {
    var walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT), nodes = [], n;
    while ((n = walker.nextNode())) if (n.nodeValue.indexOf(MARK_OPEN) >= 0) nodes.push(n);
    var mark = new RegExp(MARK_OPEN + "(\\d+)" + MARK_CLOSE, "g");
    nodes.forEach(function (node) {
      var frag = document.createDocumentFragment(), at = 0, m, s = node.nodeValue;
      mark.lastIndex = 0;
      while ((m = mark.exec(s))) {
        frag.appendChild(document.createTextNode(s.slice(at, m.index)));
        var item = maths[Number(m[1])], span = document.createElement("span");
        try {
          window.katex.render(item.tex, span, {displayMode: item.display, throwOnError: false, trust: false,
                                                strict: "ignore", maxSize: 50, maxExpand: 1000});
        } catch (err) {
          span.textContent = item.display ? "$$" + item.tex + "$$" : "$" + item.tex + "$";
        }
        frag.appendChild(span);
        at = m.index + m[0].length;
      }
      frag.appendChild(document.createTextNode(s.slice(at)));
      node.parentNode.replaceChild(frag, node);
    });
  }
})();
