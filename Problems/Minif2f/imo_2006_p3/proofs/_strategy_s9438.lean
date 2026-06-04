import Mathlib
import Problems.Minif2f.imo_2006_p3.Defs
import Problems.Minif2f.imo_2006_p3.proofs.L_bound_factored_form_squared

namespace Problems.Minif2f.imo_2006_p3

-- Square-then-sqrt bridge: reduce the radical inequality to a pure polynomial
-- form `512 * L² ≤ 81 * R^4`, then take square roots using `(9*√2/32)² = 81/512`.
theorem s9438 : ∀ (a b c : ℝ),
    (a - b) * (b - c) * (a - c) * (a + b + c)
      ≤ 9 * Real.sqrt 2 / 32 * (a ^ 2 + b ^ 2 + c ^ 2) ^ 2  := by
  intro a b c
  have h_sq : 512 * ((a - b) * (b - c) * (a - c) * (a + b + c))^2
              ≤ 81 * (a^2 + b^2 + c^2)^4 := bound_factored_form_squared a b c
  set L : ℝ := (a - b) * (b - c) * (a - c) * (a + b + c) with hL_def
  set R : ℝ := (a^2 + b^2 + c^2)^2 with hR_def
  have hR_nn : 0 ≤ R := sq_nonneg _
  have h2nn : (0:ℝ) ≤ Real.sqrt 2 := Real.sqrt_nonneg 2
  have hM_nn : 0 ≤ 9 * Real.sqrt 2 / 32 * R := by positivity
  have h2sq : (Real.sqrt 2)^2 = 2 := Real.sq_sqrt (by norm_num : (0:ℝ) ≤ 2)
  have hbound_sq : L^2 ≤ (9 * Real.sqrt 2 / 32 * R)^2 := by
    have hRHS : (9 * Real.sqrt 2 / 32 * R)^2 = 81 / 512 * R^2 := by
      have : (9 * Real.sqrt 2 / 32)^2 = 81 / 512 := by
        rw [div_pow, mul_pow]
        rw [h2sq]
        norm_num
      calc (9 * Real.sqrt 2 / 32 * R)^2
          = (9 * Real.sqrt 2 / 32)^2 * R^2 := by ring
        _ = 81 / 512 * R^2 := by rw [this]
    rw [hRHS]
    have : R^2 = (a^2 + b^2 + c^2)^4 := by simp [hR_def]; ring
    rw [this]
    linarith [h_sq]
  have habs := abs_le_of_sq_le_sq' hbound_sq hM_nn
  linarith [habs.2]

end Problems.Minif2f.imo_2006_p3
