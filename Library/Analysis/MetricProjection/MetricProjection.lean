import Mathlib.Analysis.InnerProductSpace.Projection.Minimal
import Mathlib.Data.Real.StarOrdered

/-!
# Nonexpansiveness of the metric projection onto a convex set

Given a real inner product space `X` and a convex subset `K`, a *metric projector* onto `K` is a
map `P : X → X` sending each point to a closest point of `K`. This file proves that any such `P`
is non-expansive: `‖P x - P y‖ ≤ ‖x - y‖` for all `x y : X`.

The proof goes through the classical variational characterization of the projection: a point
`p ∈ K` minimizing `‖x - ·‖` over a convex `K` satisfies `⟪x - p, y - p⟫_ℝ ≤ 0` for every `y ∈ K`.
Applying this at both `x` and `y` and combining the two resulting inequalities yields
`‖P x - P y‖ ^ 2 ≤ ⟪x - y, P x - P y⟫_ℝ`, from which the Cauchy–Schwarz inequality gives
non-expansiveness.

## Main definitions

* `is_metric_projector`: `P` is a metric projector onto `K` if every image `P x` lies in `K` and
  realizes the minimal distance from `x` to `K`.

## Main statements

* `proj_nonexpansive_of_metric_projector`: **Non-expansive metric projection** — if `K` is convex
  and `P` is a metric projector onto `K`, then `P` is non-expansive.

## Implementation notes

The variational inequality and its algebraic consequences are extracted as standalone lemmas
(`norm_min_eq_iinf`, `real_inner_le_zero_of_norm_min`, `norm_sub_sq_le_inner_of_variational_pair`,
`norm_le_norm_of_sq_le_real_inner`) so each proof step is independently reusable.
-/

open scoped InnerProductSpace

namespace Library.Analysis.MetricProjection.MetricProjection

-- `MetricProjection` repeats in the enclosing namespace path (frozen for this stage); silence it.
set_option linter.dupNamespace false in
/-- `P` is a metric projector onto `K` if every image `P x` lies in `K` and realizes the minimal
distance from `x` to `K`, i.e. `‖x - P x‖ ≤ ‖x - y‖` for every `y ∈ K`. No convexity or closedness
of `K` is assumed here; those hypotheses are supplied by the theorems that use this predicate. -/
def is_metric_projector {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (K : Set X) (P : X → X) : Prop :=
  ∀ x, P x ∈ K ∧ ∀ y ∈ K, ‖x - P x‖ ≤ ‖x - y‖

-- `MetricProjection` repeats in the enclosing namespace path (frozen for this stage); silence it.
set_option linter.dupNamespace false in
/-- If `⟪x - a, b - a⟫_ℝ ≤ 0` and `⟪y - b, a - b⟫_ℝ ≤ 0`, then
`‖a - b‖ ^ 2 ≤ ⟪x - y, a - b⟫_ℝ`. This combines the two one-sided variational inequalities
satisfied by a pair of metric projections into the quadratic bound used to prove
non-expansiveness. -/
theorem norm_sub_sq_le_inner_of_variational_pair {X} [NormedAddCommGroup X]
    [InnerProductSpace ℝ X] {x y a b : X}
    (h1 : ⟪x - a, b - a⟫_ℝ ≤ 0) (h2 : ⟪y - b, a - b⟫_ℝ ≤ 0) :
    ‖a - b‖ ^ 2 ≤ ⟪x - y, a - b⟫_ℝ := by
  have hexp : ⟪x - y, a - b⟫_ℝ
      = ⟪x - a, a - b⟫_ℝ - ⟪y - b, a - b⟫_ℝ + ⟪a - b, a - b⟫_ℝ := by
    have key : x - y = (x - a) - (y - b) + (a - b) := by abel
    rw [key, inner_add_left, inner_sub_left]
  have hself : ⟪a - b, a - b⟫_ℝ = ‖a - b‖ ^ 2 := real_inner_self_eq_norm_sq _
  have hb1 : (0 : ℝ) ≤ ⟪x - a, a - b⟫_ℝ := by
    have : ⟪x - a, b - a⟫_ℝ = -⟪x - a, a - b⟫_ℝ := by
      rw [show b - a = -(a - b) by abel, inner_neg_right]
    linarith [h1, this]
  have hb2 : ⟪y - b, a - b⟫_ℝ ≤ 0 := h2
  rw [hexp, hself] at *
  linarith

-- `MetricProjection` repeats in the enclosing namespace path (frozen for this stage); silence it.
set_option linter.dupNamespace false in
/-- If `‖a‖ ^ 2 ≤ ⟪b, a⟫_ℝ` then `‖a‖ ≤ ‖b‖`. Proved via Cauchy–Schwarz
(`⟪b, a⟫_ℝ ≤ ‖b‖ * ‖a‖`), which combines with the hypothesis to cancel a factor of `‖a‖`. -/
theorem norm_le_norm_of_sq_le_real_inner {X : Type*} [NormedAddCommGroup X]
    [InnerProductSpace ℝ X] {a b : X} (h : ‖a‖ ^ 2 ≤ ⟪b, a⟫_ℝ) : ‖a‖ ≤ ‖b‖ := by
  have hcs : ⟪b, a⟫_ℝ ≤ ‖b‖ * ‖a‖ := real_inner_le_norm b a
  have h2 : ‖a‖ ^ 2 ≤ ‖b‖ * ‖a‖ := le_trans h hcs
  nlinarith [norm_nonneg a, norm_nonneg b, h2]

-- `MetricProjection` repeats in the enclosing namespace path (frozen for this stage); silence it.
set_option linter.dupNamespace false in
/-- A point `p ∈ K` minimizing `‖x - ·‖` over `K` realizes the infimum `⨅ w : ↥K, ‖x - ↑w‖`. -/
theorem norm_min_eq_iinf {X : Type*} [NormedAddCommGroup X]
    [InnerProductSpace ℝ X] {K : Set X} {x p : X} (hp : p ∈ K)
    (hmin : ∀ y ∈ K, ‖x - p‖ ≤ ‖x - y‖) :
    ‖x - p‖ = ⨅ w : ↥K, ‖x - ↑w‖ := by
  have hne : Nonempty ↥K := ⟨⟨p, hp⟩⟩
  refine le_antisymm (le_ciInf fun w ↦ hmin w.1 w.2) ?_
  have hbdd : BddBelow (Set.range fun w : ↥K ↦ ‖x - (w : X)‖) :=
    ⟨0, by rintro _ ⟨w, rfl⟩; exact norm_nonneg _⟩
  exact ciInf_le hbdd ⟨p, hp⟩

-- `MetricProjection` repeats in the enclosing namespace path (frozen for this stage); silence it.
set_option linter.dupNamespace false in
/-- **Variational inequality**: if `K` is convex and `p ∈ K` minimizes `‖x - ·‖` over `K`, then
`⟪x - p, y - p⟫_ℝ ≤ 0` for every `y ∈ K`. -/
theorem real_inner_le_zero_of_norm_min {X : Type*} [NormedAddCommGroup X]
    [InnerProductSpace ℝ X] {K : Set X} (hK : Convex ℝ K) {x p : X} (hp : p ∈ K)
    (hmin : ∀ y ∈ K, ‖x - p‖ ≤ ‖x - y‖) :
    ∀ y ∈ K, ⟪x - p, y - p⟫_ℝ ≤ 0 := by
  have h1 : ‖x - p‖ = ⨅ w : ↥K, ‖x - ↑w‖ := norm_min_eq_iinf hp hmin
  exact (norm_eq_iInf_iff_real_inner_le_zero hK hp).mp h1

-- `MetricProjection` repeats in the enclosing namespace path (frozen for this stage); silence it.
set_option linter.dupNamespace false in
/-- **Non-expansive metric projection**: if `K` is convex and `P` is a metric projector onto `K`,
then `‖P x - P y‖ ≤ ‖x - y‖` for all `x y`. -/
theorem proj_nonexpansive_of_metric_projector {X : Type*} [NormedAddCommGroup X]
    [InnerProductSpace ℝ X] {K : Set X} {P : X → X} (hK : Convex ℝ K)
    (hP : is_metric_projector K P) : ∀ x y, ‖P x - P y‖ ≤ ‖x - y‖ := by
  intro x y
  have h1 := real_inner_le_zero_of_norm_min hK (hP x).1 (hP x).2 (P y) (hP y).1
  have h2 := real_inner_le_zero_of_norm_min hK (hP y).1 (hP y).2 (P x) (hP x).1
  have hsq := norm_sub_sq_le_inner_of_variational_pair h1 h2
  exact norm_le_norm_of_sq_le_real_inner hsq

end Library.Analysis.MetricProjection.MetricProjection
