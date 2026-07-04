"""DeclOracle — client wrapper of the Asterism.declInfo RPC (the syntactic
oracle; task: retire regex extraction).

All Lean-free: oracles are built from canned declInfo JSON over synthetic
file text. The RPC's own behavior is pinned by the `decl_info_oracle`
lean-contract (real_lake); these tests pin the CLIENT-side logic — position
plumbing, scope walks, modifier reconstruction, and the astslice fallback
seams.
"""
from __future__ import annotations

from pathlib import Path

from Tooling.lsp import decl_oracle as do
from Tooling.pipeline.librarian.astslice import (
    _defs_decl_namespace,
    _defs_decl_source,
)

_NS = "Lean.Parser.Command.namespace"
_SEC = "Lean.Parser.Command.section"
_END = "Lean.Parser.Command.end"
_VAR = "Lean.Parser.Command.variable"
_DECL = "Lean.Parser.Command.declaration"
_IN = "Lean.Parser.Command.in"


class _Builder:
    """Assemble file text line-by-line while recording (1-based line,
    0-based col) command ranges — no hand-counted positions."""

    def __init__(self):
        self.lines: list[str] = []

    def add(self, *lines: str) -> "tuple[int, int, int, int]":
        start = len(self.lines) + 1
        self.lines.extend(lines)
        end = len(self.lines)
        return (start, 0, end, len(lines[-1]))

    @property
    def text(self) -> str:
        return "\n".join(self.lines) + "\n"


def _rng_d(r):
    return {"startLine": r[0], "startCol": r[1],
            "endLine": r[2], "endCol": r[3]}


def _cmd(kind, r, name=None):
    d = {"kind": kind, "range": _rng_d(r)}
    if name:
        d["name"] = name
    return d


def _decl(user_name, r, sel, *, cmd_idx, kind="def", fq=None,
          noncomputable=False, private=False, docstring=None):
    return {"fqName": fq or user_name, "userName": user_name, "kind": kind,
            "isProp": False, "isNoncomputable": noncomputable,
            "isProtected": False, "isPrivate": private, "isInstance": False,
            "signature": "", "docstring": docstring, "cmdIdx": cmd_idx,
            "range": _rng_d(r), "selection": _rng_d(sel)}


def _noncomputable_section_fixture():
    """The live-gap shape: a data def authored under `noncomputable section`
    with a section variable in scope — the regex path drops the modifier
    (memory: librarian_migrate_drops_section_noncomputable)."""
    b = _Builder()
    r_ns = b.add("namespace Problems.p")
    r_sec = b.add("noncomputable section")
    r_var = b.add("variable (n : Nat)")
    r_def = b.add("/-- doc -/", "def sq : Nat := n * n")
    r_end = b.add("end")
    r_endns = b.add("end Problems.p")
    cmds = [
        _cmd(_NS, r_ns, "Problems.p"),
        _cmd(_SEC, r_sec),
        _cmd(_VAR, r_var),
        _cmd(_DECL, r_def),
        _cmd(_END, r_end),
        _cmd(_END, r_endns, "Problems.p"),
    ]
    sel = (r_def[2], 4, r_def[2], 6)   # the `sq` token
    decls = [_decl("Problems.p.sq", r_def, sel, cmd_idx=3,
                   noncomputable=True, docstring="doc ")]
    return b.text, cmds, decls


def test_decl_source_reconstructs_noncomputable_and_variables():
    text, cmds, decls = _noncomputable_section_fixture()
    oracle = do.DeclOracle(text, cmds, decls)
    src = oracle.decl_source("sq")
    assert src == ("variable (n : Nat)\n\n"
                   "/-- doc -/\n"
                   "noncomputable def sq : Nat := n * n")


def test_astslice_defs_decl_source_oracle_beats_regex_on_section_modifier():
    """End-seam check: the astslice entry point with the oracle returns the
    modifier the regex path loses — the live gap, fixed at the layer migrate
    actually calls."""
    text, cmds, decls = _noncomputable_section_fixture()
    oracle = do.DeclOracle(text, cmds, decls)
    with_oracle = _defs_decl_source(text, "sq", oracle=oracle)
    assert "noncomputable def sq" in with_oracle
    regex_only = _defs_decl_source(text, "sq")
    assert "noncomputable" not in regex_only   # the gap this closes


def test_decl_source_variable_scope_dies_with_its_section():
    """A `variable` inside a CLOSED sibling section must not leak into a
    later decl's slice (depth bookkeeping)."""
    b = _Builder()
    r_sec1 = b.add("section")
    r_var1 = b.add("variable (dead : Int)")
    r_end1 = b.add("end")
    r_var2 = b.add("variable (live : Nat)")
    r_def = b.add("def f : Nat := live")
    cmds = [
        _cmd(_SEC, r_sec1), _cmd(_VAR, r_var1), _cmd(_END, r_end1),
        _cmd(_VAR, r_var2), _cmd(_DECL, r_def),
    ]
    decls = [_decl("f", r_def, (r_def[0], 4, r_def[0], 5), cmd_idx=4)]
    oracle = do.DeclOracle(b.text, cmds, decls)
    src = oracle.decl_source("f")
    assert "live" in src and "dead" not in src


def test_decl_source_open_in_composite_keeps_prefix():
    """`open X in <decl>` is ONE command node — the slice keeps the prefix
    without any head-walking heuristics."""
    b = _Builder()
    r = b.add("open Classical in", "def g : Prop := True")
    cmds = [_cmd(_IN, r)]
    decls = [_decl("g", (r[2], 0, r[2], r[3]), (r[2], 4, r[2], 5),
                   cmd_idx=0)]
    oracle = do.DeclOracle(b.text, cmds, decls)
    assert oracle.decl_source("g") == ("open Classical in\n"
                                       "def g : Prop := True")


def test_namespace_stack_and_astslice_namespace_seam():
    """Foreign namespace detection (`namespace Complex` under the problem
    file) via syntax kinds; `end` pops sections too."""
    b = _Builder()
    r_ns = b.add("namespace Complex")
    r_sec = b.add("section")
    r_end = b.add("end")
    r_def = b.add("def windingNumber : Nat := 0")
    r_endns = b.add("end Complex")
    cmds = [
        _cmd(_NS, r_ns, "Complex"), _cmd(_SEC, r_sec), _cmd(_END, r_end),
        _cmd(_DECL, r_def), _cmd(_END, r_endns, "Complex"),
    ]
    decls = [_decl("Complex.windingNumber", r_def,
                   (r_def[0], 4, r_def[0], 17), cmd_idx=3)]
    oracle = do.DeclOracle(b.text, cmds, decls)
    assert _defs_decl_namespace(b.text, "windingNumber",
                                oracle=oracle) == "Complex"


def test_find_ambiguous_returns_none_and_regex_falls_back():
    """Two primaries sharing a leaf name → find refuses (no answer beats the
    wrong decl); the astslice seam then runs the regex walk."""
    b = _Builder()
    r1 = b.add("namespace A")
    r_d1 = b.add("def dup : Nat := 1")
    r2 = b.add("end A")
    r3 = b.add("namespace B")
    r_d2 = b.add("def dup : Nat := 2")
    r4 = b.add("end B")
    cmds = [_cmd(_NS, r1, "A"), _cmd(_DECL, r_d1), _cmd(_END, r2, "A"),
            _cmd(_NS, r3, "B"), _cmd(_DECL, r_d2), _cmd(_END, r4, "B")]
    decls = [
        _decl("A.dup", r_d1, (r_d1[0], 4, r_d1[0], 7), cmd_idx=1),
        _decl("B.dup", r_d2, (r_d2[0], 4, r_d2[0], 7), cmd_idx=4),
    ]
    oracle = do.DeclOracle(b.text, cmds, decls)
    assert oracle.find("dup") is None
    # seam: falls back to the regex walk, which returns the FIRST match —
    # the pre-oracle behavior, unchanged.
    src = _defs_decl_source(b.text, "dup", oracle=oracle)
    assert ":= 1" in src


def test_astslice_oracle_text_drift_falls_back_to_regex():
    """An oracle bound to different text than the caller's copy must be
    ignored entirely (file changed between reads)."""
    text, cmds, decls = _noncomputable_section_fixture()
    oracle = do.DeclOracle(text, cmds, decls)
    drifted = text + "-- trailing edit\n"
    src = _defs_decl_source(drifted, "sq", oracle=oracle)
    assert src is not None and "noncomputable" not in src   # regex path


def test_primary_decl_selection_within_command_group():
    """A structure's companions (ctor / projections) share its command; the
    primary is the earliest selection."""
    b = _Builder()
    r = b.add("structure Pt where", "  x : Nat")
    cmds = [_cmd(_DECL, r)]
    decls = [
        _decl("Pt.mk", r, (r[0], 10, r[0], 12), cmd_idx=0, kind="ctor"),
        _decl("Pt", r, (r[0], 10, r[0], 12), cmd_idx=0, kind="induct"),
        _decl("Pt.x", (r[2], 2, r[2], 10), (r[2], 2, r[2], 3), cmd_idx=0),
    ]
    # Pt's selection ties with Pt.mk here (both at the head); make Pt's
    # earlier to model the real head-name-first layout.
    decls[1]["selection"] = _rng_d((r[0], 10, r[0], 11))
    oracle = do.DeclOracle(b.text, cmds, decls)
    prim = oracle.primary_decls()
    assert [d.user_name for d in prim] == ["Pt"]
    assert oracle.find("Pt").kind == "induct"


def test_for_file_degrades_to_none(monkeypatch, tmp_path):
    """Every failure shape → None (callers regex-fallback): elaborate error,
    missing decl_info (old gateway), empty decl set (unit-test stub shape),
    unreadable file."""
    from Tooling.lsp import lifecycle as gl
    f = tmp_path / "Defs.lean"
    f.write_text("def x : Nat := 1\n", encoding="utf-8")

    responses = iter([
        {"error": "gateway unreachable", "transient": True},
        {"ok": True},                                      # no decl_info key
        {"ok": True, "decl_info": {"commands": [], "decls": []}},
    ])
    monkeypatch.setattr(gl, "verify_file",
                        lambda *a, **kw: next(responses))
    assert do.DeclOracle.for_file(f, workspace=tmp_path) is None
    assert do.DeclOracle.for_file(f, workspace=tmp_path) is None
    assert do.DeclOracle.for_file(f, workspace=tmp_path) is None
    assert do.DeclOracle.for_file(tmp_path / "nope.lean",
                                  workspace=tmp_path) is None


def test_for_file_builds_from_gateway_payload(monkeypatch, tmp_path):
    """Happy path: verify_file(decl_info=True) payload → bound oracle whose
    slices come from the file's actual text."""
    from Tooling.lsp import lifecycle as gl
    f = tmp_path / "Defs.lean"
    f.write_text("def y : Nat := 2\n", encoding="utf-8")
    payload = {
        "ok": True,
        "decl_info": {
            "commands": [_cmd(_DECL, (1, 0, 1, 16))],
            "decls": [_decl("y", (1, 0, 1, 16), (1, 4, 1, 5), cmd_idx=0)],
        },
    }
    seen = {}

    def fake_verify(target_path, **kw):
        seen["decl_info"] = kw.get("decl_info")
        return payload
    monkeypatch.setattr(gl, "verify_file", fake_verify)
    oracle = do.DeclOracle.for_file(f, workspace=tmp_path)
    assert seen["decl_info"] is True
    assert oracle is not None
    assert oracle.decl_source("y") == "def y : Nat := 2"
