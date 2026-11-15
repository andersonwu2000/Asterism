// Rendering a message's text safely (Asterism.renderText), for the messages page.
//
// Message text is hostile input. It is rendered as Markdown with these rules: raw HTML in a message is shown
// as text, Markdown images become plain links, and the HTML that Markdown produces goes through DOMPurify
// with a strict allow-list (no scripts, no event attributes, no iframes/objects/forms/images, only http(s)
// and mailto links, which open with rel="noopener noreferrer"). Mathematics ($...$, $$...$$) is taken out
// before Markdown sees it and drawn by KaTeX (trust off) into elements this script creates.
"use strict";
(function () {
  var A = window.Asterism;
  if (!A || !window.marked || !window.DOMPurify || !window.katex) return;

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }
  var md = new window.marked.Marked();
  md.use({
    gfm: true, breaks: true,
    renderer: {
      html: function (html) {                    // raw HTML in a message is shown, never interpreted
        return escapeHtml(typeof html === "string" ? html : (html && (html.raw || html.text)) || "");
      },
      image: function (href, title, text) {      // never load an image: show it as a link
        if (href && typeof href === "object") { text = href.text; href = href.href; }
        return '<a href="' + escapeHtml(href || "") + '">' + escapeHtml(text || href || "") + "</a>";
      }
    }
  });
  var PURIFY = {
    ALLOWED_TAGS: ["p", "br", "hr", "em", "strong", "del", "s", "code", "pre", "blockquote", "ul", "ol", "li",
                   "h1", "h2", "h3", "h4", "h5", "h6", "a", "table", "thead", "tbody", "tr", "th", "td"],
    ALLOWED_ATTR: ["href", "title", "start", "align"],
    ALLOWED_URI_REGEXP: /^(?:https?:|mailto:)/i,
    ALLOW_DATA_ATTR: false,
    RETURN_DOM_FRAGMENT: true
  };
  window.DOMPurify.addHook("afterSanitizeAttributes", function (node) {
    if (node.tagName === "A" && node.hasAttribute("href")) {
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer");
    }
  });
  // Code first, so that a $ inside code stays code; then display and inline mathematics.
  var MATH_RE = /(```[\s\S]*?```|`[^`\n]*`)|\$\$([\s\S]+?)\$\$|\$(?![\s$])([^$\n]*?[^\s$\\])\$/g;
  var MARK_OPEN = "", MARK_CLOSE = "";     // private-use characters: never in a message's own text

  A.renderText = function (text) {
    var maths = [];
    var src = String(text).replace(MATH_RE, function (all, code, display, inline) {
      if (code) return all;
      maths.push({tex: display !== undefined ? display : inline, display: display !== undefined});
      return MARK_OPEN + (maths.length - 1) + MARK_CLOSE;
    });
    var box = document.createElement("div");
    box.className = "text";
    box.appendChild(window.DOMPurify.sanitize(md.parse(src, {async: false}), PURIFY));
    if (maths.length) drawMaths(box, maths);
    return box;
  };

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
