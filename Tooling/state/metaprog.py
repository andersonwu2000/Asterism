"""Metaprogramming guard — ONE scanner for every path that hands
agent-written Lean text to an elaborator.

Threat model
------------
Lean 4 elaboration runs arbitrary user code. A `.lean` file an agent
writes can carry `elab` / `macro_rules` / `#eval` / `initialize`, and
that code executes **with the framework's own privileges** inside the
gateway's Lean workers (or `lake`), before any commit gate looks at the
file:

  * elab-time IO — arbitrary file/network/process access from inside the
    proving loop. This is a sandbox escape: the code does not go through
    `spawn_guard`, is not confined to the agent's `--add-dir`, and is not
    a `Bash` tool call anybody can see.
  * `Environment.add` (as opposed to `addDecl`) — inserts a declaration
    into the environment WITHOUT kernel type-checking, so a `theorem`
    that the kernel would reject becomes citable. `#print axioms` does
    not reveal it (no new axiom is named), so the axiom gate is blind.

`addDecl` itself is NOT a threat (it goes through the kernel), and
`native_decide` / a new `axiom` are already covered by the axiom gate's
whitelist + `sorryAx` tripwire (`pipeline/_axiom.py`,
`docs/architecture.md` §10).

Why a syntax blacklist, and what it is NOT
------------------------------------------
API names are NOT blocked: `Environment.add` can be aliased
(`let f := Environment.add`) or reached through any forwarding function,
and `import Lean` is pointless to block (Mathlib pulls the whole `Lean`
namespace in transitively). What CANNOT be hidden is the *entry* — the
parser keywords and attributes that make Lean run user code at
elaboration time must appear literally in the source. Those are what
this module scans for.

This layer is DEFENCE IN DEPTH, not the soundness guarantee. It stops
the known entries and gives the agent an immediate teaching message; it
cannot stop an unknown entry or a pre-poisoned `.olean`. The end-game
guarantee is an external kernel replay (`lean4checker`-style) over the
final environment — proposed in `docs/internal/framework_backlog.md`.

Where it is called (the enumeration is pinned by
`tests/test_metaprog_guard.py`; anything that elaborates agent text and
is not on this list is a hole):

  * `lsp/client.py` `did_open` / `did_change_full` — the LSP boundary.
    EVERY elaboration the gateway performs passes here, so this is the
    backstop no new gateway path can route around (raises).
  * `lsp/gateway.py` `apply_edit`, `goal_at`, `errors_at`,
    `validate_file`, `_verify_sync`, `_verify_session_sync` — the
    agent-facing entries, which answer with the rule instead of a stack
    trace. `goal_at`/`errors_at` matter because the `Write`/`Edit` tools
    reach disk without any `apply_edit`.
  * `pipeline/backward.py`, `pipeline/forward.py` — the commit gates
    (`forbidden_metaprogramming`), because a file can reach disk with no
    LSP tool call at all.
  * `quality/lake_probe.py` `run_lean_source`, `quality/dedupe.py`
    batch probes — the paths that shell out to `lake env lean` on a
    throwaway file, bypassing the gateway entirely.

Related fence, same disease: `knowledge/lemma_lookup.py` splices
requested names into an elaborated `.lean`, so it restricts them to the
Lean identifier charset (a name is not a place to smuggle a command).

Deliberately NOT blocked
------------------------
`deriving`      only dispatches to ALREADY-REGISTERED handlers; adding
                one needs `initialize` (blocked), so `deriving Repr` /
                `deriving DecidableEq` stay available.
`notation` /    declarative parser sugar with no user code attached;
`infixl` …      cannot execute anything on its own.
`set_option`    only `debug.skipKernelTC` is blocked (see below) —
                `maxHeartbeats` / linter options are everyday usage.
`import Lean`   useless to block (transitively present via Mathlib).

`debug.skipKernelTC` is not metaprogramming but belongs to the same
class: `Lean/AddDecl.lean` (v4.30.0-rc2, lines 22/29) skips kernel
type-checking when it is set, and no axiom appears in `#print axioms`
to show for it. One `set_option` would silently retire the kernel, so
it rides this gate.

Lexical discipline
------------------
Scanning runs on comment-stripped text (`strip_lean_comments`): agents
DO write `-- … (~64s elab)` in real committed proofs
(`Problems/Minif2f/mathd_numbertheory_202/proofs/L_pow_99_mod_10.lean:6`),
and a prose comment must not be a block.

The stripper follows Lean's own lexical precedence — whichever of
`--`, `/-`, `"`, `'` starts first wins — precisely so a string
containing `"/-"` cannot open a comment the scanner honours but Lean
does not (that asymmetry would BE the bypass). String and char literal
CONTENT is deliberately left in the scanned text: a literal cannot
execute, so keeping it only risks a loud false positive, never a silent
miss. Comment text is replaced by spaces/newlines, so offsets and line
numbers survive.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------
# Token sets
# ---------------------------------------------------------------------

#: Elaboration-time EXECUTION entries. These have no English-prose or
#: Lean-identifier collisions, so they are matched anywhere in code
#: (word-boundary, comment-stripped). Verified zero hits across the
#: 9k-file `Problems/` + `Library/` corpus.
EXECUTION_TOKENS: "tuple[str, ...]" = (
    "elab",
    "elab_rules",
    "macro",
    "macro_rules",
    "by_elab",
    "run_cmd",
    "run_elab",
    "run_tac",
    "initialize",
    "builtin_initialize",
    "declare_syntax_cat",
    # native-compilation accomplices of `native_decide` (the axiom itself
    # is caught by the whitelist; these swap the implementation out from
    # under a decidable instance)
    "unsafe",
    "implemented_by",
    "extern",
)

#: Parser-surface commands with an English-word collision ("… isometry
#: syntax:" appears in a Library doc comment). `syntax` alone executes
#: NOTHING — it needs a `macro_rules` / `elab_rules` companion, all of
#: which are in EXECUTION_TOKENS — so anchoring it to command position
#: is defence in depth at zero false-positive cost.
ANCHORED_TOKENS: "tuple[str, ...]" = (
    "syntax",
)

#: Attribute names that REGISTER a piece of user code with the
#: elaborator / compiler. Matched only inside an `@[…]` block, so
#: Mathlib-style rule attributes (`@[aesop unsafe 50%]`) do not trip the
#: declaration-modifier tokens above.
ATTRIBUTE_TOKENS: "tuple[str, ...]" = (
    "command_elab",
    "term_elab",
    "macro",
    "delab",
    "app_unexpander",
    "unexpander",
    "implemented_by",
    "extern",
    # `@[init f]` runs `f` at import time — `initialize` in attribute form
    "init",
)

#: `@[tactic …]` registers a tactic elaborator, but `tactic` is also an
#: Aesop rule-builder keyword (`@[aesop safe tactic]`). Only the
#: elaborator-registration form — `tactic` as the attribute HEAD — is
#: blocked.
_ATTR_HEAD_TOKENS: "tuple[str, ...]" = (
    "tactic",
)

#: `set_option`s that retire a soundness layer.
FORBIDDEN_OPTIONS: "tuple[str, ...]" = (
    "debug.skipKernelTC",
)

#: What the agent is told when the gate fires. Line 1 is the digest the
#: Context.md summary shows (`agent/context.py::_digest_failure` keeps
#: only the first line), so it must stand alone.
METAPROG_HINT = (
    "This framework forbids elaboration-time metaprogramming in Lean "
    "sources: such code runs with the framework's own privileges before "
    "any gate sees the file, and can insert declarations the kernel never "
    "checked. Write plain `theorem` / `def` declarations — soundness is "
    "carried by the Lean kernel and the axiom gate, not by custom "
    "elaborators. A proof that seems to need a new tactic should be "
    "decomposed into lemmas instead."
)


def blocked_detail(token: str, *, where: str = "") -> str:
    """The `failure_detail` / error text for a blocked token. First line
    is self-contained (it is what the one-line failure digest keeps)."""
    loc = f" in {where}" if where else ""
    return (f"forbidden metaprogramming entry `{token}`{loc} — "
            f"elaboration-time code execution is not permitted.\n"
            f"{METAPROG_HINT}")


# ---------------------------------------------------------------------
# Lean-ish lexer: comment stripping
# ---------------------------------------------------------------------

_CHAR_LIT_RE = re.compile(
    r"'(?:\\(?:x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|.)|[^\\'])'")


def _is_ident_char(c: str) -> bool:
    """Lean identifier continuation character (`!`/`?`/`'` are legal in
    declaration names: `simp!`, `decide?`, `h'`)."""
    return c.isalnum() or c in "_'!?"


def strip_lean_comments(text: str) -> str:
    """Blank out `--` line comments and nested `/- … -/` block comments,
    preserving every other byte AND the total length (comment bytes
    become spaces / newlines) so offsets stay meaningful.

    String and char literals are recognised so their content cannot open
    a comment — Lean would not treat `"/-"` as a comment start, and if
    this scanner did, everything after it would silently escape the gate.
    Their content is otherwise kept (a literal cannot execute; keeping it
    can only cause a loud false positive).
    """
    out: "list[str]" = []
    i, n = 0, len(text)
    depth = 0
    while i < n:
        if depth:
            if text.startswith("/-", i):
                depth += 1
                out.append("  ")
                i += 2
                continue
            if text.startswith("-/", i):
                depth -= 1
                out.append("  ")
                i += 2
                continue
            out.append("\n" if text[i] == "\n" else " ")
            i += 1
            continue
        if text.startswith("--", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
            continue
        if text.startswith("/-", i):
            depth = 1
            out.append("  ")
            i += 2
            continue
        c = text[i]
        if c == '"':
            # `r"…"` has no escapes; a stray backslash there must not
            # swallow the closing quote.
            raw = (i >= 1 and text[i - 1] == "r"
                   and (i < 2 or not _is_ident_char(text[i - 2])))
            j = i + 1
            while j < n:
                if text[j] == "\\" and not raw:
                    j += 2
                    continue
                if text[j] == '"':
                    j += 1
                    break
                j += 1
            out.append(text[i:min(j, n)])
            i = min(j, n)
            continue
        if c == "'" and (i == 0 or not _is_ident_char(text[i - 1])):
            m = _CHAR_LIT_RE.match(text, i)
            if m:
                out.append(m.group(0))
                i = m.end()
                continue
        out.append(c)
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------

_BEFORE = r"(?<![A-Za-z0-9_.'!?])"
_AFTER = r"(?![A-Za-z0-9_'!?])"

_EXEC_RE = re.compile(
    _BEFORE + "(" + "|".join(sorted(EXECUTION_TOKENS, key=len, reverse=True))
    + ")" + _AFTER)
#: `#eval` / `#eval!` — `#` is not an identifier character, so the
#: leading boundary is the literal `#`.
_EVAL_RE = re.compile(r"#eval!?" + _AFTER)
_ANCHORED_RE = re.compile(
    r"^[ \t]*(?:(?:private|protected|scoped|local)[ \t]+)*("
    + "|".join(ANCHORED_TOKENS) + ")" + _AFTER, re.MULTILINE)
_ATTR_TOKEN_RE = re.compile(
    _BEFORE + "(" + "|".join(sorted(ATTRIBUTE_TOKENS, key=len, reverse=True))
    + r"|builtin_[A-Za-z0-9_]+)" + _AFTER)
_ATTR_HEAD_RE = re.compile(
    r"^\s*(" + "|".join(_ATTR_HEAD_TOKENS) + ")" + _AFTER)
_OPTION_RE = re.compile(
    r"set_option\s+(" + "|".join(re.escape(o) for o in FORBIDDEN_OPTIONS)
    + ")" + _AFTER)


def _attribute_spans(code: str) -> "list[tuple[int, int]]":
    """`(start, end)` of every `@[…]` body (exclusive of the brackets),
    with balanced nesting — `@[simp, foo (bar := [1,2])]` is one span."""
    spans: "list[tuple[int, int]]" = []
    i, n = 0, len(code)
    while True:
        i = code.find("@[", i)
        if i < 0:
            return spans
        depth, j = 1, i + 2
        while j < n and depth:
            if code[j] == "[":
                depth += 1
            elif code[j] == "]":
                depth -= 1
            j += 1
        spans.append((i + 2, j - 1 if depth == 0 else n))
        i = j


#: Cheap superset pre-filter. Comment stripping is a per-character pass
#: (~35ms on a 110KB Library file) and runs on EVERY didChange, so skip
#: it when the raw text cannot possibly contain a hit. Sound because the
#: stripped text is a subsequence of the raw text: no substring here ⇒ no
#: match after stripping.
_PREFILTER_RE = re.compile("|".join(re.escape(s) for s in sorted(
    set(EXECUTION_TOKENS) | set(ANCHORED_TOKENS)
    | {"#eval", "@["} | set(FORBIDDEN_OPTIONS),
    key=len, reverse=True)))


def scan_metaprogramming(text: str) -> "str | None":
    """Return the first forbidden metaprogramming entry in `text`, or
    None. `text` is raw Lean source; comments are stripped first.

    THE chokepoint for the whole framework: the gateway calls it before
    any elaboration and the commit gates call it before accepting agent
    output. Both call sites are pinned by
    `tests/test_metaprog_guard.py`.
    """
    if not text or not _PREFILTER_RE.search(text):
        return None
    code = strip_lean_comments(text)

    # Attribute bodies are scanned with their own vocabulary and then
    # blanked, so declaration-modifier tokens (`unsafe`) do not fire on
    # rule attributes like `@[aesop unsafe 50%]`.
    spans = _attribute_spans(code)
    for start, end in spans:
        body = code[start:end]
        m = _ATTR_TOKEN_RE.search(body)
        if m:
            return m.group(1)
        m = _ATTR_HEAD_RE.match(body)
        if m:
            return m.group(1)
    if spans:
        buf = list(code)
        for start, end in spans:
            for k in range(start, min(end, len(buf))):
                if buf[k] != "\n":
                    buf[k] = " "
        code = "".join(buf)

    m = _EXEC_RE.search(code)
    if m:
        return m.group(1)
    m = _EVAL_RE.search(code)
    if m:
        return m.group(0)
    m = _ANCHORED_RE.search(code)
    if m:
        return m.group(1)
    m = _OPTION_RE.search(code)
    if m:
        return f"set_option {m.group(1)}"
    return None
