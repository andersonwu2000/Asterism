"""Metaprogramming gate invariants (`Tooling/state/metaprog.py`).

Three layers are pinned here:

  1. STRUCTURAL — every path that hands agent-written Lean text to an
     elaborator, and every commit gate that accepts agent Lean output,
     calls the shared scanner. The enumeration below IS the audit: a new
     gateway tool or commit path that elaborates un-scanned text has to
     either call the scanner or delete a line from this list.
  2. BEHAVIOUR — the execution entries are caught, the deliberately
     allowed constructs are not, and the two lexical bypasses the
     comment stripper exists to close (a `/-` inside a string, a `"`
     inside a char literal) stay closed.
  3. CORPUS — the gate fires on ZERO existing legitimate proofs. This is
     the false-positive investigation, frozen as a test: `elab` really
     does occur in committed proof comments ("(~64s elab)"), which is
     why the scanner strips comments, and `syntax` really does occur in
     a Library doc comment, which is why it is anchored to command
     position.

Rationale for what is and is not on the list lives in the module
docstring; this file only guards it.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from Tooling.state import metaprog
from Tooling.state.failures import REGISTRY

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = ROOT / "Tooling" / "lsp" / "gateway" / "__init__.py"
GATEWAY_RPC = ROOT / "Tooling" / "lsp" / "gateway" / "rpc.py"
CLIENT = ROOT / "Tooling" / "lsp" / "client.py"
BACKWARD = ROOT / "Tooling" / "pipeline" / "backward.py"
FORWARD = ROOT / "Tooling" / "pipeline" / "forward.py"
LAKE_PROBE = ROOT / "Tooling" / "quality" / "lake_probe.py"
DEDUPE = ROOT / "Tooling" / "quality" / "dedupe.py"
LIB_EXECUTE = ROOT / "Tooling" / "pipeline" / "librarian" / "execute.py"
LIB_GATE = ROOT / "Tooling" / "pipeline" / "librarian" / "gate.py"


def _fn_source(path: Path, name: str) -> str:
    """Source of the top-level (or nested) function `name` in `path`."""
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name):
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{path.name}: no function named {name!r} — the "
                         "metaprogramming-gate enumeration is stale")


# ---------------------------------------------------------------------
# 1. Structural — the enumerated entry points
# ---------------------------------------------------------------------

#: The LSP boundary. EVERY elaboration in this framework goes through
#: these two notifications, so the hard backstop lives here and cannot be
#: bypassed by adding a gateway path.
@pytest.mark.parametrize("name", ["did_open", "did_change_full"])
def test_lsp_boundary_guards_every_elaboration(name) -> None:
    src = _fn_source(CLIENT, name)
    assert "_guard_metaprogramming(" in src, (
        f"client.{name} must call `_guard_metaprogramming` before pushing "
        "text into a Lean worker — it is the one place no elaboration can "
        "route around")


#: Gateway entries that accept agent text. Each answers with the
#: teaching message instead of letting the backstop raise.
#:   apply_edit        — the agent's own edit tool
#:   goal_at/errors_at — elaborate the DISK buffer, so they cover the
#:                       `Write`/`Edit` tools that bypass apply_edit
#:   validate_file     — pre-commit candidate probe
#:   _verify_sync      — /verify (framework probe, borrow slot)
#:   _verify_session_sync — /verify_session (framework probe, own slot)
#:   interactive_sync  — the browser editor's full-buffer set
#:
#: `interactive_sync` was exempt until 2026-08-15 on the grounds that it
#: delegated to `apply_edit`; the exemption outlived the delegation by
#: five days (the line-range `apply_edit(1, end, content)` retired in
#: `1d7ad006`, and the call had been a TypeError ever since). A guard
#: whose premise is "some other function checks it" is only as good as
#: that call surviving — this list now asks every entry for its own.
#:
#: Each entry carries the FILE it lives in, so the enumeration stays an
#: audit after the gateway became a package: the three in-spawn tools
#: moved to `gateway/rpc.py` with the A1-4a split, and a name-only list
#: would have failed as "no function named" rather than telling anyone
#: where to look.
@pytest.mark.parametrize("path, name", [
    (GATEWAY_RPC, "apply_edit"), (GATEWAY_RPC, "goal_at"),
    (GATEWAY_RPC, "errors_at"), (GATEWAY, "validate_file"),
    (GATEWAY, "_verify_sync"), (GATEWAY, "_verify_session_sync"),
    (GATEWAY, "interactive_sync"),
], ids=lambda v: getattr(v, "name", v))
def test_gateway_entry_scans_agent_text(path, name) -> None:
    src = _fn_source(path, name)
    assert "_metaprog_error(" in src, (
        f"gateway.{name} elaborates agent-supplied text and must scan it "
        "first (`_metaprog_error`) so the agent gets the rule, not a "
        "stack trace")


@pytest.mark.parametrize("path", [BACKWARD, FORWARD])
def test_commit_gate_scans_agent_output(path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "metaprog.scan_metaprogramming(" in text, (
        f"{path.name}: the commit gate must scan the agent's Lean output "
        "(the file can reach disk via Write/Edit without any LSP tool "
        "call, so the gateway scan is not sufficient on its own)")
    assert '"forbidden_metaprogramming"' in text


#: The Library arm (07-30 audit): a migrate spawn's `patch.lean` is
#: assembled into a Library file and built by `lake`, and Library decls
#: are cited across problems — the widest blast radius of all, and it was
#: missing from the original enumeration.
@pytest.mark.parametrize("path,fn", [
    (LIB_EXECUTE, "_default_fill_decl"),   # per-decl fill: agent patch.lean
    (LIB_GATE, "migrate_commit_gate"),     # assembled file, pre-commit
])
def test_librarian_scans_agent_lean(path, fn) -> None:
    src = _fn_source(path, fn)
    assert "metaprog.scan_metaprogramming(" in src, (
        f"{path.name}::{fn} accepts agent-written Lean that reaches a "
        "Library file and a `lake` build — it must scan first")


#: The elaboration paths that do NOT go through the gateway: they write a
#: throwaway `.lean` and shell out to `lake env lean`, which runs elab-time
#: code exactly as a gateway worker would. Missing these was the whole
#: point of enumerating entries rather than patching the obvious one.
@pytest.mark.parametrize("path,fn", [
    (LAKE_PROBE, "run_lean_source"),          # Library cleanup / dedup probes
    (DEDUPE, "_batch_provable_via_apply"),    # alias-provability batch
    (DEDUPE, "_batch_statement_defeq"),       # defeq batch
])
def test_direct_lake_probe_scans_its_source(path, fn) -> None:
    src = _fn_source(path, fn)
    assert "metaprog.scan_metaprogramming(" in src, (
        f"{path.name}::{fn} writes agent-derived text to a `.lean` and runs "
        "`lake env lean` on it, bypassing the gateway — it must scan first")


def test_lemma_lookup_fences_non_identifier_names() -> None:
    """A requested name is spliced verbatim into an elaborated `.lean`;
    the root fix is that only Lean identifiers get through, so a name
    carrying a newline + a command cannot become code."""
    from Tooling.knowledge import lemma_lookup

    assert lemma_lookup._is_lemma_name("Nat.add_comm")
    assert lemma_lookup._is_lemma_name("Finset.sum_congr'")
    assert lemma_lookup._is_lemma_name("Filter.Tendsto.comp!")
    # unicode names (Mathlib really has these)
    assert lemma_lookup._is_lemma_name("Ω_measurable")
    for bad in ["foo\nelab \"x\" : tactic => pure ()", "foo bar", "",
                "a" * 500, "foo\n#eval IO.println \"x\"", "x -- c"]:
        assert not lemma_lookup._is_lemma_name(bad), bad
    q = lemma_lookup._build_query(["Nat.add_comm", "z\n#eval 1"])
    assert "#eval 1" not in q
    assert "#check @Nat.add_comm" in q


def test_failure_reason_registered() -> None:
    assert "forbidden_metaprogramming" in REGISTRY
    # Same shape as `forbidden_lemma`: agent-origin, retryable, visible.
    assert REGISTRY["forbidden_metaprogramming"] == REGISTRY["forbidden_lemma"]


# ---------------------------------------------------------------------
# 2. Behaviour
# ---------------------------------------------------------------------

def test_token_sets_non_empty_and_carry_the_core_entries() -> None:
    assert metaprog.EXECUTION_TOKENS
    assert metaprog.ATTRIBUTE_TOKENS
    for core in ("elab", "elab_rules", "macro", "macro_rules", "initialize",
                 "unsafe", "run_cmd"):
        assert core in metaprog.EXECUTION_TOKENS, core
    assert "syntax" in metaprog.ANCHORED_TOKENS
    assert "debug.skipKernelTC" in metaprog.FORBIDDEN_OPTIONS


@pytest.mark.parametrize("src,token", [
    ('elab "foo" : tactic => pure ()', "elab"),
    ("elab_rules : tactic | `(tactic| f) => pure ()", "elab_rules"),
    ('macro "m" : term => `(1)', "macro"),
    ("macro_rules | `(x) => `(y)", "macro_rules"),
    ("by_elab do pure ()", "by_elab"),
    ('#eval IO.println "hi"', "#eval"),
    ("#eval! (pure () : IO Unit)", "#eval!"),
    ('run_cmd Lean.logInfo "x"', "run_cmd"),
    ("run_elab pure ()", "run_elab"),
    ("initialize foo : Unit ← pure ()", "initialize"),
    ("builtin_initialize bar : Unit ← pure ()", "builtin_initialize"),
    ("unsafe def main : IO Unit := pure ()", "unsafe"),
    ("declare_syntax_cat mycat", "declare_syntax_cat"),
    ('syntax "foo" : term', "syntax"),
    ('  scoped syntax "foo" : term', "syntax"),
    ("@[implemented_by f] def g : Nat := 0", "implemented_by"),
    ('@[extern "c_fn"] def g : Nat := 0', "extern"),
    ("@[command_elab myCmd] def e := 1", "command_elab"),
    ("@[builtin_term_elab foo] def e := 1", "builtin_term_elab"),
    ("@[tactic myTac] def e := 1", "tactic"),
    ("@[init myInit] def e := 1", "init"),
    ("set_option debug.skipKernelTC true in\ntheorem t : False := s",
     "set_option debug.skipKernelTC"),
])
def test_execution_entries_are_blocked(src, token) -> None:
    assert metaprog.scan_metaprogramming(src) == token


@pytest.mark.parametrize("src", [
    "theorem t : True := trivial",
    # The real committed-proof comment that forces comment stripping.
    "-- path which finishes by rfl. Verified in LSP (~64s elab).\n"
    "theorem t : True := trivial",
    "/-- Alias for `f` with a piecewise isometry syntax: -/\ndef g := 1",
    "/- elab macro #eval initialize -/\ntheorem t : True := trivial",
    "/- nested /- elab -/ still a comment -/\ntheorem t : True := trivial",
    "theorem elaborate_this_now : True := trivial",
    # Deliberately allowed constructs (see module docstring).
    "inductive C | a | b deriving DecidableEq",
    "deriving instance DecidableEq for C",
    'notation "⟦" x "⟧" => f x',
    "set_option maxHeartbeats 400000 in\ntheorem t : True := trivial",
    "set_option linter.style.longLine false",
    "@[simp] theorem t : True := trivial",
    "@[instance] theorem t : True := trivial",
    "@[reducible] def g := 1",
    # Aesop rule attributes carry `unsafe`/`tactic` as rule-builder
    # words — a declaration modifier, not a registration.
    "@[aesop unsafe 50%] theorem t : True := trivial",
    "@[aesop safe tactic] theorem t : True := trivial",
])
def test_legitimate_lean_is_not_blocked(src) -> None:
    assert metaprog.scan_metaprogramming(src) is None


@pytest.mark.parametrize("src,token", [
    # A `/-` inside a STRING is not a comment for Lean; if the stripper
    # treated it as one, everything after would silently escape.
    ('def s : String := "/-"\nelab "x" : tactic => pure ()\n'
     'def u : String := "-/"', "elab"),
    # A `"` inside a CHAR literal must not open a string that swallows
    # the following command.
    ('def c : Char := \'"\'\nmacro "m" : term => `(1)', "macro"),
    # A raw string's trailing backslash must not eat the closing quote.
    ('def r : String := r"a\\"\nmacro_rules | `(x) => `(y)', "macro_rules"),
])
def test_lexical_bypasses_stay_closed(src, token) -> None:
    assert metaprog.scan_metaprogramming(src) == token


def test_strip_preserves_length_and_line_structure() -> None:
    src = "theorem t : True := trivial -- elab here\ndef g := 1\n"
    out = metaprog.strip_lean_comments(src)
    assert len(out) == len(src)
    assert out.count("\n") == src.count("\n")
    assert "elab" not in out


def test_block_message_first_line_is_self_contained() -> None:
    """`agent/context.py::_digest_failure` keeps only the first line of
    failure_detail for the Context.md summary — it has to name both the
    offending token and the verdict on its own."""
    first = metaprog.blocked_detail("elab", where="patch.lean").splitlines()[0]
    assert "elab" in first and "patch.lean" in first
    assert "not permitted" in first
    # And the full text must point at the right road, not just refuse.
    assert "theorem" in metaprog.METAPROG_HINT


# ---------------------------------------------------------------------
# 3. Corpus — the false-positive investigation, frozen
# ---------------------------------------------------------------------

def test_existing_lean_corpus_is_clean() -> None:
    """Zero hits over every committed proof and Library file.

    Every `.lean` under `Library/` and `Problems/`, not just the
    `proofs/` dirs of nested-layout problems: the original
    `Problems/*/*/proofs` glob silently skipped flat-layout problems
    (`Problems/sylvester_gallai/proofs`, 5 dirs / ~900 files) and the
    user-owned `Root.lean` / `Defs.lean`, which the gateway scans too
    (07-30 audit).

    `Asterism/GatewayRpc.lean` is excluded on purpose: it is the
    FRAMEWORK's own Lean RPC plugin (`builtin_initialize` by design), it
    is never agent text, and it reaches Lean through lake's module graph
    rather than through any scanned path.
    """
    roots = [ROOT / "Library", ROOT / "Problems"]
    files = [f for r in roots if r.is_dir() for f in r.rglob("*.lean")]
    if not files:
        pytest.skip("no Lean corpus in this checkout")
    hits = [(str(f.relative_to(ROOT)), tok) for f in files
            if (tok := metaprog.scan_metaprogramming(
                f.read_text(encoding="utf-8", errors="replace")))]
    assert hits == [], (
        f"metaprogramming gate fires on {len(hits)} legitimate file(s) — "
        f"either the corpus grew a real entry or a token is too broad: "
        f"{hits[:5]}")


def test_framework_rpc_plugin_would_trip_the_gate() -> None:
    """Counter-pin for the exclusion above: the plugin really does carry
    an entry, so the exemption is load-bearing rather than cosmetic — if
    it ever stops tripping, the exclusion should go."""
    plugin = ROOT / "Asterism" / "GatewayRpc.lean"
    if not plugin.is_file():
        pytest.skip("framework Lean plugin not in this checkout")
    assert metaprog.scan_metaprogramming(
        plugin.read_text(encoding="utf-8")) is not None


def test_scanner_is_referenced_from_failure_modes_doc() -> None:
    doc = (ROOT / "docs" / "failure_modes.md").read_text(encoding="utf-8")
    assert re.search(r"^\|\s*`forbidden_metaprogramming`", doc, re.MULTILINE)
    assert "metaprog.py" in doc
