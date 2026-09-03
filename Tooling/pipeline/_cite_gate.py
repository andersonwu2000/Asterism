"""Shared citation-gate logic for Backward (decomp + leaf-bypass) and
Builder pipelines.

Extracted from `backward.py` 2026-05-22 — Builder had no citation gate,
so an agent that wrote `import Problems.<p>.proofs.L_<shelved_slug>`
into Builder's `patch.lean` would not be rejected at commit time; the
shelved wrapper's underlying strategy still elaborates (sorry surfaces
as warning, not error), the build "passes", and the sorry propagates
up through goal_lean → cascade until `root_integrity_gate` finally
catches it. By that time many spawn cycles are burnt.

Gate is per-patch: scan for `import Problems.<problem>.proofs.L_<slug>`
lines and classify each cited slug by goal status:
- `proved`: legitimate, pass through.
- `open` / `attempting` / `pending_strategist_review`: if the caller
  supports auto-linking (decomposition path), collect the goal_id so
  the caller can attach a `strategy_subgoals` row and have the new
  strategy wait until the cited goal proves; otherwise (leaf-bypass /
  Builder) reject.
- `shelved`: a PARK, the status dedupe does NOT block — "reopenable",
  whatever parked it (threshold, cascade, a wrong-context decline).
  Citability mirrors dedupe-blocking, so on the decomposition path a
  machine park is REVIVED: reopened to `open` and auto-linked, regaining
  a live path through the citing strategy's `strategy_subgoals`.
  (Pre-2026-06-13 these were rejected alongside `disproved`, which
  contradicted the contract and left cascade-shelved leaves uncitable
  forever — agent_feedback T8.) A PERSON's park is the exception, below.
  Leaf-bypass / Builder still reject (can't tolerate transitive sorry).
- `disproved`: HARD terminal — the disproof gate certified a
  counterexample, dedupe BLOCKS it, so does citation. The one status
  that is never citable.
- No goal for the slug: if `proofs/L_<slug>.lean` does NOT exist it's a
  typo / cross-problem ref → pass through (lake's "unknown identifier"
  catches it). If the file DOES exist it's an ORPHAN stub (sub-goal whose
  row never committed) → reject: lake imports it fine and its `sorry`
  only warns, so citing it would silently fake-prove the citer.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from ..state import db as _db

# `import Problems.<problem>.proofs.L_<slug>` line pattern, captures
# (problem, slug). Shared SoT (state.assemble) — the gateway's citation-
# submission mirror imports the same object (task #5 Step A).
from ..state.assemble import PROBLEM_IMPORT_RE as _PROBLEM_IMPORT_RE


def inject_missing_sibling_imports(
    conn: sqlite3.Connection, *, problem: str, patch_text: str,
    declared_slugs: set[str], workspace: Path,
) -> "tuple[str, list[str]]":
    """Single impl in `state.assemble.inject_sibling_imports` (task #5 Step
    B — one normalization rule for every commit path). Kept under the
    historical name/signature for existing call sites and tests;
    `workspace` was never used by the logic."""
    from ..state import assemble
    return assemble.inject_sibling_imports(
        conn, patch_text, problem=problem, declared_slugs=declared_slugs)


def _resolve_cite_dependencies(
    conn: sqlite3.Connection, *, problem: str, patch_text: str,
    declared_slugs: set[str], allow_auto_link: bool,
    workspace: Path,
) -> tuple[set[int], set[int], str | None]:
    """Scan `patch_text` for `import Problems.<problem>.proofs.L_<slug>`
    lines and classify each cited slug:

      * declared sub-goal (in this commit's `new_<slug>.lean` files) → skip
      * status='proved' goal → skip (legitimate citation)
      * status ∈ ('open', 'attempting', 'pending_strategist_review'):
        - if `allow_auto_link`: collect goal_id for caller to insert as
          a sibling sub-goal via `strategy_subgoals` (the safe parallel
          pattern — strategy waits in 'proposed' until cited goal proves
          via `strategies_ready_for_verify`'s all-subgoals-proved check)
        - else: reject (caller is a leaf-bypass / Builder that runs
          axiom probe at submit, can't tolerate transitive sorry from
          cited stub)
      * status='shelved' — soft terminal that dedupe does NOT block:
        - if `allow_auto_link`: collect goal_id in BOTH the auto-link set
          (links as a `strategy_subgoals` row) AND the revive set (caller
          reopens it to 'open' — the citing strategy gives it a fresh live
          path back to root, so it re-dispatches). Fixes cascade-shelved
          leaves being uncitable forever (agent_feedback T8).
        - else: reject (leaf-bypass / Builder can't tolerate transitive
          sorry; revival is a decomposition-path capability).
      * status = 'disproved' → always reject (never revived): a
        kernel-certified counterexample; the statement is false.
      * no goal for the slug:
        - file `proofs/L_<slug>.lean` absent → skip (typo / cross-problem;
          lake's "unknown identifier" catches it)
        - file present but no goal → ORPHAN stub → reject (citing it
          imports a sorry; re-declare as a `new_<slug>.lean` sub-goal)

    Returns (auto_link_goal_ids, revive_goal_ids, err). `revive` ⊆
    `auto_link`. Caller commits the strategy with the declared subgoals
    plus `auto_link` goals as additional `strategy_subgoals` rows, and
    reopens every `revive` goal (currently shelved) to 'open' first.
    On err non-None the strategy must abort (subgoals would be from a
    doomed dependency).
    """
    auto_link: set[int] = set()
    revive: set[int] = set()
    bad: list[tuple[str, str]] = []
    seen: set[str] = set()
    for m in _PROBLEM_IMPORT_RE.finditer(patch_text):
        if m.group(1) != problem:
            # Cross-problem node citation is NOT allowed — only same-problem
            # siblings, Library, and Mathlib are citable. Reject explicitly
            # (previously skipped, leaving lake to maybe build it).
            bad.append((f"Problems.{m.group(1)}.proofs.L_{m.group(2)}",
                        "cross-problem citation (not allowed)"))
            continue
        slug = m.group(2)
        if slug in seen:
            continue
        seen.add(slug)
        if slug in declared_slugs:
            continue
        # Classify the cited slug via the shared source-of-truth so this
        # gate and validate_file's pre-commit mirror never disagree (#8).
        #  - no goal + L_<slug>.lean on disk → ORPHAN STUB: a sub-goal whose
        #    row never committed (a Backward killed mid-placement, or a
        #    deleted decomposition) leaves a `:= by sorry` file. Lake imports
        #    it fine and the `sorry` only WARNS, so citing it silently
        #    fake-proves the citer — how P13's density_form_supp_lhs_slice put
        #    sorryAx into the root. Reject; re-declare as a `new_<slug>.lean`.
        #  - no goal + no file → typo / cross-problem ref → pass through
        #    (lake's "unknown identifier" catches it).
        gid, status, orphan = _db.classify_cited_slug(
            conn, problem=problem, slug=slug, workspace=workspace)
        if status is None:
            if orphan:
                bad.append((slug, "orphan — file on disk, no tracked goal"))
            continue
        if status == "proved":
            continue
        if status in ("open", "attempting",
                       "pending_strategist_review"):
            if allow_auto_link:
                auto_link.add(gid)
            else:
                bad.append((slug, status))
            continue
        if status == "shelved":
            # A PERSON's park is terminal (HID §3.2 appendix, ruling
            # 2026-09-02) and the difference decides the citation. The
            # machine's park is a WAIT: it carries a paired Inject, so
            # auto-linking makes the citing strategy queue behind
            # prereqs that are actually coming. A person's park promises
            # nothing to wait for — the same auto-link would hang this
            # strategy until someone happened to reopen the goal. Reject
            # instead, and say so: the stop does not propagate (the
            # citer may re-plan), it is simply not citable.
            if _db.is_human_parked(conn, gid):
                bad.append((slug, "parked by a person"))
                continue
            # Soft terminal — revivable. dedupe doesn't block it, so
            # neither does citation: auto-link on the decomp path; reject on
            # leaf-bypass/Builder (transitive sorry).
            if allow_auto_link:
                auto_link.add(gid)
                # Revive ONLY a cascade-shelved goal (lost its last live path)
                # — the agent_feedback T8 motivation. A ConfirmShelve-PARKED
                # goal is deliberately held pending its injected prereqs; the
                # auto_link makes the citing strategy WAIT for it (it proves
                # when the Strategist re-engages it via inject_batch_done), so
                # do NOT reopen it early — that would re-dispatch it before its
                # prereqs exist and re-fail/re-shelve in a mini-spin.
                if not _db.is_confirm_shelve_parked(conn, gid):
                    revive.add(gid)
            else:
                bad.append((slug, status))
            continue
        # 'disproved' — the one hard terminal a cite can reach, and it
        # is never revived by citation: the disproof gate certified a
        # counterexample, so the statement is false. (A wrong-context
        # decline lands in the `shelved` branch above since 2026-09-04:
        # its statement was never judged, only the decomposition that
        # minted it, so a citer in a DIFFERENT context may revive it.)
        bad.append((slug, status))
    if not bad:
        return auto_link, revive, None
    lines = [f"  - `{slug}` (status={status})" for slug, status in bad]
    human_note = (
        "\n\nA goal `parked by a person` was stopped BY HAND, and that "
        "stop is terminal: unlike the framework's own park it carries no "
        "promised follow-up work, so waiting on it would wait forever. "
        "Nothing else stops — only this citation is refused. Either build "
        "what you need yourself (declare it as your own "
        "`new_<slug>.lean` sub-goal stub, or route around it), or ask the "
        "person who parked it to reopen it."
        if any(status == "parked by a person" for _, status in bad) else ""
    )
    orphan_note = (
        "\n\nAn `orphan` cite is an `import` of a `proofs/L_<slug>.lean` "
        "that has NO tracked goal — a stale stub left by an interrupted or "
        "discarded decomposition. It is NOT a proved lemma (typically "
        "`:= by sorry`); citing it would silently import a sorry. Declare "
        "what you need as your own `new_<slug>.lean` sub-goal instead."
        if any("orphan" in status for _, status in bad) else ""
    )
    if allow_auto_link:
        # On the decomp path `bad` holds disproved (false) and
        # human-parked cites; machine parks are revived above.
        hint = (
            "\n\nThese goals cannot be cited: DISPROVED = the disproof "
            "gate certified a counterexample, so the statement is false. "
            "Re-declare what you actually need as your own "
            "`new_<slug>.lean` sub-goal stub (a corrected re-statement "
            "under your strategy), or pick a different decomposition angle."
        )
    else:
        # Leaf-bypass / Builder path: any non-proved cite is rejected
        # (immediate axiom probe can't tolerate transitive sorry). The
        # auto-link / revive mechanism is only available via Backward
        # decomp.
        hint = (
            "\n\nFix by declaring each as a sub-goal stub "
            "(`new_<slug>.lean := by sorry`), or restructure as a "
            "Backward decomposition — the decomp path auto-links open "
            "siblings and revives parked ones as `strategy_"
            "subgoals` so the strategy waits for them to prove. Leaf-"
            "bypass and Builder (no decomposition) can only cite "
            "already-proved siblings."
        )
    return auto_link, revive, (
        "Patch imports sibling goals that cannot be cited:\n"
        + "\n".join(lines) + hint + human_note + orphan_note
    )
