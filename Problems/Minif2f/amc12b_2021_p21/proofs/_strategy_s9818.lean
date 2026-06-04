import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_deriv_g_neg_one_sqrt2
import Problems.Minif2f.amc12b_2021_p21.proofs.L_func_continuous_on_one_sqrt2

namespace Problems.Minif2f.amc12b_2021_p21

-- Decompose `StrictAntiOn g (Icc 1 √2)` via `strictAntiOn_of_deriv_neg` on the convex set
-- `Icc 1 √2 = convex_Icc 1 √2`. The two side-conditions are strictly simpler analytic facts:
-- `h_cont` — `ContinuousOn g (Icc 1 √2)` (a `ContinuousOn.sub` of an rpow times a constant
-- and a constant times a `log`); and `h_deriv` — pointwise negativity of `deriv g` on
-- `interior (Icc 1 √2) = Ioo 1 √2` (one-variable analytic inequality where the `−2^√2/t`
-- term dominates the small `2^t · log 2 · log √2` term throughout the interval).  Each is
-- one structural step below the parent monotonicity statement.
theorem s9818 :
    StrictAntiOn
      (fun t : ℝ => (2:ℝ)^t * Real.log (Real.sqrt 2)
            - (2:ℝ)^Real.sqrt 2 * Real.log t)
      (Set.Icc 1 (Real.sqrt 2))  := by
  have h_cont := func_continuous_on_one_sqrt2
  have h_deriv := deriv_g_neg_one_sqrt2
  exact strictAntiOn_of_deriv_neg (convex_Icc 1 (Real.sqrt 2)) h_cont h_deriv

end Problems.Minif2f.amc12b_2021_p21
