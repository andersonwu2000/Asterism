---
problem: proj_nonexpansive
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# proj_nonexpansive — metric projection onto closed convex set is non-expansive

## Statement
∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
  {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
  ∀ {P : X → X}, IsMetricProjector K P →
  ∀ x y, ‖P x - P y‖ ≤ ‖x - y‖

## Lemma hints
- `Mathlib.Analysis.InnerProductSpace.Basic` — inner product API (`inner`, `inner_sub_left`, `inner_sub_right`, `real_inner_self_eq_norm_sq`)
- `inner_le_nnorm_mul_nnorm` / `abs_inner_le_norm` — Cauchy-Schwarz for real inner product
- `Convex.combo_mem` / `Convex.add_smul_mem` — convex combination membership (for variational inequality derivation)
- `norm_sub_pow_two_real` / `norm_add_pow_two_real` — `‖x ± y‖² = ‖x‖² ± 2⟨x,y⟩ + ‖y‖²`
- `sq_le_sq'` / `pow_le_pow_iff_left` — squaring/desquaring for the final step

## Strategic notes
The classical Hilbert-space argument has three layers, each a natural sub-goal:

1. **Variational inequality** for the metric projector. From the minimisation
   property `‖x − P x‖ ≤ ‖x − y‖` for `y ∈ K`, derive
   `Real.inner (P x − x) (y − P x) ≥ 0` for every `y ∈ K`. Standard trick:
   substitute `y := (1−t)·(P x) + t·y` for small `t > 0`, expand `‖x − …‖²`,
   divide by `t`, take `t → 0⁺`. The convexity of `K` is needed exactly here.

2. **Apply variational at both x and y** with the OTHER projection as the
   test point: take `y = P (something else)`. Adding the two inequalities
   yields `‖P x − P y‖² ≤ Real.inner (x − y) (P x − P y)`.

3. **Cauchy-Schwarz + cancellation**. By Cauchy-Schwarz the right side is
   `≤ ‖x − y‖ · ‖P x − P y‖`. Divide both sides by `‖P x − P y‖`
   (handle the degenerate case `P x = P y` separately).

`P` is given as a hypothesis — no need to construct it. Don't reach for
`Submodule.orthogonalProjection`; that's for closed *subspaces* and gives
linearity which we don't have here. The work is purely the three-step
inner product manipulation above.
