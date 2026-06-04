import Mathlib
import Problems.Minif2f.amc12a_2008_p4.Defs
import Problems.Minif2f.amc12a_2008_p4.proofs.L_prod_telescope_general

namespace Problems.Minif2f.amc12a_2008_p4

-- Generalize the closed form: the product over `Icc 1 n` of `(4k+4)/(4k)` equals `n+1`.
-- Sub-goal `prod_telescope_general` proves this for all `n : ℕ` (parametric induction
-- on `n` is strictly simpler than the fixed numeric case); specializing at `n = 501`
-- and using `linarith` (treating `∏…` as opaque) discharges `(501:ℝ) + 1 = 502`.
theorem s9279 : (∏ k ∈ Finset.Icc (1 : ℕ) 501, ((4 : ℝ) * k + 4) / (4 * k)) = 502  := by
  have h := prod_telescope_general 501
  linarith [h]

end Problems.Minif2f.amc12a_2008_p4
