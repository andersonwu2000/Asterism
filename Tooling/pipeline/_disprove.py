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
          absurd @<original stub constant>
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
    The `@` is load-bearing and was missing until 2026-09-08 — see
    `_ABSURD_AT_WHY`.
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

#: Machine tag on every non-infra refusal this gate returns. The DB
#: cannot otherwise tell a disprove-road refusal from any other
#: `agent_declined` row, and the burn cap below has to count exactly
#: those. Leading, so it survives every downstream truncation.
REFUSAL_MARKER = "[disproof-gate refused]"

#: Refusals on the disprove road a goal may collect before it is parked
#: for the Strategist instead of re-spawned. 2026-09-08 post-mortem:
#: three union_closed goals (10948/10949/10952) each burned FIVE spawns
#: — 4-6 minutes apart, all night — against a probe that could not
#: accept any answer (see `_ABSURD_AT_WHY`). Once two independent
#: spawns have failed to state the negation the probe wants, the open
#: question is about the STATEMENT, and that is the Strategist's to
#: answer (Inject the missing lemma / ConfirmShelve / Reopen with a
#: directive) — not a third worker's to guess at.
PARK_AFTER_REFUSALS = 2


def _refusal(detail: str) -> str:
    """Tag a refusal so `refusal_count` can find it in the death row."""
    return f"{REFUSAL_MARKER} {detail}"


def refusal_count(conn, goal_id: int) -> int:
    """How many times this gate has already refused THIS goal — the
    tagged `dead_attempts` rows. Counts prior pipelines only: a
    terminal decline returns straight out of the retry loop, so the
    current attempt's row is not written until cascade."""
    # instr(), not LIKE: the marker is a literal, and a `_` or `%` ever
    # appearing in it would silently turn into a wildcard.
    row = conn.execute(
        "SELECT COUNT(*) FROM dead_attempts"
        " WHERE target_kind = 'Goal' AND target_id = ?"
        "   AND instr(COALESCE(failure_detail, ''), ?) > 0",
        (int(goal_id), REFUSAL_MARKER)).fetchone()
    return int(row[0]) if row else 0


def park_prefix(nth: int) -> str:
    """PREFIXED to the refusal that parks the goal, never appended: the
    reader is the Strategist, whose dossier digests each dead attempt
    down to its FIRST line (`_digest_failure`, 200 chars). A park reason
    at the tail is a park reason it never sees. Line one therefore says
    the whole verdict; the rest names the moves that are actually open
    (a gate message has to name an action its reader can take)."""
    return (
        f"[disproof-gate] parked for Strategist review: the kernel "
        f"disproof probe refused this goal {nth} times "
        f"(cap {PARK_AFTER_REFUSALS}) — the open question is the "
        f"STATEMENT, not the submission.\n\n"
        f"{nth} independent spawns could not state the negation this "
        f"probe accepts. The next move is yours: Inject what is "
        f"missing, ConfirmShelve, or Reopen with a directive — not "
        f"another worker at the same submission. The refusal that "
        f"ended the road follows.\n\n")


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


_ABSURD_AT_WHY = """\
Why the bridge writes `absurd @<slug>` and not `absurd <slug>`
(post-mortem 2026-09-08, union_closed g10948/g10949/g10952: eleven
spawns in eight hours, every one refused at the same column).

Scope: EVERY refusal this gate has ever recorded is this bug, and it
has certified nothing since it shipped on 2026-08-25 — 0 goals reached
`disproved` in that window. The other face of it is g10897 (09-05),
refused with `typeclass instance problem is stuck: DecidableEq ?m.7`
instead of a mismatch; same metavariable, one elaboration step earlier.
All three 09-08 submissions certify under `@`, on the three classical
axioms — the mathematics was right every time.

A BARE constant is elaborated with its leading implicit and
instance-implicit binders EAGERLY INSTANTIATED to metavariables:
`four_target_block_uniformity` does not have the type its file
declares, it has `∀ (C D : Finset (Finset ?α)) …` with `?α` open.
`absurd : a → ¬a → b` reads `a` off that, so the negation the probe
then demands is the negation of the INSTANTIATED body — a type with a
free metavariable in it (`∀ ⦃A B : Finset ?m.3⦄, …`), which no agent
can state, while the gate's own teaching message tells it to state the
closed `¬ (∀ {α} [DecidableEq α], …)`. The two can never meet, so
EVERY goal whose locked signature opens with an implicit or
instance-implicit binder was un-disprovable, and the agent could only
retry until the goal's attempts cap parked it.

`@` suppresses that insertion: the constant keeps its declared type,
binders and all, and the demanded negation is exactly the closed one
the message promises. Lean's defeq ignores binder ANNOTATION, so the
agent's `{α}` / `[inst]` spelling still unifies with the `@`-form, and
a negation of a DIFFERENT statement still fails to unify — the
soundness of the bridge is untouched.
"""


def build_probe(patch_text: str, *, slug: str,
                goal_lean_path: str,
                claim_slug: "str | None" = None) -> "str | None":
    """The probe unit: the renamed claim + the absurd bridge, with the
    original stub module imported for its constant. The claim head may
    be the attempt's own `s<id>` token (`claim_slug`) or the bare goal
    slug; either renames to `<slug>_disproof_claim`, so the bridge and
    the fq name downstream never change. None when the patch declares
    neither head (nothing to certify).

    The bridge negates `@<slug>`, never the bare constant — see
    `_ABSURD_AT_WHY` above for the eleven-spawn reason why."""
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
        f"-- `@` on the constant is LOAD-BEARING: see `_ABSURD_AT_WHY`.\n"
        f"example : False :=\n"
        f"  absurd @{slug}\n"
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


#: Lean's mismatch report, verbatim: the type the probe DEMANDED. It is
#: the one thing an agent can copy and state without guessing, and the
#: 400-char slice of `gate.detail` cut the message off two lines above
#: it — every one of the eleven refusals reached the agent ending mid
#: "has type", so it never once saw what the gate actually wanted.
_EXPECTED_TYPE_RE = re.compile(
    r"but is expected to have type\r?\n(?P<ty>(?:[ \t]+\S.*(?:\r?\n|$))+)")

#: Raw-error budget in the refusal, and how it is spent: a Lean type
#: mismatch puts the demanded type at the END, so a head-only slice
#: drops precisely the half that matters (that is how a 400-char cut
#: landed two lines above `but is expected to have type`, eleven times).
#: Head AND tail — the belt behind `expected_type`'s dedicated field,
#: for the failure shapes the regex does not know.
_RAW_HEAD_BUDGET = 800
_RAW_TAIL_BUDGET = 400
_EXPECTED_TYPE_BUDGET = 4000


def _clip(detail: "str | None") -> str:
    """Head + tail of a raw Lean error — never the head alone."""
    text = (detail or "").strip()
    if len(text) <= _RAW_HEAD_BUDGET + _RAW_TAIL_BUDGET:
        return text
    return (f"{text[:_RAW_HEAD_BUDGET]}\n…\n{text[-_RAW_TAIL_BUDGET:]}")


def expected_type(detail: "str | None") -> str:
    """The `but is expected to have type …` block of a Lean type
    mismatch, dedented, or "" when the failure was not a mismatch."""
    m = _EXPECTED_TYPE_RE.search(detail or "")
    if m is None:
        return ""
    block = m.group("ty").rstrip()
    lines = block.splitlines()
    pad = min((len(ln) - len(ln.lstrip()) for ln in lines if ln.strip()),
              default=0)
    out = "\n".join(ln[pad:] for ln in lines).strip()
    return out[:_EXPECTED_TYPE_BUDGET]


def teaching(locked_signature: "str | None", why: str,
             expected: str = "") -> str:
    """The gate's refusal — hands the agent the framework-known
    negation (owner-approved wording shape, 2026-08-25) and the way
    out. Never a judgment on the mathematics. The negation shows the
    TYPE alone: the locked signature arrives as a full declaration
    (`theorem s3497 : ∀ …`) and wrapping THAT in `¬ (…)` hands the
    agent an un-Lean target it cannot possibly state (three decline
    loops on mathd_algebra_433, 2026-08-27).

    `expected` is the probe's own demanded type, lifted verbatim out of
    the Lean error (`expected_type`). The rendered signature is a
    RE-STATEMENT of the goal; this is the elaborator's answer, so when
    the two disagree the agent has something it can copy."""
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
    verbatim = ""
    if expected:
        verbatim = (
            f" The probe's EXACT demanded type, as the elaborator "
            f"printed it — state this verbatim:\n```\n{expected}\n```\n")
    return (
        f"disproof not certified: {why}. The goal's negation is: {neg} — "
        f"rewrite patch.lean so your declaration proves exactly that "
        f"(keep the `-- decline: disprove` marker; do the push_neg work "
        f"inside the proof body, or state the pushed form and the gate's "
        f"push_neg arm will match it).{verbatim} The signature lock does "
        f"not apply "
        f"on this road — commit sends a disprove-marked patch here before "
        f"it ever compares signatures, so a `locked_signature` warning "
        f"from an editing tool is wrong about this turn; keep the "
        f"declaration HEAD and rewrite what follows the `:`. If you "
        f"cannot prove the negation "
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
        return DisproofVerdict(False, _refusal(teaching(
            locked_signature,
            f"patch.lean declares no `theorem {owned}` head to certify "
            f"— keep your locked `theorem {owned} : …` declaration and "
            f"prove the negation under that head")))
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
        return DisproofVerdict(False, _refusal(teaching(
            locked_signature,
            f"the probe unit did not certify "
            f"({gate.failure_reason}: {_clip(gate.detail)})",
            expected_type(gate.detail))))
    return DisproofVerdict(True, (
        f"kernel-verified disproof: {fq_claim} proves the negation of "
        f"the goal (absurd-bridge probe compiled sorry-free and "
        f"axiom-clean; unit preserved as {PROBE_FILENAME})"))


# The one statement DECL_HEAD source, shared with the rest of the
# pipeline (unused today beyond the rename regex above, imported so a
# future head-shape change breaks THIS module's tests too).
_ = assemble.DECL_HEAD_RE
