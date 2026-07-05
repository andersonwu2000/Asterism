---
problem: Analysis.metric_projection
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
library: true
---

# Analysis.metric_projection — metric projection onto a closed convex set is non-expansive

## Statement

In a real inner-product space `X`, given a nonempty closed convex set `K`, a
map `P : X → X` is a *metric projector* onto `K` when for every `x`, `P x ∈ K`
and `‖x - P x‖ ≤ ‖x - y‖` for all `y ∈ K`. Prove that any metric projector
onto such a `K` is non-expansive: `‖P x - P y‖ ≤ ‖x - y‖` for all `x y`.

### Deliverables

Forward-build these (snake_case names); Backward-decompose the hard ones;
`MarkDeliverable` each; then `Ingest`:

- `is_metric_projector` — the defining predicate described above,
- `proj_nonexpansive_of_metric_projector` — the non-expansiveness theorem.

### Proof shape (classical Hilbert-space argument, three natural layers)

1. **Variational inequality**: from the minimisation property derive
   `Real.inner (x − P x) (y − P x) ≤ 0` for every `y ∈ K` (perturb along the
   segment toward `y` via `Convex.combo_mem`, expand with
   `norm_sub_pow_two_real`, divide by the parameter, take the limit).
2. **Monotonicity**: apply (1) at `x` with `y := P y'` and at `y'` with
   `y := P x`, add — get `‖P x − P y'‖² ≤ Real.inner (x − y') (P x − P y')`.
3. **Cauchy–Schwarz** (`real_inner_le_norm`) on (2) and desquare.

### Useful mathlib entry points

- `Mathlib.Analysis.InnerProductSpace.Basic` — `inner_sub_left/right`,
  `real_inner_self_eq_norm_sq`
- `real_inner_le_norm` — Cauchy–Schwarz
- `norm_sub_pow_two_real` / `norm_add_pow_two_real`
- `Convex.combo_mem` — convex-combination membership for the perturbation

ALWAYS search mathlib first (grep + loogle) — cite what exists, only build the
genuinely missing. Do NOT introduce axioms or `sorry`-bearing shortcuts.
