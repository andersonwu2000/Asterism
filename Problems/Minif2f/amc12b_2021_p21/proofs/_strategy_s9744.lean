import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_continuous_on_f_three
import Problems.Minif2f.amc12b_2021_p21.proofs.L_deriv_f_neg_three

namespace Problems.Minif2f.amc12b_2021_p21

-- Standard "negative derivative ⇒ strict anti" decomposition via `strictAntiOn_of_deriv_neg`.
-- The convex set is `Set.Ioi 3` (use `convex_Ioi`); we discharge the two side conditions:
-- h_cont — continuity of F on (3, ∞); h_deriv — pointwise negativity of `deriv F` on the
-- interior (which equals `Set.Ioi 3` itself). Each side is strictly simpler than the parent
-- StrictAntiOn claim: continuity is a pure `ContinuousOn.sub` of two rpow facts, and the
-- derivative-negativity is a pointwise analytic inequality on a single variable.
theorem s9744 :
    StrictAntiOn (fun t : ℝ => t ^ (2 : ℝ) ^ Real.sqrt 2 - Real.sqrt 2 ^ (2 : ℝ) ^ t)
      (Set.Ioi 3)  := by
  have h_cont := continuous_on_f_three
  have h_deriv := deriv_f_neg_three
  exact strictAntiOn_of_deriv_neg (convex_Ioi 3) h_cont h_deriv

end Problems.Minif2f.amc12b_2021_p21
