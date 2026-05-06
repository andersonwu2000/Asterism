import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- inner_le_mul_t: for any t ∈ (0,1], the minimality of P x and convexity of K imply
-- 2 * ⟪x - P x, z - P x⟫ ≤ t * ‖z - P x‖²  (by perturbing Px toward z, expanding ‖·‖²)
-- entry_kind: Backward
theorem inner_le_mul_t {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {K : Set X} (hconvex : Convex ℝ K) {P : X → X} (hP : IsMetricProjector K P)
    (x z : X) (hz : z ∈ K) :
    ∀ t : ℝ, 0 < t → t ≤ 1 →
    2 * @inner ℝ _ _ (x - P x) (z - P x) ≤ t * ‖z - P x‖ ^ 2 := by sorry

end Problems.proj_nonexpansive
