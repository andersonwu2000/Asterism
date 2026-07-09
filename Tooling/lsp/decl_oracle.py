"""Client-side wrapper of the `Asterism.declInfo` RPC — the syntactic oracle.

Consumers that previously re-derived Lean declaration structure from source
text with regexes (librarian astslice being the first migrated client) ask
this oracle instead. The oracle's facts come from the parsed syntax tree +
the elaborated environment (see `Asterism/GatewayRpc.lean`), so the recorded
regex bug family — `noncomputable` lost under `noncomputable section`,
decl-keyword prose in comments read as declarations, docstrings orphaned
from their decl — cannot recur on the oracle path.

Availability contract: the oracle is BEST-EFFORT. `for_file` returns None
when the gateway is unreachable, the file doesn't elaborate, or the running
`lean-asterism-server` binary predates the declInfo RPC — callers keep their
regex path as the cold fallback, so a missing oracle degrades to today's
behavior, never blocks. The `lean_contracts` `decl_info_oracle` contract
pins the RPC behaviors this wrapper consumes.

Positions: `startLine`/`endLine` are 1-based, columns are 0-based CODEPOINT
offsets (`Lean.Position`) — Python `str` indexing is codepoint-based, so the
conversion here is exact, no UTF-16 mangling.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

# cached_for_file: (resolved path, mtime_ns, size) → (oracle | None, born).
# Successes live as long as the key (mtime-invalidated); failures expire
# after _NEG_TTL_SEC so gateway recovery is picked up.
_CACHE: "dict[tuple, tuple[object, float]]" = {}
_CACHE_MAX = 256
_NEG_TTL_SEC = 60.0

_NS_KIND = "Lean.Parser.Command.namespace"
_SECTION_KIND = "Lean.Parser.Command.section"
_END_KIND = "Lean.Parser.Command.end"
_VARIABLE_KIND = "Lean.Parser.Command.variable"

# Insertion point for a reconstructed `noncomputable` modifier: the decl
# keyword at a line start (after visibility modifiers). This regex does NOT
# derive truth — the noncomputability verdict is the env's — it only locates
# where in an already-identified decl slice the keyword sits. Miss → the
# slice is returned unmodified (today's behavior; the migrate build gate
# catches it loudly, as it does now).
_DECL_KW_INSERT_RE = re.compile(
    r"(?m)^([ \t]*(?:private[ \t]+|protected[ \t]+|scoped[ \t]+|local[ \t]+)*)"
    r"(def|abbrev|instance|structure|class|inductive|theorem|lemma)\b")


@dataclass(frozen=True)
class OracleDecl:
    """One non-internal constant of the probed file (env + syntax facts)."""
    fq_name: str
    user_name: str            # private-name-normalized qualified name
    kind: str                 # kernel kind: thm / def / induct / ctor / …
    is_prop: bool
    is_noncomputable: bool
    is_protected: bool
    is_private: bool
    is_instance: bool
    signature: str            # ppSignature (section vars incorporated)
    docstring: "str | None"
    cmd_idx: int              # index into DeclOracle.commands
    range: "tuple[int, int, int, int]"       # startLine, startCol, endLine, endCol
    selection: "tuple[int, int, int, int]"
    # Direct used constants (type + body) with kernel module provenance:
    # (name, module) — module None = local to the probed file (an
    # intra-batch sibling). Populated only when the declInfo call asked
    # for `includeUsedConstants` (task #84 import derivation); () else.
    used_constants: "tuple[tuple[str, str | None], ...]" = ()


def _rng(d: dict) -> "tuple[int, int, int, int]":
    return (d["startLine"], d["startCol"], d["endLine"], d["endCol"])


# ---- ppSignature parsing ---------------------------------------------
#
# A ppSignature is `<fqName>[.{u, v}] <binders…> : <type>` — the
# elaborator's own rendering, so the type is ALWAYS explicit (an
# inferred-type `def f (x : A) := body` still prints `f (x : A) : B`),
# names are fully qualified, and section variables are incorporated.
# Splitting it needs the same top-level walk the text extractors do, but
# against pp-normal form instead of hand-written source — that is the
# entire point (statement mint / skeleton reconstruction, tasks decl-#1
# and decl-#2).

_UNIVERSE_SUFFIX_RE = re.compile(r"\.\{[^}]*\}$")
_BINDER_OPEN = {"(": ")", "{": "}", "[": "]", "⦃": "⦄"}
_BINDER_CLOSE = {v: k for k, v in _BINDER_OPEN.items()}


def split_signature(sig: str) -> "tuple[str, str, str] | None":
    """Split a ppSignature into `(name, universes, rest)`:

      name       — the fully-qualified constant name (no universe suffix)
      universes  — the literal `.{u_1, u_2}` suffix or ''
      rest       — everything after the head token, whitespace-collapsed
                   to ONE line (`<binders…> : <type>`; pp wraps at render
                   width, which is presentation, not content)

    None when `sig` is empty or has no top-level `:` after the head — a
    malformed / truncated signature the caller must not trust."""
    sig = (sig or "").strip()
    if not sig:
        return None
    parts_ws = sig.split(None, 1)      # any whitespace — pp may wrap
    if len(parts_ws) != 2:             # right after a long name
        # A bare name with no binders and no colon — nothing to split.
        return None
    head, rest = parts_ws
    m = _UNIVERSE_SUFFIX_RE.search(head)
    universes = m.group(0) if m else ""
    name = head[: m.start()] if m else head
    rest = " ".join(rest.split())
    if _top_level_colon_pos(rest) is None:
        return None
    return name, universes, rest


def _top_level_colon_pos(rest: str) -> "int | None":
    """Offset of the first `:` outside binder groups `()` `{}` `[]` `⦃⦄`
    in `rest`, or None. The type colon of a pp signature is the only
    top-level `:` — binder ascriptions all sit inside their groups."""
    depth = 0
    for i, ch in enumerate(rest):
        if ch in _BINDER_OPEN:
            depth += 1
        elif ch in _BINDER_CLOSE:
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            # `:=` never appears in a ppSignature (no body), so a bare
            # top-level `:` is the type colon.
            return i
    return None


def sig_conclusion(sig: str) -> "str | None":
    """The conclusion (type after the top-level `:`) of a ppSignature,
    single-line — the kernel-true counterpart of the text extractors'
    `goal.statement` (binders stripped, conclusion only). None when the
    signature doesn't split."""
    parts = split_signature(sig)
    if parts is None:
        return None
    _name, _univ, rest = parts
    pos = _top_level_colon_pos(rest)
    if pos is None:
        return None
    out = rest[pos + 1:].strip()
    return out or None


def statement_from_decl_info(info: "dict | None", slug: str) -> "str | None":
    """`sig_conclusion` for the decl named `slug` (exact or `.slug`-suffixed)
    in a raw `decl_info` response dict — the piggyback path for callers that
    already paid the elaboration (backward's placed-file verify, forward's
    candidate verify). None on any miss: no info, ambiguous slug, decl
    without a splittable signature — callers keep their text fallback."""
    if not info:
        return None
    o = DeclOracle("", list(info.get("commands") or []),
                   list(info.get("decls") or []))
    d = o.find(slug)
    if d is None:
        return None
    return sig_conclusion(d.signature)


def primary_user_names(info: dict) -> "list[str]":
    """Primary decls' user-facing names straight from a raw `decl_info`
    response dict — for consumers holding a response of their own (the
    migrate gate's probe elaboration) rather than a file-bound oracle.
    Position-only computation; no text needed."""
    o = DeclOracle("", list(info.get("commands") or []),
                   list(info.get("decls") or []))
    return [d.user_name for d in o.primary_decls()]


class DeclOracle:
    """declInfo response bound to the exact text it was computed against.

    `text` is read by `for_file` itself; callers holding their own copy of
    the file must compare (`oracle.text == my_text`) before trusting slices
    — a mismatch means the file changed between reads and the caller falls
    back to its regex path.
    """

    def __init__(self, text: str, commands: "list[dict]",
                 decls: "list[dict]") -> None:
        self.text = text
        self.commands = commands
        self.decls = [OracleDecl(
            fq_name=d["fqName"], user_name=d["userName"], kind=d["kind"],
            is_prop=bool(d.get("isProp")),
            is_noncomputable=bool(d.get("isNoncomputable")),
            is_protected=bool(d.get("isProtected")),
            is_private=bool(d.get("isPrivate")),
            is_instance=bool(d.get("isInstance")),
            signature=d.get("signature") or "",
            docstring=d.get("docstring"),
            cmd_idx=d["cmdIdx"],
            range=_rng(d["range"]), selection=_rng(d["selection"]),
            used_constants=tuple(
                (str(u.get("name")), u.get("module"))
                for u in (d.get("usedConstants") or [])),
        ) for d in decls]
        # 0-based offsets of each 1-based line start, computed on the SAME
        # text slices are taken from.
        starts = [0]
        for ln in text.splitlines(keepends=True):
            starts.append(starts[-1] + len(ln))
        self._line_starts = starts

    # ---- construction ------------------------------------------------

    @classmethod
    def for_file(cls, path: Path, *,
                 workspace: "Path | None" = None) -> "DeclOracle | None":
        """Elaborate `path` on the warm gateway and bind its declInfo.
        None (with a loud line) on ANY failure — callers regex-fallback."""
        from . import lifecycle
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as e:
            print(f"[decl-oracle] {path}: unreadable ({e}) — regex fallback",
                  flush=True)
            return None
        # No retries: the oracle is best-effort with an instant regex
        # fallback — burning verify_file's ~50s retry budget on a downed
        # gateway would turn every oracle miss into a stall.
        r = lifecycle.verify_file(Path(path), write_olean=False,
                                  decl_info=True, workspace=workspace,
                                  _retry_delays=())
        if r.get("error") or not r.get("ok"):
            print(f"[decl-oracle] {path}: elaborate failed "
                  f"({r.get('error') or 'diagnostics'}) — regex fallback",
                  flush=True)
            return None
        info = r.get("decl_info")
        if not info:
            # decl_info_error covers both the stale-binary case and an RPC
            # fault; an old gateway simply omits the field.
            print(f"[decl-oracle] {path}: declInfo unavailable "
                  f"({r.get('decl_info_error') or 'gateway predates RPC'}) "
                  f"— regex fallback", flush=True)
            return None
        if not info.get("decls"):
            # A decl-less view of a non-trivial file is a degenerate oracle
            # (also the unit-test verify_file stub's shape) — one line here
            # beats a misleading per-slug fallback print downstream.
            print(f"[decl-oracle] {path}: empty decl set — regex fallback",
                  flush=True)
            return None
        return cls(text, list(info.get("commands") or []),
                   list(info.get("decls") or []))

    # ---- cached construction -------------------------------------------

    @classmethod
    def cached_for_file(cls, path: Path, *,
                        workspace: "Path | None" = None
                        ) -> "DeclOracle | None":
        """`for_file` behind an (path, mtime, size)-keyed cache — hot
        callers (inventory.defs_decls has ~10 call sites per librarian
        run) must not pay one elaborate each. Failures are cached under
        the same key with a short TTL so a downed gateway costs one
        fast probe per file per minute, not one per call — and recovery
        is picked up without waiting for the file to change."""
        key = None
        try:
            st = Path(path).stat()
            key = (str(Path(path).resolve()), st.st_mtime_ns, st.st_size)
        except OSError:
            pass
        if key is not None:
            hit = _CACHE.get(key)
            if hit is not None:
                oracle, born = hit
                if oracle is not None or (time.monotonic() - born
                                          < _NEG_TTL_SEC):
                    return oracle
        oracle = cls.for_file(Path(path), workspace=workspace)
        if key is not None:
            if len(_CACHE) > _CACHE_MAX:
                _CACHE.clear()
            _CACHE[key] = (oracle, time.monotonic())
        return oracle

    # ---- positional plumbing ------------------------------------------

    def _offset(self, line: int, col: int) -> int:
        if not (1 <= line <= len(self._line_starts) - 1):
            return len(self.text) if line > 1 else 0
        return self._line_starts[line - 1] + col

    def _slice(self, rng: "tuple[int, int, int, int]") -> str:
        return self.text[self._offset(rng[0], rng[1]):
                         self._offset(rng[2], rng[3])]

    # ---- queries -------------------------------------------------------

    def surface_decl_names(self) -> "list[str]":
        """Names AS WRITTEN of every named top-level declaration, in source
        order, deduped — the oracle-path contract of
        `inventory.defs_decls`. Anonymous instances / `example`s have no
        `declId` and are excluded, matching the regex scan's named-only
        semantics (env-side synthesized names like `instFooBar` must NOT
        surface as migratable slugs)."""
        out: "list[str]" = []
        for cmd in self.commands:
            for n in cmd.get("declNames") or []:
                if n not in out:
                    out.append(n)
        return out

    def primary_decls(self) -> "list[OracleDecl]":
        """One decl per declaration command: the earliest selection in each
        cmd_idx group (a structure's projections/ctors, a `deriving`'s
        instances share their command with the head decl and come later)."""
        by_cmd: "dict[int, OracleDecl]" = {}
        for d in self.decls:
            cur = by_cmd.get(d.cmd_idx)
            if cur is None or d.selection < cur.selection:
                by_cmd[d.cmd_idx] = d
        return sorted(by_cmd.values(), key=lambda d: d.range)

    def find(self, name: str) -> "OracleDecl | None":
        """The primary decl whose user-facing name is `name` (exact) or ends
        with `.name` (slug under a namespace). Ambiguous → None (caller
        falls back; better no answer than the wrong decl)."""
        hits = [d for d in self.primary_decls()
                if d.user_name == name or d.user_name.endswith("." + name)]
        if len(hits) != 1:
            return None
        return hits[0]

    def namespace_stack(self, decl: OracleDecl) -> "list[str]":
        """Dotted namespace components open at `decl`'s command — the walk is
        over syntax kinds, never text. `section` doesn't contribute a name
        but `end` closes it, so the stack tracks both kinds and reports only
        namespace entries."""
        stack: "list[tuple[str, str | None]]" = []   # (kind, name)
        for cmd in self.commands[:decl.cmd_idx]:
            kind = cmd.get("kind")
            if kind == _NS_KIND:
                stack.append(("ns", cmd.get("name")))
            elif kind == _SECTION_KIND:
                stack.append(("sec", None))
            elif kind == _END_KIND and stack:
                stack.pop()
        return [n for k, n in stack if k == "ns" and n]

    def variables_in_scope(self, decl: OracleDecl) -> "list[str]":
        """Source text of every `variable` command in scope at `decl`: born
        before it, not yet closed by an `end` dropping below its birth depth.
        `variable (..) in <decl>` composites parse as ONE `Command.in` node
        (not kind `variable`), so decl-local re-annotations are naturally
        excluded — the exclusion the regex path implements by hand."""
        depth = 0
        alive: "list[tuple[int, str]]" = []          # (birth_depth, text)
        for cmd in self.commands[:decl.cmd_idx]:
            kind = cmd.get("kind")
            if kind in (_NS_KIND, _SECTION_KIND):
                depth += 1
            elif kind == _END_KIND:
                depth -= 1
                alive = [(bd, t) for bd, t in alive if bd <= depth]
            elif kind == _VARIABLE_KIND:
                alive.append((depth, self._slice(_rng(cmd["range"]))))
        return [t for _bd, t in alive]

    def decl_source(self, name: str) -> "str | None":
        """Self-contained source slice for decl `name`: the full declaring
        command (docstring + attrs + any `open X in` prefix included — they
        are part of the command node), reconstructed keyword modifiers the
        surface text doesn't carry (a def under `noncomputable section` —
        env truth), prepended with the `variable` commands in scope. The
        oracle-path equivalent of astslice `_defs_decl_source`."""
        d = self.find(name)
        if d is None:
            return None
        cmd = (self.commands[d.cmd_idx]
               if d.cmd_idx < len(self.commands) else None)
        if cmd is None:
            return None
        body = self._slice(_rng(cmd["range"])).rstrip()
        if d.is_noncomputable and not re.search(r"\bnoncomputable\b", body):
            m = _DECL_KW_INSERT_RE.search(body)
            if m:
                at = m.start(2)
                body = body[:at] + "noncomputable " + body[at:]
            else:
                print(f"[decl-oracle] {name}: noncomputable reconstruction "
                      f"found no decl keyword — slice left as-is", flush=True)
        in_scope = self.variables_in_scope(d)
        if in_scope:
            return ("\n".join(s.rstrip() for s in in_scope)
                    + "\n\n" + body).rstrip()
        return body
