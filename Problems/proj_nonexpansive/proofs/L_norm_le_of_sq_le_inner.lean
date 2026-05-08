import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- norm_le_of_sq_le_inner: real Cauchy-Schwarz `⟨b,a⟩ ≤ ‖b‖·‖a‖` turns the
-- hypothesis `‖a‖² ≤ ⟨b,a⟩` into `‖a‖·‖a‖ ≤ ‖b‖·‖a‖`; cancel `‖a‖` (or use
-- `‖a‖ = 0` in the degenerate case) to conclude `‖a‖ ≤ ‖b‖`.
theorem norm_le_of_sq_le_inner : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
  {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
  ∀ {P : X → X}, IsMetricProjector K P →
  ∀ a b : X, ‖a‖^2 ≤ @inner ℝ X _ b a → ‖a‖ ≤ ‖b‖ := by
  intro X _ _ K _ _ _ P _ a b h
  have hCS : @inner ℝ X _ b a ≤ ‖b‖ * ‖a‖ := real_inner_le_norm b a
  have h2 : ‖a‖ * ‖a‖ ≤ ‖b‖ * ‖a‖ := by
    have := h.trans hCS
    simpa [sq] using this
  rcases eq_or_lt_of_le (norm_nonneg a) with ha | ha
  · rw [← ha]; exact norm_nonneg b
  · exact le_of_mul_le_mul_right h2 ha

end Problems.proj_nonexpansive
