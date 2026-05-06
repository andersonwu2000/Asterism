import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_inner_sq_bound
import Problems.proj_nonexpansive.proofs.L_norm_le_of_inner_sq
import Problems.proj_nonexpansive.proofs.L_variational_ineq

namespace Problems.proj_nonexpansive

theorem s1 : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
  {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
  ∀ {P : X → X}, IsMetricProjector K P →
  ∀ x y, ‖P x - P y‖ ≤ ‖x - y‖  := by
  intro X _ _ K hK hConv hNe P hP x y
  have hvar : ∀ z : X, ∀ w ∈ K, @inner ℝ _ _ (P z - z) (w - P z) ≥ 0 :=
    variational_ineq hK hConv hNe hP
  have hinner : ‖P x - P y‖ ^ 2 ≤ @inner ℝ _ _ (x - y) (P x - P y) :=
    inner_sq_bound hP hvar x y
  exact norm_le_of_inner_sq hinner

end Problems.proj_nonexpansive
