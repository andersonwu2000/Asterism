"""Kernel-certified disproof gate (owner design, 2026-08-25).

A goal flips to `disproved` (hard terminal; dedupe #112a blocks every
future same-shape proposal) ONLY through this gate. History: the
`-- decline: unprovable` directive flipped it on the agent's bare
say-so — ox-alpha condemned the TRUE `kelly_core` after four failed
attempts, no counterexample anywhere, and the poisoned dedupe then
aborted the correct decomposition road for the rest of the run
(sylvester_gallai, 2026-08-24). claude-era agents never abused the
directive (27/27 historical disproved were genuine), so the hole
shipped unnoticed until a new model's behavior distribution found it.

The owner's shape — no modes, no second file, no exit ceremony:
  * the agent that believes the statement false REWRITES patch.lean
    to prove the negation, marks the leading block
    `-- decline: disprove`, and submits;
  * changed its mind mid-way? rewrite back, drop the marker, submit
    normally — nothing to undo, nobody to tell;
  * the gate certifies the negation relationship IN THE KERNEL — no
    type printing, no string comparison:

        example : False :=
          absurd <original stub constant>
            (by first
              | exact <claim>
              | (push_neg; exact <claim>))

    `absurd : a → ¬a → b` unifies the claim's type against the
    NEGATION of the original constant's type — that unification IS the
    defeq check, and the `push_neg` arm admits the natural pushed
    forms (owner call: with the three classical axioms whitelisted,
    propositional pushing is fair game). The probe is a throwaway
    elaboration: the original constant's `sorry` proof is used only
    for its TYPE and nothing from the probe is ever committed.
  * the claim itself must be sorry-free and axiom-clean (the same
    `axiom_gate` every proved goal passes).

Fail any of it and the reply is a TEACHING message that hands the
agent the framework-known negation and the `return_to_nl` way out —
never a judgment.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..state import assemble

#: The renamed claim declaration inside the probe unit — the rename
#: lets it coexist with the imported original constant of the same slug.
_CLAIM_SUFFIX = "_disproof_claim"

#: Probe filename inside attempts_dir. A `.lean` there is snapshotted
#: into `dead_attempts.artifacts` by `collect_artifacts`, so a
#: successful disproof's certified unit is preserved with the death row.
PROBE_FILENAME = "_disproof.lean"


@dataclass
class DisproofVerdict:
    ok: bool
    #: teaching / certification detail for the pipeline result.
    detail: str
    #: non-empty when the PROBE could not be judged at all — the axiom
    #: gate answered with an infra reason (a gateway 5xx, a transport
    #: death). The caller must abort on THIS reason instead of teaching
    #: the agent: nothing about the submission was learned, and
    #: `agent_declined` would burn a goal attempt for a machine fault
    #: (owner ruling 2026-09-06).
    infra_reason: str = ""


BRICK_SUFFIX = "_disproof"


def _rename_claim_decl(patch_text: str, slug: str,
                       claim_slug: "str | None" = None,
                       suffix: str = _CLAIM_SUFFIX) -> "str | None":
    """Rename the patch's claim head to `<slug>_disproof_claim` so it
    can coexist with the imported original. The head the pipeline
    actually seeds is the per-attempt strategy token (`theorem s<id>`,
    backward's locked signature) — NEVER the goal slug, which is why
    the goal-slug-only lookup certified zero real submissions between
    2026-08-25 and 2026-08-27 (flagship: 0 disproved all-time; local:
    last disproved the night BEFORE the gate shipped). `claim_slug` is
    that owned head; the bare `slug` head stays accepted as the belt
    (synthetic probes, future flat paths). None when neither head is
    declared (nothing to certify)."""
    for head in dict.fromkeys(h for h in (claim_slug, slug) if h):
        pat = re.compile(
            rf"^((?:@\[[^\]]*\]\s*)?(?:theorem|lemma))(\s+)"
            rf"{re.escape(head)}\b",
            re.MULTILINE)
        if pat.search(patch_text):
            return pat.sub(rf"\g<1>\g<2>{slug}{suffix}",
                           patch_text, count=1)
    return None


def brick_text(patch_text: str, slug: str,
               claim_slug: "str | None" = None) -> "str | None":
    """The certified negation as a brick: the claim under the head
    `<slug>_disproof`, the `-- decline:` directive dropped, no probe
    bridge. None when the patch declares no claim head."""
    renamed = _rename_claim_decl(patch_text, slug, claim_slug=claim_slug,
                                 suffix=BRICK_SUFFIX)
    if renamed is None:
        return None
    lines = [ln for ln in renamed.splitlines()
             if not ln.lstrip().startswith("-- decline:")]
    return "\n".join(lines).rstrip("\n") + "\n"


def persist_disproof_brick(conn, *, workspace: Path, attempts_dir: Path,
                           patch_text: str, goal, problem: str,
                           claim_slug: "str | None",
                           axiom_whitelist: "list[str]") -> int:
    """Land the certified negation as a proved brick `<slug>_disproof`
    through the ordinary Forward commit (name gate, proof_store, axiom
    gate with olean, goal row, proved transition) — owner ruling
    2026-08-30: `ReturnToParent(refuted)` and a refuted root's `Ingest`
    point at THIS node, so the refutation stays kernel-linked to the
    claim instead of living in a hand-minted `¬claim` nobody checked.
    Returns the brick's goal id; raises on a landing failure (name
    collision, axiom gate) — the caller records it, the certification
    itself stands."""
    from . import forward as _forward
    slug = str(goal["slug"])
    text = brick_text(patch_text, slug, claim_slug=claim_slug)
    if text is None:
        raise ValueError(f"no claim head to land for {slug}")
    brick_slug = f"{slug}{BRICK_SUFFIX}"
    src = attempts_dir / f"new_{brick_slug}.lean"
    src.write_text(text, encoding="utf-8")
    out = _forward.commit_forward_lemma(
        conn, problem=problem, workspace=workspace, attempts_dir=attempts_dir,
        metadata=_forward.ForwardMetadata(slug=brick_slug, sorry_free=True,
                                          kind="theorem"),
        whitelist=list(axiom_whitelist), source_filename=src.name)
    return int(out.goal_id)


def disproof_brick_for(conn, goal_id: int) -> "int | None":
    """The gate-born brick of a goal: `<slug>_disproof`, proved, same
    problem. None when the goal was never refuted through the gate."""
    g = conn.execute("SELECT problem, slug FROM goals WHERE id = ?",
                     (int(goal_id),)).fetchone()
    if g is None:
        return None
    row = conn.execute(
        "SELECT id FROM goals WHERE problem = ? AND slug = ?"
        " AND status = 'proved' AND origin = 'forward'",
        (g["problem"], f"{g['slug']}{BRICK_SUFFIX}")).fetchone()
    return int(row["id"]) if row is not None else None


def refuted_goal_for(conn, brick_id: int) -> "int | None":
    """Inverse: the `disproved` goal a `<slug>_disproof` brick refutes.
    The pair is machine-derived — only the gate flips a goal to
    `disproved` and only the gate mints under that name — so a proved
    brick without a disproved partner is a brick, not a refutation."""
    b = conn.execute("SELECT problem, slug, status, origin FROM goals"
                     " WHERE id = ?", (int(brick_id),)).fetchone()
    if b is None or not str(b["slug"]).endswith(BRICK_SUFFIX):
        return None
    if str(b["status"]) != "proved" or str(b["origin"]) != "forward":
        return None
    row = conn.execute(
        "SELECT id FROM goals WHERE problem = ? AND slug = ?"
        " AND status = 'disproved'",
        (b["problem"], str(b["slug"])[:-len(BRICK_SUFFIX)])).fetchone()
    return int(row["id"]) if row is not None else None


def _stub_module(goal_lean_path: str) -> str:
    """`Problems/<p>/proofs/L_<slug>.lean` → dotted module name."""
    return goal_lean_path.replace("/", ".").removesuffix(".lean")


def build_probe(patch_text: str, *, slug: str,
                goal_lean_path: str,
                claim_slug: "str | None" = None) -> "str | None":
    """The probe unit: the renamed claim + the absurd bridge, with the
    original stub module imported for its constant. The claim head may
    be the attempt's own `s<id>` token (`claim_slug`) or the bare goal
    slug; either renames to `<slug>_disproof_claim`, so the bridge and
    the fq name downstream never change. None when the patch declares
    neither head (nothing to certify)."""
    renamed = _rename_claim_decl(patch_text, slug, claim_slug=claim_slug)
    if renamed is None:
        return None
    stub_import = f"import {_stub_module(goal_lean_path)}"
    # After the last import line (the seed always carries at least
    # `import Mathlib`).
    lines = renamed.splitlines()
    last_import = max((i for i, ln in enumerate(lines)
                       if ln.startswith("import ")), default=-1)
    lines.insert(last_import + 1, stub_import)
    claim = f"{slug}{_CLAIM_SUFFIX}"
    probe = (
        f"\n-- kernel certification: the claim's type IS the negation of\n"
        f"-- the original goal — defeq via `exact`, or its pushed form\n"
        f"-- (`push Not` is current mathlib; `push_neg` the older\n"
        f"-- spelling — both arms so either vintage certifies).\n"
        f"example : False :=\n"
        f"  absurd {slug}\n"
        f"    (by first\n"
        f"      | exact {claim}\n"
        f"      | (push Not; exact {claim})\n"
        f"      | (push_neg; exact {claim}))\n")
    # Before the closing `end <namespace>` when present, else appended.
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("end "):
            lines.insert(i, probe)
            break
    else:
        lines.append(probe)
    return "\n".join(lines) + "\n"


def teaching(locked_signature: "str | None", why: str) -> str:
    """The gate's refusal — hands the agent the framework-known
    negation (owner-approved wording shape, 2026-08-25) and the way
    out. Never a judgment on the mathematics. The negation shows the
    TYPE alone: the locked signature arrives as a full declaration
    (`theorem s3497 : ∀ …`) and wrapping THAT in `¬ (…)` hands the
    agent an un-Lean target it cannot possibly state (three decline
    loops on mathd_algebra_433, 2026-08-27)."""
    neg = "the negation of the goal's locked signature"
    if locked_signature:
        m = re.match(r"^\s*(?:@\[[^\]]*\]\s*)?(?:theorem|lemma)\s+\S+\s*(.*)$",
                     locked_signature.strip(), re.S)
        rest = (m.group(1) if m else locked_signature).strip()
        if rest.startswith(":"):
            neg = f"¬ ({rest[1:].strip()})"
        elif rest:
            # binder-style head: dropping the binders would drop the
            # quantifiers, so describe rather than misquote
            neg = (f"the negation of `{rest}` (with its binders "
                   f"universally quantified)")
    return (
        f"disproof not certified: {why}. The goal's negation is: {neg} — "
        f"rewrite patch.lean so your declaration proves exactly that "
        f"(keep the `-- decline: disprove` marker; do the push_neg work "
        f"inside the proof body, or state the pushed form and the gate's "
        f"push_neg arm will match it). If you cannot prove the negation "
        f"either, the statement may be true after all — submit "
        f"`-- decline: return_to_nl` and say what you learned."
    )


def run_disproof_gate(*, workspace: Path, attempts_dir: Path,
                      patch_text: str, slug: str, goal_lean_path: str,
                      locked_signature: "str | None",
                      axiom_whitelist: "list[str]",
                      problem: str,
                      claim_slug: "str | None" = None) -> DisproofVerdict:
    """Certify a `-- decline: disprove` submission. ok=True detail
    carries the certification line; ok=False detail carries teaching.
    `claim_slug` = the declaration head the attempt actually owns (the
    `s<id>` strategy token backward locked); the goal `slug` head stays
    accepted as the belt."""
    from . import _axiom
    probe_text = build_probe(patch_text, slug=slug,
                             goal_lean_path=goal_lean_path,
                             claim_slug=claim_slug)
    if probe_text is None:
        owned = claim_slug or slug
        return DisproofVerdict(False, teaching(
            locked_signature,
            f"patch.lean declares no `theorem {owned}` head to certify "
            f"— keep your locked `theorem {owned} : …` declaration and "
            f"prove the negation under that head"))
    probe_path = attempts_dir / PROBE_FILENAME
    probe_path.write_text(probe_text, encoding="utf-8")
    fq_claim = f"Problems.{problem}.{slug}{_CLAIM_SUFFIX}"
    gate = _axiom.axiom_gate(
        probe_path, fq_name=fq_claim, whitelist=axiom_whitelist,
        workspace=workspace, attempts_dir=attempts_dir,
        write_olean=False)
    if not gate.ok:
        from ..state import failures as _failures
        reason = str(gate.failure_reason or "")
        if _failures.is_infra(reason):
            # The gate never got to ask the kernel anything — see
            # `infra_reason`. Its own third arm exists for exactly this
            # (08-12), and folding it into teaching here undid that.
            return DisproofVerdict(
                False, f"the probe unit could not be judged ({reason}: "
                       f"{(gate.detail or '')[:400]})", reason)
        return DisproofVerdict(False, teaching(
            locked_signature,
            f"the probe unit did not certify "
            f"({gate.failure_reason}: {(gate.detail or '')[:400]})"))
    return DisproofVerdict(True, (
        f"kernel-verified disproof: {fq_claim} proves the negation of "
        f"the goal (absurd-bridge probe compiled sorry-free and "
        f"axiom-clean; unit preserved as {PROBE_FILENAME})"))


# The one statement DECL_HEAD source, shared with the rest of the
# pipeline (unused today beyond the rename regex above, imported so a
# future head-shape change breaks THIS module's tests too).
_ = assemble.DECL_HEAD_RE
