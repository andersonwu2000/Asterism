import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_inner_le_mul_t
import Problems.proj_nonexpansive.proofs.L_inner_nonpos_from_forall_le

namespace Problems.proj_nonexpansive

-- Variational inequality via convex combination perturbation argument:
-- For small t>0, P x + t*(z - P x) ∈ K by convexity; minimality gives a norm bound;
-- expanding in t yields 2⟪x-Px, z-Px⟫ ≤ t*‖z-Px‖²; sending t→0 gives ≤ 0;
-- flipping sign via inner_neg_left yields the goal 0 ≤ ⟪Px-x, z-Px⟫.
theorem s14 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {K : Set X} (hconvex : Convex ℝ K) {P : X → X} (hP : IsMetricProjector K P)
    (x z : X) (hz : z ∈ K) : 0 ≤ @inner ℝ _ _ (P x - x) (z - P x) := by
  have h1 : ∀ t : ℝ, 0 < t → t ≤ 1 →
      2 * @inner ℝ _ _ (x - P x) (z - P x) ≤ t * ‖z - P x‖ ^ 2 :=
    inner_le_mul_t hconvex hP x z hz
  have h2 : @inner ℝ _ _ (x - P x) (z - P x) ≤ 0 :=
    inner_nonpos_from_forall_le h1
  have h3 : @inner ℝ _ _ (P x - x) (z - P x) =
      -@inner ℝ _ _ (x - P x) (z - P x) := by
    rw [show P x - x = -(x - P x) by ring, inner_neg_left]
  linarith

end Problems.proj_nonexpansive
