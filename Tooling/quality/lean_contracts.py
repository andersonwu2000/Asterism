"""Framework⇄Lean interface contracts — executable, toolchain-triggered
(task #12).

Every unit test stubs Lean, so the contracts between the framework and the
real toolchain (probe output parsing, assembled text actually elaborating,
alias forms actually compiling) had exactly one regression detector: a live
daemon run burning agent budget. The classic blast radius is a Lean/mathlib
bump — `#print axioms` wording, the `hint` 🎉 marker, diagnostic shapes.

Design: each contract is a PLAIN FUNCTION over a warm gateway (one throwaway
file + one `verify_file`), so the same implementation serves two consumers:
  * the daemon — `check_on_startup` runs right after the gateway is ready,
    ONLY when the toolchain fingerprint (lean-toolchain + lake-manifest
    hash) changed since the last recorded pass; a red contract refuses
    startup (rc=2) rather than running the fleet against a broken
    interface. `ASTERISM_SKIP_LEAN_CONTRACTS=1` is the emergency override.
  * pytest — `real_lake`-marked wrappers (tests/test_lean_contracts.py)
    call the same functions for on-demand local runs.
The discipline "run the contract suite before touching the toolchain" is
thereby a mechanism: the toolchain cannot change without the suite running
once (user call, 2026-07-04 — discipline was judged not reliable enough).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

_STAMP_REL = Path(".asterism") / "lean_contracts_ok.json"

# Probe files live under Problems/ so the gateway resolves the lake package
# root the same way it does for real proof files.
_PROBE_DIR_REL = Path(".asterism") / "lean_contract_probes"


def toolchain_fingerprint(workspace: Path) -> str:
    """Hash of the files that pin the Lean world: `lean-toolchain` (compiler)
    + `lake-manifest.json` (mathlib + deps revs). Missing files hash as
    empty — a broken checkout still yields a stable fingerprint."""
    h = hashlib.sha256()
    for rel in ("lean-toolchain", "lake-manifest.json"):
        try:
            h.update((workspace / rel).read_bytes())
        except OSError:
            h.update(b"<absent>")
        h.update(b"\x00")
    return h.hexdigest()


def _read_stamp(workspace: Path) -> "str | None":
    try:
        data = json.loads((workspace / _STAMP_REL).read_text(
            encoding="utf-8"))
        return data.get("fingerprint")
    except (OSError, ValueError):
        return None


def _write_stamp(workspace: Path, fingerprint: str,
                 results: "list[tuple[str, bool, str]]") -> None:
    path = workspace / _STAMP_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "fingerprint": fingerprint,
        "passed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "contracts": [{"name": n, "ok": ok} for n, ok, _ in results],
    }, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------
# The contracts. Each returns (ok, detail). All single-file probes on the
# warm gateway — self-contained, no cross-module olean choreography.
# ---------------------------------------------------------------------

def _verify(workspace: Path, name: str, content: str, *,
            axioms_for: "str | None" = None,
            decl_info: bool = False) -> dict:
    from ..lsp import lifecycle as gateway_lifecycle
    d = workspace / _PROBE_DIR_REL
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{name}.lean"
    f.write_text(content, encoding="utf-8")
    try:
        return gateway_lifecycle.verify_file(
            f, write_olean=False, axioms_for=axioms_for,
            decl_info=decl_info, workspace=workspace)
    finally:
        try:
            f.unlink()
        except OSError:
            pass


def contract_clean_theorem_elaborates(workspace: Path) -> "tuple[bool, str]":
    """Baseline: a trivial theorem elaborates ok with zero errors — the
    gateway/verify plumbing itself works on this toolchain."""
    r = _verify(workspace, "c_clean",
                "import Mathlib\ntheorem c_clean : 1 + 1 = 2 := by norm_num\n")
    if r.get("error") or not r.get("ok"):
        return False, f"clean theorem failed to elaborate: {r}"
    return True, ""


def contract_axiom_probe_reports_whitelist(workspace: Path) -> "tuple[bool, str]":
    """`axioms_for` returns the classical axiom set for a classical proof —
    the `#print axioms`/collectAxioms output is still parseable and the
    names are the ones our whitelists pin."""
    r = _verify(workspace, "c_axioms",
                "import Mathlib\n"
                "theorem c_axioms (p : Prop) : p ∨ ¬p := Classical.em p\n",
                axioms_for="c_axioms")
    if r.get("error") or not r.get("ok"):
        return False, f"probe elaborate failed: {r}"
    axioms = set(r.get("axioms") or [])
    if not axioms or not axioms <= {"propext", "Classical.choice",
                                    "Quot.sound"}:
        return False, (f"unexpected axiom set {sorted(axioms)} — whitelist "
                       "name drift or probe parse break")
    return True, ""


def contract_axiom_probe_detects_sorry(workspace: Path) -> "tuple[bool, str]":
    """sorryAx must appear in the axiom set of a sorry proof — THE tripwire
    every proved-flip gate relies on."""
    r = _verify(workspace, "c_sorry",
                "import Mathlib\ntheorem c_sorry : True := by sorry\n",
                axioms_for="c_sorry")
    if r.get("error"):
        return False, f"probe infra error: {r['error']}"
    if "sorryAx" not in set(r.get("axioms") or []):
        return False, (f"sorryAx NOT reported for a sorry proof "
                       f"(got {r.get('axioms')}) — the soundness tripwire "
                       "is blind on this toolchain")
    return True, ""


def contract_assembled_text_elaborates(workspace: Path) -> "tuple[bool, str]":
    """assemble_for_commit's normalization on a bare statement (the exact
    transform every commit path runs) yields text the real toolchain
    accepts — imports/opens injection still produces valid Lean."""
    from ..state import assemble
    a = assemble.assemble_for_commit(
        "theorem c_asm : 2 * 3 = 6 := by norm_num\n",
        problem="__lean_contract__", workspace=workspace)
    if "import Mathlib" not in a.text:
        return False, "framework import injection missing"
    r = _verify(workspace, "c_asm", a.text)
    if r.get("error") or not r.get("ok"):
        return False, f"assembled text failed to elaborate: {r}"
    return True, ""


def contract_alias_forms_compile(workspace: Path) -> "tuple[bool, str]":
    """The two framework-generated alias shapes still compile: the tactic
    delegation (`apply <canonical> <;> assumption`, dedupe/revival) and the
    noncomputable def re-export (`noncomputable def b := @a`, promote/
    reconcile — BUG4's shape)."""
    r = _verify(workspace, "c_alias",
                "import Mathlib\n"
                "theorem c_canon (n : Nat) (h : 0 < n) : 0 < n + 1 := "
                "Nat.lt_succ_of_lt h\n"
                "theorem c_alias_t (n : Nat) (h : 0 < n) : 0 < n + 1 := by "
                "apply c_canon <;> assumption\n"
                "noncomputable def c_data : Real := Real.pi\n"
                "noncomputable def c_reexport := @c_data\n")
    if r.get("error") or not r.get("ok"):
        return False, f"alias forms failed to compile: {r}"
    return True, ""


def contract_hint_probe_emits_winner(workspace: Path) -> "tuple[bool, str]":
    """Builder Phase 1 parses `hint`'s `🎉` info lines for the winning
    tactic — the register_hint output format still matches our parser."""
    from ..pipeline import _parse_hint_winner
    r = _verify(workspace, "c_hint",
                "import Mathlib\ntheorem c_hint : 2 + 2 = 4 := by hint\n")
    if r.get("error"):
        return False, f"hint probe infra error: {r['error']}"
    msgs = "\n".join(d.get("message", "")
                     for d in (r.get("diagnostics") or []))
    winner = _parse_hint_winner(msgs)
    if not winner:
        return False, ("no parseable hint winner in diagnostics — "
                       "register_hint output format drifted "
                       f"(saw: {msgs[:300]!r})")
    return True, ""


def contract_decl_info_oracle(workspace: Path) -> "tuple[bool, str]":
    """The `Asterism.declInfo` RPC reports the per-decl facts the regex
    retirement rests on (task: declInfo syntactic oracle). Pins exactly the
    behaviors consumers consume:

      * a def under `noncomputable section` is `isNoncomputable` (env truth
        — the BUG4 / astslice-section-gap class);
      * `range` covers the docstring + `@[attr]` modifiers (slicing by range
        never orphans a docstring);
      * `ppSignature` incorporates section variables as ordinary binders;
      * a private decl is visible with its user-facing name normalized;
      * `open X in <decl>` is ONE command whose span covers the prefix
        (kind `Lean.Parser.Command.in`);
      * decls arrive in source order.

    NOTE: needs a `lean-asterism-server` binary built from a GatewayRpc.lean
    that registers `Asterism.declInfo` — a stale binary fails here with an
    RPC-method error, which is the correct loud signal to rebuild
    (`lake build lean-asterism-server`)."""
    r = _verify(workspace, "c_declinfo",
                "import Mathlib\n"
                "namespace CDi\n"
                "/-- thm doc -/\n"
                "@[simp] theorem c_di_thm : 1 + 1 = 2 := rfl\n"
                "private def c_di_priv : Nat := 3\n"
                "noncomputable section\n"
                "variable (n : Nat)\n"
                # Body must be GENUINELY noncomputable (Real.pi): Lean tags
                # `noncomputableExt` only for decls that actually fail to
                # compile — a compilable def under `noncomputable section`
                # is compiled and NOT tagged (verified live 2026-07-04).
                # That is exactly the right reconstruction semantics: the
                # modifier is re-emitted iff the decl needs it.
                "def c_di_data : Real := n + Real.pi\n"
                "end\n"
                "open Nat in\n"
                "theorem c_di_open : 2 = 2 := rfl\n"
                "end CDi\n",
                decl_info=True)
    if r.get("error") or not r.get("ok"):
        return False, f"probe elaborate failed: {r}"
    if r.get("decl_info_error") or not r.get("decl_info"):
        return False, (f"declInfo RPC unavailable/failed: "
                       f"{r.get('decl_info_error')} — stale "
                       "lean-asterism-server binary? (rebuild: lake build "
                       "lean-asterism-server)")
    info = r["decl_info"]
    commands = info.get("commands") or []
    decls = info.get("decls") or []
    by_user = {d["userName"]: d for d in decls}
    data = by_user.get("CDi.c_di_data")
    if not data or not data.get("isNoncomputable"):
        return False, (f"noncomputable-section def not reported "
                       f"noncomputable: {data}")
    if "(n : ℕ)" not in (data.get("signature") or ""):
        return False, (f"section variable missing from signature: "
                       f"{data.get('signature')!r}")
    thm = by_user.get("CDi.c_di_thm")
    if not thm or not thm.get("docstring"):
        return False, f"docstring not reported: {thm}"
    if thm["range"]["startLine"] >= thm["selection"]["startLine"]:
        return False, (f"decl range does not cover docstring/attr lines: "
                       f"{thm['range']} vs selection {thm['selection']}")
    priv = by_user.get("CDi.c_di_priv")
    if not priv or not priv.get("isPrivate"):
        return False, f"private decl missing/unflagged: {priv}"
    opn = by_user.get("CDi.c_di_open")
    if not opn:
        return False, "open-in decl missing"
    opn_cmd = (commands[opn["cmdIdx"]]
               if opn["cmdIdx"] < len(commands) else None)
    if not opn_cmd or opn_cmd["kind"] != "Lean.Parser.Command.in":
        return False, (f"open-in composite not one command: {opn_cmd}")
    order = [d["userName"] for d in decls
             if d["userName"].startswith("CDi.c_di_")]
    if order != ["CDi.c_di_thm", "CDi.c_di_priv", "CDi.c_di_data",
                 "CDi.c_di_open"]:
        return False, f"decls not in source order: {order}"
    return True, ""


CONTRACTS = [
    ("clean_theorem_elaborates", contract_clean_theorem_elaborates),
    ("axiom_probe_reports_whitelist", contract_axiom_probe_reports_whitelist),
    ("axiom_probe_detects_sorry", contract_axiom_probe_detects_sorry),
    ("assembled_text_elaborates", contract_assembled_text_elaborates),
    ("alias_forms_compile", contract_alias_forms_compile),
    ("hint_probe_emits_winner", contract_hint_probe_emits_winner),
    ("decl_info_oracle", contract_decl_info_oracle),
]


def run_all(workspace: Path) -> "list[tuple[str, bool, str]]":
    """Run every contract against the (already warm) gateway; returns
    [(name, ok, detail)]."""
    out = []
    for name, fn in CONTRACTS:
        try:
            ok, detail = fn(workspace)
        except Exception as exc:  # noqa: BLE001 — a contract crashing IS a failure
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        print(f"[lean-contract] {name}: {'ok' if ok else 'FAIL — ' + detail}",
              flush=True)
        out.append((name, ok, detail))
    return out


def check_on_startup(workspace: Path) -> bool:
    """Daemon-startup hook (call AFTER the gateway is ready — contracts run
    on its warm slots). Returns True when the daemon may proceed:
      * fingerprint unchanged since last recorded pass → skip, True.
      * changed/missing → run the suite; pass → stamp + True; any FAIL →
        False (caller exits: don't run the fleet against a broken Lean
        interface). `ASTERISM_SKIP_LEAN_CONTRACTS=1` overrides to True."""
    if os.environ.get("ASTERISM_SKIP_LEAN_CONTRACTS") == "1":
        print("[lean-contract] skipped by ASTERISM_SKIP_LEAN_CONTRACTS=1",
              flush=True)
        return True
    fp = toolchain_fingerprint(workspace)
    if _read_stamp(workspace) == fp:
        return True
    print("[lean-contract] toolchain fingerprint changed (or no pass on "
          "record) — running the framework⇄Lean contract suite once",
          flush=True)
    results = run_all(workspace)
    failed = [n for n, ok, _ in results if not ok]
    if failed:
        print(f"[lean-contract] {len(failed)} contract(s) FAILED "
              f"({', '.join(failed)}) — the framework's Lean interface is "
              "broken on this toolchain; refusing to start. Fix the "
              "parser/toolchain or set ASTERISM_SKIP_LEAN_CONTRACTS=1 to "
              "override.", flush=True)
        return False
    _write_stamp(workspace, fp, results)
    print(f"[lean-contract] all {len(results)} contracts passed — "
          "fingerprint stamped", flush=True)
    return True
