// Files mode, the one source view (Asterism.editor): CodeMirror 6, served from this server
// (static/vendor/codemirror/codemirror.min.js, the global CodeMirror). Read only for a file of the repository,
// editable for a local one. Line numbers, search and replace (Ctrl+F; its words from the catalogue), undo history,
// bracket matching; the prose kinds (.md, .tex, .txt) wrap, code does not. Markdown is highlighted by CodeMirror's
// own parser, Lean and TeX by this project's tokenizers (highlight.js) as stream languages.
// Its colours are the page's tokens (var(--color-…), the --color-syn-* ones for code), so it follows the theme switch
// at once; nothing here names a colour. Tab is left to move the focus out of the editor.
//   var ed = A.editor.create({path, text, readOnly, label, onChange: fn(ed, remote), onSave: fn(ed)})
//   ed.dom, ed.view, ed.text(), ed.setText(text) (only what differs is replaced, outside the undo history, so the
//   cursor and the scroll stay where they can), ed.at(), ed.markSaved(at), ed.dirty(), ed.setReadOnly(bool), ed.focus(),
//   ed.snapshot() / ed.restore(snap) (the scroll position), ed.destroy()
"use strict";
(function () {
  var A = window.Asterism, CM = window.CodeMirror;
  if (!A || !CM) return;
  var WRAPS = /\.(?:md|markdown|tex|txt)$/i, MARKDOWN = /\.(?:md|markdown)$/i;

  var tags = CM.tags;
  var style = CM.HighlightStyle.define([
    {tag: tags.comment, color: "var(--color-ink-dim)", fontStyle: "italic"},
    {tag: tags.keyword, color: "var(--color-syn-keyword)"},
    {tag: tags.definition(tags.variableName), color: "var(--color-syn-name)"},
    {tag: tags.typeName, color: "var(--color-syn-type)"},
    {tag: tags.string, color: "var(--color-syn-string)"},
    {tag: tags.number, color: "var(--color-syn-number)"},
    {tag: tags.attributeName, color: "var(--color-syn-attr)"},
    // Markdown: structure by weight and shape; links and code take the code tokens.
    {tag: tags.heading, fontWeight: "600", color: "var(--color-ink)"},
    {tag: tags.strong, fontWeight: "600"},
    {tag: tags.emphasis, fontStyle: "italic"},
    {tag: [tags.link, tags.url], color: "var(--color-syn-string)"},
    {tag: tags.monospace, color: "var(--color-syn-type)"},
    {tag: [tags.processingInstruction, tags.contentSeparator, tags.quote], color: "var(--color-ink-dim)"}
  ]);

  var theme = CM.EditorView.theme({
    "&": {height: "100%", color: "var(--color-ink)", backgroundColor: "var(--color-surface-2)", fontSize: "13px"},
    "&.cm-focused": {outline: "1px solid var(--color-edge-strong)", outlineOffset: "-1px"},
    ".cm-scroller": {fontFamily: "var(--font-mono)", lineHeight: "1.6", overscrollBehavior: "contain"},
    ".cm-content": {caretColor: "var(--color-ink)", padding: "16px 0 48px"},
    ".cm-line": {padding: "0 24px 0 16px"},
    ".cm-cursor, .cm-dropCursor": {borderLeftColor: "var(--color-ink)"},
    ".cm-selectionBackground": {background: "var(--color-wash-3)"},
    "&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground": {background: "var(--color-wash-3)"},
    ".cm-activeLine": {backgroundColor: "var(--color-wash)"},
    ".cm-activeLineGutter": {backgroundColor: "var(--color-wash-2)", color: "var(--color-ink)"},
    ".cm-gutters": {backgroundColor: "var(--color-surface-2)", color: "var(--color-ink-dim)", border: "0",
                    borderRight: "1px solid var(--color-edge)"},
    ".cm-lineNumbers .cm-gutterElement": {padding: "0 14px 0 12px", minWidth: "3.5em"},
    ".cm-specialChar": {color: "var(--color-ink-dim)"},
    "&.cm-focused .cm-matchingBracket": {backgroundColor: "var(--color-wash-3)", outline: "1px solid var(--color-edge-strong)"},
    "&.cm-focused .cm-nonmatchingBracket": {backgroundColor: "transparent", textDecoration: "underline wavy var(--color-ink-dim)"},
    ".cm-searchMatch": {backgroundColor: "var(--color-wash-3)", outline: "1px solid var(--color-edge-strong)"},
    ".cm-searchMatch.cm-searchMatch-selected": {backgroundColor: "var(--color-wash-3)", outline: "2px solid var(--color-ink)"},
    ".cm-selectionMatch": {backgroundColor: "var(--color-wash-2)"},
    ".cm-panels": {backgroundColor: "var(--color-surface)", color: "var(--color-ink)"},
    ".cm-panels-top": {borderBottom: "1px solid var(--color-edge)"},
    ".cm-panels-bottom": {borderTop: "1px solid var(--color-edge)"},
    ".cm-panel.cm-search": {padding: "8px 36px 8px 12px", font: "400 13px/1.5 var(--font-ui)"},
    ".cm-panel.cm-search label": {fontSize: "13px", color: "var(--color-ink-dim)", marginRight: "8px"},
    ".cm-panel.cm-search input[type=checkbox]": {accentColor: "var(--color-ink)"},
    ".cm-panel.cm-search [name=close]": {color: "var(--color-ink-dim)", fontSize: "18px", top: "6px", right: "8px",
                                          width: "24px", height: "24px", borderRadius: "var(--r-micro)"},
    ".cm-textfield": {backgroundColor: "var(--color-surface-2)", color: "var(--color-ink)", fontSize: "13px",
                      border: "1px solid var(--color-edge-strong)", borderRadius: "var(--r-control)", padding: "3px 8px",
                      margin: "2px 4px 2px 0"},
    ".cm-button": {backgroundImage: "none", backgroundColor: "var(--color-surface-2)", color: "var(--color-ink)",
                   fontSize: "13px", border: "1px solid var(--color-edge-strong)", borderRadius: "var(--r-control)",
                   padding: "3px 10px", margin: "2px 4px 2px 0"},
    ".cm-button:active": {backgroundImage: "none", backgroundColor: "var(--color-wash-3)"},
    ".cm-tooltip": {backgroundColor: "var(--color-surface-3)", color: "var(--color-ink)", border: "1px solid var(--color-edge)"}
  });

  // The words of the search panel, from the catalogue.
  var PHRASES = {"Find": "editor.find", "Replace": "editor.replace", "next": "editor.next", "previous": "editor.previous",
                 "all": "editor.all", "match case": "editor.match_case", "by word": "editor.by_word",
                 "regexp": "editor.regexp", "replace": "editor.replace_one", "replace all": "editor.replace_all",
                 "close": "editor.close", "current match": "editor.current_match", "on line": "editor.on_line",
                 "replaced match on line $": "editor.replaced_on_line", "replaced $ matches": "editor.replaced_count",
                 "Go to line": "editor.go_to_line", "go": "editor.go", "Control character": "editor.control_char"};
  var phrases = {};
  Object.keys(PHRASES).forEach(function (k) { if (A.MSG[PHRASES[k]]) phrases[k] = A.MSG[PHRASES[k]]; });

  var streams = {};
  function language(path) {
    if (MARKDOWN.test(path)) return [CM.markdownLanguage, CM.keymap.of(CM.markdownKeymap)];
    var lang = A.highlight && A.highlight.language(path);
    if (!lang) return [];
    if (!streams[lang]) streams[lang] = CM.StreamLanguage.define(A.highlight[lang]);
    return streams[lang];
  }

  var remote = CM.Transaction.remote, addToHistory = CM.Transaction.addToHistory;

  A.editor = {};
  A.editor.wraps = function (path) { return WRAPS.test(path || ""); };

  A.editor.create = function (opts) {
    var readOnly = new CM.Compartment(), dom = A.make("div", "editor");
    var ed = {dom: dom};
    var state = CM.EditorState.create({
      doc: opts.text || "",
      extensions: [
        language(opts.path),
        CM.keymap.of([{key: "Mod-s", preventDefault: true, run: function () {
          if (!opts.onSave) return false;
          opts.onSave(ed);
          return true;
        }}]),
        CM.lineNumbers(), CM.highlightActiveLineGutter(), CM.highlightSpecialChars(), CM.history(), CM.drawSelection(),
        CM.dropCursor(), CM.indentOnInput(), CM.bracketMatching(), CM.highlightActiveLine(),
        CM.highlightSelectionMatches(), CM.search({top: true}), CM.syntaxHighlighting(style),
        CM.keymap.of([].concat(CM.searchKeymap, CM.historyKeymap, CM.defaultKeymap)),
        A.editor.wraps(opts.path) ? CM.EditorView.lineWrapping : [],
        readOnly.of(CM.EditorState.readOnly.of(!!opts.readOnly)),
        CM.EditorState.phrases.of(phrases),
        CM.EditorView.contentAttributes.of({"aria-label": opts.label || opts.path || ""}),
        theme,
        CM.EditorView.updateListener.of(function (u) {
          if (!u.docChanged || !opts.onChange) return;
          opts.onChange(ed, u.transactions.some(function (tr) { return tr.annotation(remote); }));
        })
      ]
    });
    var view = new CM.EditorView({state: state, parent: dom});
    var saved = view.state.doc;
    ed.view = view;
    ed.text = function () { return view.state.doc.toString(); };
    ed.setText = function (text) {
      var cur = view.state.doc.toString();
      if (cur === text) return;
      var n = Math.min(cur.length, text.length), a = 0, b = 0;
      while (a < n && cur.charCodeAt(a) === text.charCodeAt(a)) a++;
      while (b < n - a && cur.charCodeAt(cur.length - 1 - b) === text.charCodeAt(text.length - 1 - b)) b++;
      view.dispatch({changes: {from: a, to: cur.length - b, insert: text.slice(a, text.length - b)},
                     annotations: [remote.of(true), addToHistory.of(false)]});
    };
    // `at`: the text as it was when it was written (ed.at()); typing meanwhile stays unsaved.
    ed.at = function () { return view.state.doc; };
    ed.markSaved = function (at) { saved = at || view.state.doc; };
    ed.dirty = function () { return !view.state.doc.eq(saved); };
    ed.setReadOnly = function (on) { view.dispatch({effects: readOnly.reconfigure(CM.EditorState.readOnly.of(!!on))}); };
    ed.focus = function () { view.focus(); };
    ed.snapshot = function () { return view.scrollSnapshot(); };
    ed.restore = function (snap) {
      view.requestMeasure();
      if (snap) view.dispatch({effects: snap});
    };
    ed.destroy = function () { view.destroy(); };
    return ed;
  };
})();
