import Mathlib
namespace Problems.proj_nonexpansive

-- norm_le_of_sq_le_inner: Cauchy-Schwarz + cancellation: ‖a‖^2 ≤ ⟨b,a⟩ implies ‖a‖ ≤ ‖b‖
-- Uses real_inner_le_norm for ⟨b,a⟩ ≤ ‖b‖·‖a‖, then cancels ‖a‖ from both sides.
theorem norm_le_of_sq_le_inner
    {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (a b : X) (h : ‖a‖ ^ 2 ≤ inner ℝ b a) :
    ‖a‖ ≤ ‖b‖ := by
  have hcs : inner ℝ b a ≤ ‖b‖ * ‖a‖ := real_inner_le_norm b a
  have h2 : ‖a‖ ^ 2 ≤ ‖b‖ * ‖a‖ := h.trans hcs
  have ha : 0 ≤ ‖a‖ := norm_nonneg a
  rcases ha.eq_or_lt with ha0 | ha0
  · linarith [norm_nonneg b]
  · rw [sq] at h2
    exact le_of_mul_le_mul_right h2 ha0

end Problems.proj_nonexpansive
