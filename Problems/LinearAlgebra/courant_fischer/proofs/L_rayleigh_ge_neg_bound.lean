import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- rayleigh_ge_neg_bound: Rayleigh quotient ≥ -C via Cauchy-Schwarz + operator bound.
-- Cauchy-Schwarz gives ⟪Tx,x⟫ ≥ -‖Tx‖·‖x‖; the operator bound hC gives ‖Tx‖ ≤ C·‖x‖;
-- combining yields ⟪Tx,x⟫ ≥ -C·‖x‖², and dividing by ‖x‖² > 0 closes the goal.
theorem rayleigh_ge_neg_bound
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    (T : E →ₗ[ℝ] E) (C : ℝ) (hC : ∀ x : E, ‖T x‖ ≤ C * ‖x‖)
    (x : E) (hx : x ≠ 0) :
    -C ≤ @inner ℝ E _ (T x) x / ‖x‖ ^ 2 := by
  have hx_norm : (0 : ℝ) < ‖x‖ := norm_pos_iff.mpr hx
  have hpos : (0 : ℝ) < ‖x‖ ^ 2 := by positivity
  have hcs : |@inner ℝ E _ (T x) x| ≤ ‖T x‖ * ‖x‖ := abs_real_inner_le_norm (T x) x
  have hC' := hC x
  have hinner_lb : -C * ‖x‖ ^ 2 ≤ @inner ℝ E _ (T x) x := by
    nlinarith [neg_abs_le (@inner ℝ E _ (T x) x), norm_nonneg x]
  exact (le_div_iff₀ hpos).mpr hinner_lb

end Problems.LinearAlgebra.courant_fischer
