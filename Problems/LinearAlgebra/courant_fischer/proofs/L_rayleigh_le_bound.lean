import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- rayleigh_le_bound: Rayleigh quotient ⟪Tx,x⟫/‖x‖² ≤ C given operator bound ‖Tx‖ ≤ C‖x‖
-- Chain: inner ≤ |inner| ≤ ‖Tx‖·‖x‖ ≤ C·‖x‖², then divide by ‖x‖² > 0.
theorem rayleigh_le_bound
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    (T : E →ₗ[ℝ] E) (C : ℝ) (hC : ∀ x : E, ‖T x‖ ≤ C * ‖x‖)
    (x : E) (hx : x ≠ 0) :
    @inner ℝ E _ (T x) x / ‖x‖ ^ 2 ≤ C := by
  have hxnorm : 0 < ‖x‖ := norm_pos_iff.mpr hx
  have hxnorm2 : (0 : ℝ) < ‖x‖ ^ 2 := by positivity
  rw [div_le_iff₀ hxnorm2]
  calc @inner ℝ E _ (T x) x
      ≤ |@inner ℝ E _ (T x) x| := le_abs_self _
    _ ≤ ‖T x‖ * ‖x‖ := abs_real_inner_le_norm (T x) x
    _ ≤ C * ‖x‖ * ‖x‖ := by nlinarith [norm_nonneg x, hC x]
    _ = C * ‖x‖ ^ 2 := by ring

end Problems.LinearAlgebra.courant_fischer
