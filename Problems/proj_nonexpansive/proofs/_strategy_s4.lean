import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_inner_le_zero_of_t_bound
import Problems.proj_nonexpansive.proofs.L_inner_sq_bound_2

namespace Problems.proj_nonexpansive

theorem s4 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (a b : X) (h : ∀ t : ℝ, 0 < t → t ≤ 1 → ‖a‖ ≤ ‖a - t • b‖) :
    @inner ℝ _ _ a b ≤ 0  := by
  have h1 : ∀ t : ℝ, 0 < t → t ≤ 1 → 2 * t * @inner ℝ _ _ a b ≤ t ^ 2 * ‖b‖ ^ 2 :=
    fun t ht ht1 => inner_sq_bound_2 a b t ht (h t ht ht1)
  exact inner_le_zero_of_t_bound (@inner ℝ _ _ a b) (‖b‖ ^ 2) (sq_nonneg _) h1

end Problems.proj_nonexpansive
