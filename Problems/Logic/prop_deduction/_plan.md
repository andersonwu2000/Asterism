# Plan — Logic.prop_deduction

## State (2026-07-05, after batch 5f72b81f)
- Three deliverables landed AND marked (success): `prop_identity` (5079), `prop_weakening` (5077), `prop_soundness` (5078).
- **ANOMALY**: the `prop_deduction` Forward inject in batch 5f72b81f resolved as outcome=`proved`, but there is NO `L_prop_deduction.lean` in proofs/, NO `prop_deduction` node in TREE.md (counters stuck at 10 proved), and nothing in Library. Contrast: the previous batch's `prop_soundness` Forward inject resolved as `success` and genuinely landed. `proved` on an inject step most plausibly means the framework aliased the statement to an existing **proved twin** without dispatching a worker — the only fuzzy candidate is `prop_add_hyp` (`Γ ⊢ B → Γ ⊢ A.imp B`), which is strictly WEAKER than the deduction theorem (hypothesis context `Γ` vs `insert A Γ`). If that alias happened, it is a soundness-adjacent framework dedupe bug. Alternative hypothesis: proof landed then a post-hoc gate rolled it back and wiped file+node while the step outcome stayed `proved`. Could not distinguish from here (DB and git blocked in strategist sandbox).
- This batch: re-Injected the `prop_deduction` Forward brick (same calibrated recipe; brief now explicitly says "this is NOT prop_add_hyp, must land as `L_prop_deduction.lean`", and offers `prop_add_hyp` as a citation for the axiom / hyp-in-Γ cases, plus the `generalize hΔ : insert A Γ = Δ` contingency promoted into the main text).

## Next wake (when this batch resolves)
1. `L_prop_deduction.lean` exists on disk + node in tree → `MarkDeliverable prop_deduction`. That completes all four Manifest deliverables.
2. Re-wake after that mark → `Ingest` (never same batch as the mark).
3. **If the inject again resolves `proved` with NO artifact on disk** → the alias-to-proved-twin bug is confirmed. Do NOT loop a third identical inject. Escalate: `RequestUserAmend` (or equivalent user-facing surface) reporting the dedupe false-match between `prop_deduction` and `prop_add_hyp` — marking/Ingesting without the real theorem would be unsound. VERIFY on disk before every mark from now on.
4. If it fails with a real `why:` → read it; the math is certainly right (standard Hilbert deduction theorem, Manifest confirms the shape); most likely friction remains the induction motive over the compound index — the generalize formulation is already primary in the brief.

## Notes
- Standing directive (self-contained calculus, no mathlib hunt, fixed snake_case names, negation = `A.imp bot`, no axioms/sorry) still accurate — keep as-is.
- Lesson applied: an inject-step `outcome=proved` is NOT proof an artifact landed — always cross-check TREE.md counters + proofs/ dir before MarkDeliverable/Ingest.
- Defs.lean absent — fine, everything went through Forward bricks.
