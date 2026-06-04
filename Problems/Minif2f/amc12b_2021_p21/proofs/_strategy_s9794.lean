import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_has_deriv_exp_part
import Problems.Minif2f.amc12b_2021_p21.proofs.L_has_deriv_pow_part

namespace Problems.Minif2f.amc12b_2021_p21

-- Differentiate `s ↦ s^(2^√2) - √2^(2^s)` at `t > 3` as the difference of
-- two `HasDerivAt` facts; combine via `HasDerivAt.sub`.
-- h_left  — derivative of the polynomial term `s ↦ s^(2^√2)`.
-- h_right — derivative of the exponential term `s ↦ √2^(2^s)`.
theorem s9794 :
    ∀ t : ℝ, 3 < t → HasDerivAt
      (fun s : ℝ => s ^ (2 : ℝ) ^ Real.sqrt 2 - Real.sqrt 2 ^ (2 : ℝ) ^ s)
      ((2 : ℝ) ^ Real.sqrt 2 * t ^ ((2 : ℝ) ^ Real.sqrt 2 - 1)
        - Real.sqrt 2 ^ ((2 : ℝ) ^ t) * Real.log (Real.sqrt 2) *
          ((2 : ℝ) ^ t) * Real.log 2) t  := by
  intro t ht
  have h_left : HasDerivAt (fun s : ℝ => s ^ (2 : ℝ) ^ Real.sqrt 2)
      ((2 : ℝ) ^ Real.sqrt 2 * t ^ ((2 : ℝ) ^ Real.sqrt 2 - 1)) t :=
    has_deriv_pow_part t ht
  have h_right : HasDerivAt (fun s : ℝ => Real.sqrt 2 ^ (2 : ℝ) ^ s)
      (Real.sqrt 2 ^ ((2 : ℝ) ^ t) * Real.log (Real.sqrt 2) *
        ((2 : ℝ) ^ t) * Real.log 2) t :=
    has_deriv_exp_part t ht
  exact h_left.sub h_right
end Problems.Minif2f.amc12b_2021_p21
