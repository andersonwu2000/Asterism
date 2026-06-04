import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_func1_continuous_on
import Problems.Minif2f.amc12b_2021_p21.proofs.L_func2_continuous_on

namespace Problems.Minif2f.amc12b_2021_p21

-- Split f(x) = x^(2^√2) - √2^(2^x) into its two continuous parts and apply ContinuousOn.sub.
-- h1 handles continuity of x ↦ x^(2^√2) on [2,4] (positive base, constant exponent).
-- h2 handles continuity of x ↦ √2^(2^x) on [2,4] (positive constant base, continuous exponent).
theorem s9718 :
    ContinuousOn (fun x : ℝ => x^((2:ℝ)^Real.sqrt 2) - Real.sqrt 2 ^ ((2:ℝ)^x))
      (Set.Icc (2:ℝ) 4)  := by
  have h1 := func1_continuous_on
  have h2 := func2_continuous_on
  exact h1.sub h2

end Problems.Minif2f.amc12b_2021_p21
