import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_norm_le_of_sq_le_inner
import Problems.proj_nonexpansive.proofs.L_norm_sq_le_inner_diff
import Problems.proj_nonexpansive.proofs.L_variational_ineq

namespace Problems.proj_nonexpansive

-- Three-layer Hilbert-space decomposition: variational inequality, combine
-- at x and y, then Cauchy-Schwarz finish.
-- `variational_ineq` derives the projector's variational inequality from
-- the minimisation property + convexity. `norm_sq_le_inner_diff` adds the
-- variational inequalities at x and y to obtain a norm-squared bound.
-- `norm_le_of_sq_le_inner` is the abstract Cauchy-Schwarz consequence
-- ‖a‖²≤⟨b,a⟩ ⟹ ‖a‖≤‖b‖, which closes the parent goal.
theorem s142 : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
  {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
  ∀ {P : X → X}, IsMetricProjector K P →
  ∀ x y, ‖P x - P y‖ ≤ ‖x - y‖  := by
  intro X _ _ K hK hConv hNe P hP x y
  have h_var : ∀ z : X, ∀ w ∈ K, 0 ≤ @inner ℝ X _ (P z - z) (w - P z) :=
    variational_ineq hK hConv hNe hP
  have h_norm_sq : ‖P x - P y‖^2 ≤ @inner ℝ X _ (x - y) (P x - P y) :=
    norm_sq_le_inner_diff hK hConv hNe hP h_var x y
  exact norm_le_of_sq_le_inner hK hConv hNe hP (P x - P y) (x - y) h_norm_sq

end Problems.proj_nonexpansive
