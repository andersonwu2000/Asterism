// What files mode needs of CodeMirror 6, as the one global `CodeMirror` (asterism/static/editor.js uses it).
// Only what is named here ends up in the bundle.
export { EditorState, EditorSelection, Compartment, Transaction } from "@codemirror/state";
export {
  EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter, highlightSpecialChars,
  drawSelection, dropCursor
} from "@codemirror/view";
export { history, historyKeymap, defaultKeymap } from "@codemirror/commands";
export { search, searchKeymap, highlightSelectionMatches } from "@codemirror/search";
export { StreamLanguage, HighlightStyle, syntaxHighlighting, bracketMatching, indentOnInput } from "@codemirror/language";
export { tags } from "@lezer/highlight";
export { markdownLanguage, markdownKeymap } from "@codemirror/lang-markdown";
