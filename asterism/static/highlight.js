// Two small tokenizers for the source view of files mode (Asterism.highlight): Lean 4 and TeX. They mark comments,
// strings, keywords (commands, for TeX), declared names, types and sorts (environments, for TeX), numbers and
// attributes, and nothing else; whatever they do not know stays plain. Code is the one place hue is allowed: each
// class maps to a --color-syn-* token (app.css). The text is never markup: tokens become text nodes and spans.
//   A.highlight.language(path)  -> "lean" | "tex" | null
//   A.highlight.code(text, language) -> a DocumentFragment of the whole text
"use strict";
(function () {
  var A = window.Asterism;
  if (!A) return;

  var LEAN_KEYWORDS = new Set(("theorem lemma def example abbrev axiom opaque structure class inductive instance where " +
    "extends deriving by fun λ let have show from at with match do if then else for in unless return mutual " +
    "namespace section end open import export variable universe noncomputable private protected partial unsafe " +
    "macro macro_rules syntax notation infix infixl infixr prefix postfix set_option attribute calc suffices " +
    "obtain rcases intro intros exact apply refine rw rewrite simp simp_all omega linarith nlinarith ring norm_num " +
    "constructor cases induction using sorry admit decide aesop field_simp positivity gcongr exists use specialize " +
    "termination_by decreasing_by local scoped").split(" "));
  var LEAN_DECLARES = new Set("theorem lemma def abbrev axiom opaque structure class inductive instance".split(" "));
  var LEAN_TYPES = new Set("Type Sort Prop Nat Int Rat Real Complex Bool String Char List Array Option Fin ℕ ℤ ℚ ℝ ℂ".split(" "));
  var TEX_DEFINES = new Set(["\\newcommand", "\\renewcommand", "\\providecommand", "\\def", "\\gdef", "\\edef",
                             "\\DeclareMathOperator", "\\newenvironment", "\\renewenvironment", "\\newtheorem"]);
  var TEX_KEYS = new Set(["\\label", "\\ref", "\\eqref", "\\cref", "\\Cref", "\\cite", "\\citep", "\\citet", "\\input",
                          "\\include", "\\usepackage", "\\documentclass", "\\bibliography", "\\includegraphics", "\\url"]);

  A.highlight = {};
  A.highlight.language = function (path) {
    var m = /\.([A-Za-z0-9]+)$/.exec(path || "");
    var ext = m ? m[1].toLowerCase() : "";
    if (ext === "lean") return "lean";
    if (["tex", "sty", "cls", "bbl", "ltx"].indexOf(ext) >= 0) return "tex";
    return null;
  };

  // ------------------------------------------------------------------ Lean

  var IDENT = /(?:«[^»\n]*»|[\p{L}_][\p{L}\p{N}_'!?₀-ₜ]*)(?:\.(?:«[^»\n]*»|[\p{L}_][\p{L}\p{N}_'!?₀-ₜ]*))*/uy;
  var NUMBER = /(?:0x[0-9a-fA-F_]+|0b[01_]+|\d[\d_]*(?:\.\d+)?(?:e[+-]?\d+)?)/y;
  var SPACE = /\s+/y;
  var CHAR = /'(?:\\.|[^\\'\n])'/y;

  function at(re, s, i) { re.lastIndex = i; var m = re.exec(s); return m ? m[0] : null; }
  function identChar(c) { return !!c && /[\p{L}\p{N}_'!?]/u.test(c); }

  function lean(s) {
    var out = [], i = 0, n = s.length, declaring = false;
    function push(cls, text) { out.push([cls, text]); i += text.length; }
    while (i < n) {
      var c = s.charAt(i), c2 = s.substr(i, 2), m;
      if (c2 === "/-") {                                   // block comment, nested
        var depth = 0, j = i;
        while (j < n) {
          if (s.substr(j, 2) === "/-") { depth++; j += 2; }
          else if (s.substr(j, 2) === "-/") { depth--; j += 2; if (!depth) break; }
          else j++;
        }
        push("comment", s.slice(i, j));
      } else if (c2 === "--") {
        var eol = s.indexOf("\n", i);
        push("comment", s.slice(i, eol < 0 ? n : eol));
      } else if (c === '"') {
        var k = i + 1;
        while (k < n && s.charAt(k) !== '"') k += s.charAt(k) === "\\" ? 2 : 1;
        push("string", s.slice(i, Math.min(n, k + 1)));
      } else if (c === "'" && !identChar(s.charAt(i - 1)) && (m = at(CHAR, s, i))) {
        push("string", m);
      } else if (c2 === "@[") {
        var close = s.indexOf("]", i), nl = s.indexOf("\n", i);
        var end = close < 0 || (nl >= 0 && nl < close) ? (nl < 0 ? n : nl) : close + 1;
        push("attr", s.slice(i, end));
      } else if (/\d/.test(c) && !identChar(s.charAt(i - 1)) && (m = at(NUMBER, s, i))) {
        push("number", m);
      } else if ((m = at(IDENT, s, i))) {
        var cls = null;
        if (declaring) { cls = "name"; declaring = false; }
        else if (LEAN_KEYWORDS.has(m)) { cls = "keyword"; declaring = LEAN_DECLARES.has(m); }
        else if (LEAN_TYPES.has(m)) cls = "type";
        push(cls, m);
      } else if ((m = at(SPACE, s, i))) {
        push(null, m);
      } else {
        push(null, c);
        if (c !== "(" && c !== "{" && c !== "[") declaring = false;
      }
    }
    return out;
  }

  // ------------------------------------------------------------------ TeX

  var COMMAND = /\\(?:[A-Za-z@]+\*?|.)/y;
  var BRACED = /\{([^{}\n]*)\}/y;
  var PLAIN_TEX = /[^\\%${}#\d\s]+/y;

  function tex(s) {
    var out = [], i = 0, n = s.length, define = false, m;
    function push(cls, text) { out.push([cls, text]); i += text.length; }
    while (i < n) {
      var c = s.charAt(i);
      if (c === "%") {
        var eol = s.indexOf("\n", i);
        push("comment", s.slice(i, eol < 0 ? n : eol));
      } else if (c === "\\") {
        m = at(COMMAND, s, i);
        if (/^\\[()[\]]$/.test(m)) { push("attr", m); continue; }
        if (define && /^\\[A-Za-z@]/.test(m)) { push("name", m); define = false; continue; }
        push("keyword", m);
        if (TEX_DEFINES.has(m)) { define = true; continue; }
        var arg = at(BRACED, s, i);
        if (arg && (m === "\\begin" || m === "\\end")) {
          push(null, "{"); push("type", arg.slice(1, -1)); push(null, "}");
        } else if (arg && TEX_KEYS.has(m)) {
          push(null, "{"); push("string", arg.slice(1, -1)); push(null, "}");
        }
      } else if (c === "$") {
        push("attr", s.substr(i, 2) === "$$" ? "$$" : "$");
      } else if (c === "#" && /\d/.test(s.charAt(i + 1))) {
        push("attr", s.substr(i, 2));
      } else if (/\d/.test(c) && (m = at(NUMBER, s, i))) {
        push("number", m);
      } else if ((m = at(SPACE, s, i))) {
        push(null, m);
      } else if ((m = at(PLAIN_TEX, s, i))) {
        push(null, m);
      } else {
        push(null, c);
        if (c !== "{" && c !== "}") define = false;
      }
    }
    return out;
  }

  // ------------------------------------------------------------------ drawing

  A.highlight.tokens = function (text, language) {
    if (language === "lean") return lean(text);
    if (language === "tex") return tex(text);
    return [[null, text]];
  };

  A.highlight.code = function (text, language) {
    var frag = document.createDocumentFragment(), plain = "";
    A.highlight.tokens(text, language).forEach(function (t) {
      if (!t[0]) { plain += t[1]; return; }
      if (plain) { frag.appendChild(document.createTextNode(plain)); plain = ""; }
      var span = document.createElement("span");
      span.className = "syn-" + t[0];
      span.textContent = t[1];
      frag.appendChild(span);
    });
    if (plain) frag.appendChild(document.createTextNode(plain));
    return frag;
  };
})();
