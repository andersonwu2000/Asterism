import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_concave_log_term
import Problems.Minif2f.amc12b_2021_p21.proofs.L_convex_exp_term

namespace Problems.Minif2f.amc12b_2021_p21

-- Concave − convex = concave: split g(z) = 2^√2·log z − 2^z·log √2.
-- Sub-goal 1: concavity of the log term (positive scalar × log, log strictly concave).
-- Sub-goal 2: convexity of the exponential term (positive scalar × 2^z, 2^z convex).
-- Combine via ConcaveOn.sub.
theorem s9822 :
    ConcaveOn ℝ (Set.Icc (Real.sqrt 2) 3)
      (fun z => (2:ℝ)^Real.sqrt 2 * Real.log z
              - (2:ℝ)^z * Real.log (Real.sqrt 2))  := by
  have h_log_concave := concave_log_term
  have h_exp_convex := convex_exp_term
  exact h_log_concave.sub h_exp_convex

end Problems.Minif2f.amc12b_2021_p21
