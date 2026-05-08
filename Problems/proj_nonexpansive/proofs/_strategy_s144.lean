import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_minimization_norm_sq_at_combo
import Problems.proj_nonexpansive.proofs.L_post_division_arith

namespace Problems.proj_nonexpansive

-- Split the post-division bound into the geometric step (minimisation at the
-- convex combination yₜ = P z + t • (w - P z)) and the pure inner-product
-- algebra step (expand ‖a - t • b‖² and divide by t).
-- `minimization_norm_sq_at_combo` packages the K-convexity + IsMetricProjector
-- content; `post_division_arith` is the parent goal with the squared-norm
-- inequality as an extra hypothesis, leaving only inner-product manipulation.
theorem s144 :
    ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
      {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
      ∀ {P : X → X}, IsMetricProjector K P →
      ∀ z : X, ∀ w ∈ K, ∀ t : ℝ, 0 < t → t ≤ 1 →
      0 ≤ 2 * @inner ℝ X _ (P z - z) (w - P z) + t * ‖w - P z‖^2  := by
  intro X _ _ K hClosed hConv hNe P hP z w hw t ht htle
  have h1 : ‖z - P z‖^2 ≤ ‖(z - P z) - t • (w - P z)‖^2 :=
    minimization_norm_sq_at_combo hClosed hConv hNe hP z w hw t ht htle
  exact post_division_arith hClosed hConv hNe hP z w hw t ht htle h1

end Problems.proj_nonexpansive
