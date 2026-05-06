import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- inner_nonpos_from_forall_le: if 2*c ≤ t*M for all t ∈ (0,1] then c ≤ 0
-- (specialised to c = ⟪x - Px, z - Px⟫ and M = ‖z - Px‖²; proved by sending t→0⁺)
-- entry_kind: Backward
theorem inner_nonpos_from_forall_le {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {P : X → X} (x z : X)
    (h : ∀ t : ℝ, 0 < t → t ≤ 1 →
      2 * @inner ℝ _ _ (x - P x) (z - P x) ≤ t * ‖z - P x‖ ^ 2) :
    @inner ℝ _ _ (x - P x) (z - P x) ≤ 0 := by sorry

end Problems.proj_nonexpansive
