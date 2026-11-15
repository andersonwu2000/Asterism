// The project's own tokenizers for Lean 4 and TeX (Asterism.highlight), in the shape of a stream parser: the editor
// (editor.js) makes each a language of its own. They mark comments, strings, keywords (commands, for TeX), declared
// names, types and sorts (environments, for TeX), numbers and attributes, and nothing else; whatever they do not know
// stays plain. Code is the one place hue is allowed: the editor's highlight style gives each tag a --color-syn-* token.
//   A.highlight.language(path)  -> "lean" | "tex" | null
//   A.highlight.lean, A.highlight.tex -> {name, startState(), token(stream, state)}
//     token() reads one token of the line stream.string from stream.pos, moves stream.pos past it and answers its tag
//     ("comment", "keyword", "def", "typeName", "string", "number", "attributeName") or null for plain text. What runs
//     over lines (a nested Lean comment, a Lean string, a TeX definition waiting for its name) is kept in the state.
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

  var IDENT = /(?:«[^»\n]*»|[\p{L}_][\p{L}\p{N}_'!?₀-ₜ]*)(?:\.(?:«[^»\n]*»|[\p{L}_][\p{L}\p{N}_'!?₀-ₜ]*))*/uy;
  var NUMBER = /(?:0x[0-9a-fA-F_]+|0b[01_]+|\d[\d_]*(?:\.\d+)?(?:e[+-]?\d+)?)/y;
  var SPACE = /\s+/y;
  var CHAR = /'(?:\\.|[^\\'\n])'/y;

  function at(re, s, i) { re.lastIndex = i; var m = re.exec(s); return m ? m[0] : null; }
  function identChar(c) { return !!c && /[\p{L}\p{N}_'!?]/u.test(c); }
  function take(stream, text, tag) { stream.pos += text.length; return tag; }

  // ------------------------------------------------------------------ Lean

  // A block comment from stream.pos, nested; it may go on past the line (state.depth > 0).
  function leanComment(stream, st) {
    var s = stream.string, j = stream.pos, n = s.length;
    while (j < n) {
      if (s.substr(j, 2) === "/-") { st.depth++; j += 2; }
      else if (s.substr(j, 2) === "-/") { st.depth--; j += 2; if (!st.depth) break; }
      else j++;
    }
    stream.pos = j;
    return "comment";
  }
  // A string from stream.pos (after its opening quote, when it began on an earlier line); it may go on too.
  function leanString(stream, st, from) {
    var s = stream.string, k = from, n = s.length;
    while (k < n && s.charAt(k) !== '"') k += s.charAt(k) === "\\" ? 2 : 1;
    st.string = k >= n;
    stream.pos = Math.min(n, k + 1);
    return "string";
  }

  A.highlight.lean = {
    name: "lean",
    startState: function () { return {depth: 0, string: false, declaring: false}; },
    token: function (stream, st) {
      var s = stream.string, i = stream.pos, c = s.charAt(i), c2 = s.substr(i, 2), m;
      if (st.depth) return leanComment(stream, st);
      if (st.string) return leanString(stream, st, i);
      if (c2 === "/-") return leanComment(stream, st);
      if (c2 === "--") { stream.pos = s.length; return "comment"; }
      if (c === '"') return leanString(stream, st, i + 1);
      if (c === "'" && !identChar(s.charAt(i - 1)) && (m = at(CHAR, s, i))) return take(stream, m, "string");
      if (c2 === "@[") {
        var close = s.indexOf("]", i);
        stream.pos = close < 0 ? s.length : close + 1;
        return "attributeName";
      }
      if (/\d/.test(c) && !identChar(s.charAt(i - 1)) && (m = at(NUMBER, s, i))) return take(stream, m, "number");
      if ((m = at(IDENT, s, i))) {
        var tag = null;
        if (st.declaring) { tag = "def"; st.declaring = false; }
        else if (LEAN_KEYWORDS.has(m)) { tag = "keyword"; st.declaring = LEAN_DECLARES.has(m); }
        else if (LEAN_TYPES.has(m)) tag = "typeName";
        return take(stream, m, tag);
      }
      if ((m = at(SPACE, s, i))) return take(stream, m, null);
      if (c !== "(" && c !== "{" && c !== "[") st.declaring = false;
      // One character; a surrogate pair stays whole.
      return take(stream, String.fromCodePoint(s.codePointAt(i)), null);
    }
  };

  // ------------------------------------------------------------------ TeX

  var COMMAND = /\\(?:[A-Za-z@]+\*?|.)/y;
  var BRACED = /\{([^{}\n]*)\}/y;
  var PLAIN_TEX = /[^\\%${}#\d\s]+/y;

  A.highlight.tex = {
    name: "tex",
    // queue: the pieces of a command's argument still to give out ([tag, length]), always on the same line.
    startState: function () { return {define: false, queue: []}; },
    token: function (stream, st) {
      var s = stream.string, i = stream.pos, c = s.charAt(i), m;
      while (st.queue.length) {
        var piece = st.queue.shift();
        if (piece[1]) { stream.pos += piece[1]; return piece[0]; }
      }
      if (c === "%") { stream.pos = s.length; return "comment"; }
      if (c === "\\") {
        m = at(COMMAND, s, i);
        if (/^\\[()[\]]$/.test(m)) return take(stream, m, "attributeName");
        if (st.define && /^\\[A-Za-z@]/.test(m)) { st.define = false; return take(stream, m, "def"); }
        take(stream, m, "keyword");
        if (TEX_DEFINES.has(m)) { st.define = true; return "keyword"; }
        var arg = at(BRACED, s, stream.pos);
        var tag = !arg ? null : m === "\\begin" || m === "\\end" ? "typeName" : TEX_KEYS.has(m) ? "string" : null;
        if (tag) st.queue = [[null, 1], [tag, arg.length - 2], [null, 1]];
        return "keyword";
      }
      if (c === "$") return take(stream, s.substr(i, 2) === "$$" ? "$$" : "$", "attributeName");
      if (c === "#" && /\d/.test(s.charAt(i + 1))) return take(stream, s.substr(i, 2), "attributeName");
      if (/\d/.test(c) && (m = at(NUMBER, s, i))) return take(stream, m, "number");
      if ((m = at(SPACE, s, i))) return take(stream, m, null);
      if ((m = at(PLAIN_TEX, s, i))) return take(stream, m, null);
      if (c !== "{" && c !== "}") st.define = false;
      return take(stream, String.fromCodePoint(s.codePointAt(i)), null);
    }
  };
})();
