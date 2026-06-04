import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_continuous_on_f_three
import Problems.Minif2f.amc12b_2021_p21.proofs.L_deriv_f_neg_three

namespace Problems.Minif2f.amc12b_2021_p21

-- Decompose `StrictAntiOn f (Ioi 3)` via `strictAntiOn_of_deriv_neg` on the convex set
-- `Ioi 3 = convex_Ioi 3`. The two side-conditions are strictly simpler analytic facts:
-- h_cont — `ContinuousOn f (Ioi 3)` (a `ContinuousOn.sub` of two rpow factors); and
-- h_deriv — pointwise negativity of `deriv f` on `interior (Ioi 3) = Ioi 3` (single-variable
-- analytic inequality).  Each is one step below the parent monotonicity statement.
theorem s9751 :
    StrictAntiOn (fun t : ℝ => t ^ (2 : ℝ) ^ Real.sqrt 2 - Real.sqrt 2 ^ (2 : ℝ) ^ t)
      (Set.Ioi 3)  := by
  have h_cont := continuous_on_f_three
  have h_deriv := deriv_f_neg_three
  exact strictAntiOn_of_deriv_neg (convex_Ioi 3) h_cont h_deriv

end Problems.Minif2f.amc12b_2021_p21
