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
from dataclasses import dataclass
from pathlib import Path

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


def _rng(d: dict) -> "tuple[int, int, int, int]":
    return (d["startLine"], d["startCol"], d["endLine"], d["endCol"])


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
        r = lifecycle.verify_file(Path(path), write_olean=False,
                                  decl_info=True, workspace=workspace)
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

    # ---- positional plumbing ------------------------------------------

    def _offset(self, line: int, col: int) -> int:
        if not (1 <= line <= len(self._line_starts) - 1):
            return len(self.text) if line > 1 else 0
        return self._line_starts[line - 1] + col

    def _slice(self, rng: "tuple[int, int, int, int]") -> str:
        return self.text[self._offset(rng[0], rng[1]):
                         self._offset(rng[2], rng[3])]

    # ---- queries -------------------------------------------------------

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
