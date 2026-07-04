"""librarian.astslice — split out of the former pipeline/librarian.py monolith."""
from __future__ import annotations

import re

from ._base import MigratedDecl


_COMPLEX_DECL_RE = re.compile(
    r"(?m)^[ \t]*(?:@\[[^\]]*\][ \t]*)*"
    r"(?:private[ \t]+|protected[ \t]+|noncomputable[ \t]+|scoped[ \t]+"
    r"|local[ \t]+)*"
    r"(?:structure|class|instance|inductive|abbrev|axiom)\b")
_DECL_COMMENT_RE = re.compile(r"--[^\n]*|/-.*?-/", re.DOTALL)


_DECL_KW = ("theorem", "lemma", "def", "abbrev", "structure",
            "class", "instance", "inductive")
_DECL_RE = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*"
    r"(?:noncomputable\s+|private\s+|protected\s+|scoped\s+)*"
    # Dotted declaration names (`def DiffForm.integral`, a namespace
    # extension) must capture WHOLE — truncating at the dot made the axiom
    # probe reference a nonexistent constant (`Unknown constant
    # …StokesIntegralDefs.DiffForm`, stokes_integral 2026-06-12).
    r"(?:" + "|".join(_DECL_KW)
    + r")\s+([A-Za-z_][\w']*(?:\.[A-Za-z_][\w']*)*)")
_NS_RE = re.compile(r"^\s*namespace\s+([A-Za-z_][\w.]*)")


# Decl-kind detector (Gate D must distinguish def/abbrev from nominal
# kinds, and per-file migrate maps each decl positionally). Reuses
# _DECL_KW; captures the keyword rather than the name.
_DECL_KW_RE = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*"
    r"(?:noncomputable\s+|private\s+|protected\s+|scoped\s+)*"
    r"(def|abbrev|theorem|lemma|structure|class|inductive|instance)\b")

# Nominal kinds: two separate declarations are never definitionally equal
# even with identical fields, so `rfl` (Gate D) cannot equate them.
_NOMINAL_KINDS = ("structure", "class", "inductive")

# `end <ns>` closes a namespace opened by `namespace <ns>`.
_END_RE = re.compile(r"^\s*end\s+([A-Za-z_][\w.]*)")


def extract_decls(patch_text: str) -> "list[MigratedDecl]":
    """Every named top-level declaration in a patch, in source order.

    Per-file migrate pairs these positionally with the file's classified
    slugs (file_order) to backfill each `target_name`, run the per-decl
    axiom check, and drive Gate D. Tracks the open namespace(s) so each
    name is fully qualified; an `end <ns>` matching the innermost open
    namespace pops it, so multi-section files qualify correctly."""
    # Strip comments first so decl-keyword prose inside a `/-! … -/` docstring or
    # a `-- …` line (e.g. "the analytic lemma of the bridge") is not mis-read as a
    # declaration. Same class as the `defs_decls` phantom-`of` bug (2026-06-30).
    patch_text = _DECL_COMMENT_RE.sub("", patch_text)
    ns_stack: list[str] = []
    out: list[MigratedDecl] = []
    for line in patch_text.splitlines():
        m = _NS_RE.match(line)
        if m:
            ns_stack.append(m.group(1))
            continue
        me = _END_RE.match(line)
        if me and ns_stack and ns_stack[-1] == me.group(1):
            ns_stack.pop()
            continue
        m = _DECL_RE.match(line)
        if m:
            mk = _DECL_KW_RE.match(line)
            ns = ".".join(ns_stack)
            out.append(MigratedDecl(
                kind=mk.group(1) if mk else None, name=m.group(1),
                fq_name=f"{ns}.{m.group(1)}" if ns else m.group(1)))
    return out


def extract_decl_fq_name(patch_text: str) -> str | None:
    """The fully-qualified name of the FIRST named declaration in a patch
    (`<namespace>.<decl>`), or None when none is found. Convenience over
    `extract_decls` for single-decl callers (e.g. Gate D's fallback when
    no explicit name is supplied). The FQ name is namespace-derived, so it
    resolves under `#print axioms` regardless of the (temp) file name."""
    decls = extract_decls(patch_text)
    return decls[0].fq_name if decls else None


def extract_decl_kind(patch_text: str) -> str | None:
    """The keyword (`def` / `abbrev` / `theorem` / …) of the first named
    declaration in a patch, or None. Convenience over `extract_decls`."""
    decls = extract_decls(patch_text)
    return decls[0].kind if decls else None


def _library_module_of(rel_lean_path: str) -> str:
    """Map a Library file's repo-relative path to its Lean module name:
    `Library/LinearAlgebra/JordanForm/Defs.lean` →
    `Library.LinearAlgebra.JordanForm.Defs`."""
    p = rel_lean_path.replace("\\", "/")
    if p.endswith(".lean"):
        p = p[:-5]
    return p.replace("/", ".")


def _nominal_decl_src(text: str, slug: str) -> "str | None":
    """The SOURCE of declaration `slug` in `text`: its keyword head through
    to the next top-level command (decl / variable / section / end),
    excluding the preceding docstring (comments are stripped by the
    normalized comparison anyway). None when `slug` isn't declared here.
    Covers every decl keyword: the verbatim guard serves nominal kinds AND
    defs whose rfl probe cannot cross a re-declared nominal boundary."""
    head = re.compile(
        rf"(?m)^[ \t]*(?:@\[[^\]]*\][ \t]*)*"
        rf"(?:noncomputable\s+|private\s+|protected\s+|scoped\s+)*"
        rf"(?:" + "|".join(_DECL_KW) + rf")\s+{re.escape(slug)}\b")
    m = head.search(text)
    if m is None:
        return None
    rest = text[m.start():]
    nxt = re.search(
        r"(?m)^(?:@\[[^\]]*\]\s*)*"
        r"(?:noncomputable\s+|private\s+|protected\s+|scoped\s+)*"
        r"(?:def|abbrev|theorem|lemma|structure|class|inductive|instance)"
        r"\s+[A-Za-z_]"
        # A scoped `open X in` line introduces the NEXT decl (it is that decl's
        # prefix), so it bounds the current slice — else `_nominal_decl_src`
        # over-captures the trailing `open … in` of the following declaration
        # (residue_thm's `windingNumber` is followed by `open Classical in` +
        # `residue`), making the verbatim guard's source comparison spuriously
        # unequal to the migrated copy (which has a different next decl).
        r"|^open\b[^\n]*\bin\b[ \t]*$"
        r"|^variable\b|^section\b|^end\b", rest[1:])
    return rest[:nxt.start() + 1] if nxt else rest


def _defs_decl_fqn(defs_text: str, slug: str, *, problem: str) -> str:
    """Real fully-qualified name of Defs declaration `slug` as it lives in
    `Problems.<problem>.Defs`, accounting for a foreign `namespace` the problem
    declares its OWN decls under (residue_thm puts `windingNumber`/`residue`
    under `namespace Complex`, so the FQN is `Complex.windingNumber`, NOT
    `Problems.<problem>.windingNumber` — cf. the relabel-side `self_namespaces`).
    Walks the namespace stack to the decl header. Falls back to the standard
    `Problems.<problem>.<slug>` when `slug` is not found (preserves the
    historical default for the common in-`Problems`-namespace case)."""
    stack: list[str] = []
    head = re.compile(
        r"^[ \t]*(?:@\[[^\]]*\][ \t]*)*"
        r"(?:private[ \t]+|protected[ \t]+|noncomputable[ \t]+|scoped[ \t]+)*"
        r"(?:def|abbrev|theorem|lemma|instance|structure|class|inductive)"
        r"[ \t]+([A-Za-z_][\w'.]*)")
    for raw in defs_text.splitlines():
        s = raw.strip()
        m = re.match(r"^namespace\s+([\w.]+)\s*$", s)
        if m:
            stack.append(m.group(1))
            continue
        m = re.match(r"^end\s+([\w.]+)\s*$", s)
        if m:
            if stack and stack[-1] == m.group(1):
                stack.pop()
            continue
        m = head.match(raw)
        if m and m.group(1).split(".")[-1] == slug:
            return ".".join(p for p in (*stack, m.group(1)) if p)
    return f"Problems.{problem}.{slug}"


# Decl head up to and including the name — its end is where the binders
# start. Dotted names (`def DiffForm.integral`) must be consumed whole or
# the signature slice starts mid-name.
_DECL_HEAD_RE = re.compile(
    r"(?:noncomputable\s+|private\s+|protected\s+|scoped\s+)*"
    r"(?:def|abbrev|theorem|lemma|instance)\s+"
    r"[A-Za-z_][\w']*(?:\.[A-Za-z_][\w']*)*")


def _decl_signature(text: str) -> str:
    """The NAME-STRIPPED, whitespace-normalized signature (binders +
    conclusion type) of the first theorem/def in a proof file — everything
    from just after the decl name up to the proof body (`:= by`, or the last
    term-mode `:=`).

    Used to test whether a verbatim-merge pair is *callable-compatible*:
    `goals.statement` holds only the CONCLUSION, so two lemmas with the same
    conclusion but different binders (e.g. `..._of_sum_zero` taking an extra
    hypothesis) compare equal there yet have different argument lists — a
    citation rename then mis-positions call-site args (root cause 1). Comparing
    the full signature catches that and declines the rename to the LLM path."""
    m = _DECL_HEAD_RE.search(text)
    if not m:
        return ""
    region = text[m.end():]
    bym = re.search(r":=\s*by\b", region)
    cut = bym.start() if bym else None
    if cut is None:
        last = None
        for mm in re.finditer(r":=", region):
            last = mm
        cut = last.start() if last else len(region)
    return " ".join(region[:cut].split())


def _variable_block_spans(defs_text: str) -> "list[tuple[int, int, str]]":
    """Every file/section-level `variable` command in `defs_text` as
    `(start_offset, end_offset, text)`. A command runs from its `variable`
    keyword through its indented continuation lines (binders wrap; any line
    starting with whitespace continues the command)."""
    spans: list[tuple[int, int, str]] = []
    lines = defs_text.splitlines(keepends=True)
    pos = 0
    i = 0
    while i < len(lines):
        ln = lines[i]
        if re.match(r"variable\b", ln.strip()):
            start = pos
            j = i + 1
            block = ln
            p2 = pos + len(ln)
            while j < len(lines) and lines[j][:1] in (" ", "\t"):
                block += lines[j]
                p2 += len(lines[j])
                j += 1
            # `variable (..) in` is a LOCAL re-annotation for the next decl, not
            # a section-level variable — exclude it (it travels in its own decl's
            # slice via `_head_start`; replaying it elsewhere dangled it on the
            # previous slice / prepended it to later decls → migrate build broke,
            # stokes_induced_orient POU 2026-06-12).
            if not re.search(r"\bin\Z", block.rstrip()):
                spans.append((start, p2, block.rstrip()))
            pos = p2
            i = j
            continue
        pos += len(ln)
        i += 1
    return spans


def _defs_decl_source(defs_text: str, name: str,
                      oracle=None) -> "str | None":
    """A SELF-CONTAINED slice of `Defs.lean` declaring `name`: the decl's
    keyword head through to the next top-level declaration / enclosing `end`,
    PREPENDED with every `variable` command in scope at the decl's position.

    `oracle` (a `Tooling.lsp.decl_oracle.DeclOracle` bound to the same text)
    answers first when provided: spans/scope/modifiers then come from the
    parsed syntax tree + env — which fixes the class this regex path can't
    represent (a data def under `noncomputable section` loses its modifier;
    the slice boundary heuristics below are each a patched incident). The
    regex walk below is the cold fallback (no gateway / stale binary /
    oracle text drift) and the unit-test default.

    A Defs decl authored inside `section X / variable {E …} [inst …] / end X`
    references its binders through the section context — slicing the decl
    alone loses them (auto-bound implicits then drop the instance constraints
    → `synthInstanceFailed` at migrate build, stokes form_coord 2026-06-11)
    and drags the stray `end X` along. Scope tracking: `variable` commands are
    in scope from their position until the `end` that closes their enclosing
    `section`/`namespace`; the wrapping namespace is re-created by the caller,
    so only the variable lines (not `section`/`end` markers) are replayed.

    Defs decls have no `proofs/L_<slug>.lean`; this gives them the same
    per-decl source every other migratable decl has, so they relabel through
    the one mechanical path instead of forcing a cold from-scratch spawn."""
    if oracle is not None and oracle.text == defs_text:
        src = oracle.decl_source(name)
        if src is not None:
            return src
        # Oracle bound but decl unseen there (renamed? non-primary?) — the
        # regex walk may still find it; note the divergence signal.
        print(f"[decl-oracle] `{name}` not in oracle view — regex fallback",
              flush=True)
    from ...quality.librarian.inventory import _DEFS_DECL_RE
    matches = list(_DEFS_DECL_RE.finditer(defs_text))

    def _head_start(pos: int) -> int:
        """Extend a decl-head offset backwards over its immediately-preceding
        `/-- ... -/` docstring, so the docstring travels in the decl's OWN
        slice. With next-decl-head slicing alone, decl N+1's docstring sits at
        the tail of decl N's slice -- harmless while slices were concatenated
        verbatim, but the per-slice `variable` replay then lands BETWEEN a
        docstring and its decl -> `unexpected token 'variable'; expected
        'lemma'` (stokes bdry_chart 2026-06-11)."""
        # Pull `@[attr]`, a `variable (..) in`, and the docstring into the slice.
        while True:
            head = defs_text[:pos].rstrip()
            nl = head.rfind("\n")
            last = head[nl + 1:].strip()
            # standalone attribute line(s) (e.g. `@[instance]` on its own line)
            if last.startswith("@[") and last.endswith("]"):
                pos = nl + 1 if nl >= 0 else 0
                continue
            # `variable (..) in` binds ONLY to the next decl (single-line form)
            if re.match(r"variable\b.*\bin\Z", last):
                pos = nl + 1 if nl >= 0 else 0
                continue
            # `open X in` likewise scopes to the next decl — keep it WITH the
            # decl in its slice (residue_thm declares defs under `open Classical
            # in`). Hoisting it file-level dangles a scoped-open above
            # `namespace` and breaks the parse ("Missing name after `end`").
            if re.match(r"open\b.*\bin\Z", last):
                pos = nl + 1 if nl >= 0 else 0
                continue
            # an immediately-preceding `/-- ... -/` docstring. The trailing `-/`
            # must close THIS `/--` (no closer between) — else it ends some
            # other comment form (`/-!`, `/- ... -/`).
            if head.endswith("-/"):
                k = head.rfind("/--")
                if k != -1 and "-/" not in head[k + 3:-2]:
                    pos = k
                    continue
            break
        return pos

    for i, m in enumerate(matches):
        if m.group(2) != name:
            continue
        start = _head_start(m.start())
        end = (_head_start(matches[i + 1].start())
               if i + 1 < len(matches) else len(defs_text))
        body = defs_text[start:end]
        # Trim trailing `end <X>` closers that the next-decl/EOF cut dragged
        # in — they close scopes the slice does not open.
        body_lines = body.rstrip().splitlines()
        while body_lines and (not body_lines[-1].strip()
                              or re.match(r"\s*end\b", body_lines[-1])):
            body_lines.pop()
        body = "\n".join(body_lines).rstrip()
        # `variable` commands in scope at the decl: declared before it, and
        # not closed by an `end` between their position and the decl. Track
        # scope depth: each `section`/`namespace` line pushes, `end` pops —
        # a variable at depth d dies when depth drops below d.
        in_scope: list[str] = []
        var_spans = _variable_block_spans(defs_text)
        depth = 0
        var_depth: dict[int, int] = {}      # span index -> depth at decl
        events: list[tuple[int, str, int]] = []
        for mm in re.finditer(r"^[ \t]*(section\b|namespace\b|end\b)",
                              defs_text, re.M):
            events.append((mm.start(), mm.group(1).strip(), 0))
        for k, (s, _e, _t) in enumerate(var_spans):
            events.append((s, "var", k))
        events.sort()
        alive: dict[int, int] = {}          # span index -> birth depth
        for off, kind, k in events:
            if off >= start:
                break
            if kind in ("section", "namespace"):
                depth += 1
            elif kind == "end":
                depth -= 1
                for vk, bd in list(alive.items()):
                    if bd > depth:
                        del alive[vk]
            else:
                alive[k] = depth
        in_scope = [var_spans[k][2] for k in sorted(alive)]
        if in_scope:
            return ("\n".join(in_scope) + "\n\n" + body).rstrip()
        return body
    return None


def _defs_decl_namespace(defs_text: str, name: str,
                         oracle=None) -> "str | None":
    """The dotted namespace a Defs.lean decl `name` is declared under, or None
    if it sits at file top level. With `oracle` (same-text `DeclOracle`) the
    stack comes from syntax kinds; the regex line walk is the fallback.

    An operator who authors a Defs decl under an explicit namespace (e.g.
    residue_thm puts `windingNumber`/`residue` under `namespace Complex`) makes
    that namespace LOAD-BEARING: the root statement cites the decl by the
    qualified name `Complex.windingNumber`, so the migrated Library copy must
    keep the SAME qualified name or Gate B can no longer re-derive the original
    statement. This tells the migrate which namespace to preserve. The
    framework's own scaffolding namespace (`Problems.<p>`) is NOT operator-
    specified and is relabelled to the Library namespace as usual — preserving
    it would leak `Problems.<p>` into the (must-be-self-sufficient) Library."""
    if oracle is not None and oracle.text == defs_text:
        d = oracle.find(name)
        if d is not None:
            stack = oracle.namespace_stack(d)
            return ".".join(stack) if stack else None
        print(f"[decl-oracle] `{name}` not in oracle view — regex fallback",
              flush=True)
    from ...quality.librarian.inventory import _DEFS_DECL_RE
    decl_pos = None
    for m in _DEFS_DECL_RE.finditer(defs_text):
        if m.group(2) == name:
            decl_pos = m.start()
            break
    if decl_pos is None:
        return None
    stack: list[str] = []
    for line in defs_text[:decl_pos].splitlines():
        mn = _NS_RE.match(line)
        if mn:
            stack.append(mn.group(1))
            continue
        me = _END_RE.match(line)
        if me and stack and stack[-1] == me.group(1):
            stack.pop()
    return ".".join(stack) if stack else None


def _ns_is_operator_specified(ns: "str | None", problem: str) -> bool:
    """True iff `ns` is an explicit operator-chosen namespace whose decls must
    be PRESERVED on migration (vs the framework's `Problems.<p>` scaffolding,
    which is relabelled to the Library namespace). Self-sufficiency rule: the
    Library never references `Problems.<p>`, so only non-scaffolding namespaces
    are preserved."""
    return bool(ns) and ns != f"Problems.{problem}" \
        and not ns.startswith("Problems.")
