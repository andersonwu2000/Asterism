import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_inner_sq_from_two_var_ineq

namespace Problems.proj_nonexpansive

theorem s3 : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {K : Set X} {P : X → X},
    IsMetricProjector K P →
    (∀ z : X, ∀ w ∈ K, @inner ℝ _ _ (P z - z) (w - P z) ≥ 0) →
    ∀ x y : X, ‖P x - P y‖ ^ 2 ≤ @inner ℝ _ _ (x - y) (P x - P y)  := by
  intro X _ _ K P hP hvar x y
  have hPx : P x ∈ K := (hP x).1
  have hPy : P y ∈ K := (hP y).1
  have h1 : @inner ℝ _ _ (P x - x) (P y - P x) ≥ 0 := hvar x (P y) hPy
  have h2 : @inner ℝ _ _ (P y - y) (P x - P y) ≥ 0 := hvar y (P x) hPx
  exact inner_sq_from_two_var_ineq (P x) (P y) x y h1 h2

end Problems.proj_nonexpansive
