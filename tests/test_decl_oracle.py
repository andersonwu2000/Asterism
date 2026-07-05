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


def test_surface_decl_names_named_only_source_order():
    """defs_decls' oracle contract: names AS WRITTEN, source order, deduped;
    an anonymous instance (no declId → empty declNames) is excluded even
    though its synthesized constant appears in `decls`."""
    b = _Builder()
    r1 = b.add("def alpha : Nat := 1")
    r2 = b.add("instance : Inhabited Nat := ⟨0⟩")
    r3 = b.add("def DiffForm.integral : Nat := 2")
    cmds = [
        {**_cmd(_DECL, r1), "declNames": ["alpha"]},
        {**_cmd(_DECL, r2), "declNames": []},
        {**_cmd(_DECL, r3), "declNames": ["DiffForm.integral"]},
    ]
    decls = [
        _decl("alpha", r1, (r1[0], 4, r1[0], 9), cmd_idx=0),
        _decl("instInhabitedNat", r2, (r2[0], 0, r2[0], 8), cmd_idx=1),
        _decl("DiffForm.integral", r3, (r3[0], 4, r3[0], 21), cmd_idx=2),
    ]
    oracle = do.DeclOracle(b.text, cmds, decls)
    assert oracle.surface_decl_names() == ["alpha", "DiffForm.integral"]


def test_inventory_defs_decls_oracle_first(monkeypatch, tmp_path):
    """inventory.defs_decls consults the cached oracle; regex is the
    fallback when the oracle is unavailable."""
    from Tooling.quality.librarian import inventory as inv
    from Tooling.state import db as _db
    pdir = _db.problem_dir(tmp_path, "p1")
    pdir.mkdir(parents=True)
    # Prose in the docstring would regex-match a phantom decl without the
    # comment strip; the oracle never sees comments at all.
    (pdir / "Defs.lean").write_text(
        "/-- the analytic lemma of the bridge -/\n"
        "def realOne : Nat := 1\n", encoding="utf-8")

    fake = do.DeclOracle(
        "x", [{**_cmd(_DECL, (1, 0, 2, 22)), "declNames": ["realOne"]}],
        [_decl("realOne", (1, 0, 2, 22), (2, 4, 2, 11), cmd_idx=0)])
    monkeypatch.setattr(do.DeclOracle, "cached_for_file",
                        classmethod(lambda cls, path, workspace=None: fake))
    assert inv.defs_decls(tmp_path, "p1") == ["realOne"]

    monkeypatch.setattr(do.DeclOracle, "cached_for_file",
                        classmethod(lambda cls, path, workspace=None: None))
    assert inv.defs_decls(tmp_path, "p1") == ["realOne"]   # regex fallback


def test_cached_for_file_mtime_key_and_negative_ttl(monkeypatch, tmp_path):
    """Successes cache per (path, mtime); failures expire after the TTL so
    gateway recovery is picked up without a file change."""
    from Tooling.lsp import lifecycle as gl
    f = tmp_path / "Defs.lean"
    f.write_text("def z : Nat := 1\n", encoding="utf-8")
    calls = {"n": 0}
    payload = {
        "ok": True,
        "decl_info": {
            "commands": [{**_cmd(_DECL, (1, 0, 1, 16)),
                          "declNames": ["z"]}],
            "decls": [_decl("z", (1, 0, 1, 16), (1, 4, 1, 5), cmd_idx=0)],
        },
    }

    def fake_verify(*a, **kw):
        calls["n"] += 1
        return payload
    monkeypatch.setattr(gl, "verify_file", fake_verify)
    do._CACHE.clear()
    o1 = do.DeclOracle.cached_for_file(f, workspace=tmp_path)
    o2 = do.DeclOracle.cached_for_file(f, workspace=tmp_path)
    assert o1 is o2 and calls["n"] == 1

    # failure: cached under TTL, re-probed after expiry
    monkeypatch.setattr(gl, "verify_file",
                        lambda *a, **kw: {"error": "down",
                                          "transient": True})
    f.write_text("def z : Nat := 2\n", encoding="utf-8")   # new mtime key
    do._CACHE.clear()
    assert do.DeclOracle.cached_for_file(f, workspace=tmp_path) is None
    key = next(iter(do._CACHE))
    assert do.DeclOracle.cached_for_file(f, workspace=tmp_path) is None
    # age the negative entry past the TTL → next call re-probes
    do._CACHE[key] = (None, do.time.monotonic() - do._NEG_TTL_SEC - 1)
    monkeypatch.setattr(gl, "verify_file", fake_verify)
    assert do.DeclOracle.cached_for_file(f, workspace=tmp_path) is not None


def test_primary_user_names_from_raw_info():
    b = _Builder()
    r1 = b.add("theorem t1 : True := trivial")
    r2 = b.add("instance : Inhabited Nat := ⟨0⟩")
    info = {
        "commands": [_cmd(_DECL, r1), _cmd(_DECL, r2)],
        "decls": [
            _decl("t1", r1, (r1[0], 8, r1[0], 10), cmd_idx=0, kind="thm"),
            _decl("instInhabitedNat", r2, (r2[0], 0, r2[0], 8), cmd_idx=1),
        ],
    }
    assert do.primary_user_names(info) == ["t1", "instInhabitedNat"]


def test_defs_decl_fqn_oracle_gives_kernel_name():
    """Gate D's FQN resolution: the oracle answer IS the env userName —
    a foreign-namespace decl (`Complex.windingNumber`) resolves without
    any stack walk; regex fallback preserved on oracle miss."""
    from Tooling.pipeline.librarian.astslice import _defs_decl_fqn
    b = _Builder()
    r_ns = b.add("namespace Complex")
    r_def = b.add("def windingNumber : Nat := 0")
    r_end = b.add("end Complex")
    cmds = [_cmd(_NS, r_ns, "Complex"), _cmd(_DECL, r_def),
            _cmd(_END, r_end, "Complex")]
    decls = [_decl("Complex.windingNumber", r_def,
                   (r_def[0], 4, r_def[0], 17), cmd_idx=1)]
    oracle = do.DeclOracle(b.text, cmds, decls)
    assert _defs_decl_fqn(b.text, "windingNumber", problem="p",
                          oracle=oracle) == "Complex.windingNumber"
    assert _defs_decl_fqn(b.text, "nope", problem="p",
                          oracle=oracle) == "Problems.p.nope"   # fallback


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


# ---------------------------------------------------------------------
# ppSignature parsing (decl-#1 / decl-#2): split_signature /
# sig_conclusion / statement_from_decl_info. Samples mirror real
# ppSignature output (fully-qualified names, render-width wrapping,
# universe suffixes) captured from the sphere_homology harvest.
# ---------------------------------------------------------------------

_PP_MULTILINE = (
    "Library.A.B.contractible_zero {R : Type} [Ring R]\n"
    "  {X : TopCat} [ContractibleSpace X] (k : N) (hk : k != 0) :\n"
    "  CategoryTheory.Limits.IsZero\n"
    "    (((AlgebraicTopology.singularHomologyFunctor (ModuleCat R) k).obj\n"
    "      (ModuleCat.of R R)).obj X)")

_PP_UNIVERSE = (
    "Library.A.sphere_path_connected.{u_1} (n : N)\n"
    "  (hn : 1 <= n) : PathConnectedSpace (TopCat.sphere n)")


def test_split_signature_multiline_collapses_to_one_line():
    name, univ, rest = do.split_signature(_PP_MULTILINE)
    assert name == "Library.A.B.contractible_zero"
    assert univ == ""
    assert "\n" not in rest
    assert rest.startswith("{R : Type} [Ring R]")


def test_split_signature_universe_suffix():
    name, univ, rest = do.split_signature(_PP_UNIVERSE)
    assert name == "Library.A.sphere_path_connected"
    assert univ == ".{u_1}"
    assert rest.startswith("(n : N)")


def test_split_signature_no_binders():
    name, univ, rest = do.split_signature("Foo.bar : Nat")
    assert (name, univ, rest) == ("Foo.bar", "", ": Nat")


def test_split_signature_rejects_malformed():
    assert do.split_signature("") is None
    assert do.split_signature("bare_name_only") is None
    # colon only inside a binder group -> no top-level type colon
    assert do.split_signature("Foo.f (x : Nat)") is None


def test_sig_conclusion_strips_binders():
    assert (do.sig_conclusion(_PP_UNIVERSE)
            == "PathConnectedSpace (TopCat.sphere n)")
    out = do.sig_conclusion(_PP_MULTILINE)
    assert out.startswith("CategoryTheory.Limits.IsZero")
    assert "{R : Type}" not in out


def test_sig_conclusion_strict_implicit_binders():
    # Strict-implicit binder brackets must count as groups too.
    sig = "F.g ⦃x : A⦄ (y : B) : C x y"
    assert do.sig_conclusion(sig) == "C x y"


def test_sig_conclusion_inferred_type_def():
    # The decl-#1 payoff: pp always spells the type, even when the
    # source `def f (x : Nat) := x + 1` does not.
    assert do.sig_conclusion("Problems.p.f (x : Nat) : Nat") == "Nat"


def _sig_info(user_name, signature, *, cmd_idx=0):
    r = (1, 0, 1, 40)
    return {
        "commands": [_cmd(_DECL, r)],
        "decls": [dict(_decl(user_name, r, (1, 4, 1, 5), cmd_idx=cmd_idx),
                       signature=signature)],
    }


def test_statement_from_decl_info_finds_slug():
    info = _sig_info("Problems.p.my_lemma",
                     "Problems.p.my_lemma (n : Nat) : 0 < n + 1")
    assert do.statement_from_decl_info(info, "my_lemma") == "0 < n + 1"


def test_statement_from_decl_info_misses_return_none():
    info = _sig_info("Problems.p.my_lemma",
                     "Problems.p.my_lemma (n : Nat) : 0 < n + 1")
    assert do.statement_from_decl_info(None, "my_lemma") is None
    assert do.statement_from_decl_info({}, "my_lemma") is None
    assert do.statement_from_decl_info(info, "other_slug") is None
    # unsplittable signature -> None (caller text-fallback)
    bad = _sig_info("Problems.p.g", "")
    assert do.statement_from_decl_info(bad, "g") is None
