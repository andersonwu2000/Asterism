import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_inner_sq_le_inner_of_proj
import Problems.proj_nonexpansive.proofs.L_norm_le_of_sq_le_inner
import Problems.proj_nonexpansive.proofs.L_projector_variational_ineq

namespace Problems.proj_nonexpansive

-- Decompose into: (1) variational inequality for metric projectors, (2) inner-product squared bound
-- via two applications of the VI, (3) norm bound from ‖v‖² ≤ inner(u,v) via Cauchy-Schwarz + division.
-- Sub-goals: projector_variational_ineq (Backward), inner_sq_le_inner_of_proj (Backward),
-- norm_le_of_sq_le_inner (Builder). Main theorem: intro, have h1 from sub-goal 2, exact sub-goal 3.
theorem s12 : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
  {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
  ∀ {P : X → X}, IsMetricProjector K P →
  ∀ x y, ‖P x - P y‖ ≤ ‖x - y‖  := by
  intro X _ _ K _ hconvex _ P hP x y
  have h1 : ‖P x - P y‖ ^ 2 ≤ @inner ℝ _ _ (x - y) (P x - P y) :=
    inner_sq_le_inner_of_proj hconvex hP x y
  exact norm_le_of_sq_le_inner (x - y) (P x - P y) h1

end Problems.proj_nonexpansive
