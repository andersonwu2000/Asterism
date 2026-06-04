import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_deriv_expr_neg
import Problems.Minif2f.amc12b_2021_p21.proofs.L_has_deriv_expr

namespace Problems.Minif2f.amc12b_2021_p21

-- Reduce `interior (Ioi 3)` to `Ioi 3`, then split into two strictly simpler analytic facts:
-- h_hasderiv — `HasDerivAt F E(t) t` at every t > 3 (explicit derivative formula).
-- h_expr_neg — the explicit expression E(t) is negative for every t > 3.
-- Combine via `HasDerivAt.deriv` to rewrite `deriv F t = E(t)`, then close with h_expr_neg.
theorem s9774 :
    ∀ t ∈ interior (Set.Ioi (3 : ℝ)),
      deriv (fun s : ℝ => s ^ (2 : ℝ) ^ Real.sqrt 2 - Real.sqrt 2 ^ (2 : ℝ) ^ s) t < 0  := by
  intro t ht
  rw [interior_Ioi] at ht
  have h_hasderiv : HasDerivAt
      (fun s : ℝ => s ^ (2 : ℝ) ^ Real.sqrt 2 - Real.sqrt 2 ^ (2 : ℝ) ^ s)
      ((2 : ℝ) ^ Real.sqrt 2 * t ^ ((2 : ℝ) ^ Real.sqrt 2 - 1)
        - Real.sqrt 2 ^ ((2 : ℝ) ^ t) * Real.log (Real.sqrt 2) *
          ((2 : ℝ) ^ t) * Real.log 2) t := has_deriv_expr t ht
  have h_expr_neg :
      (2 : ℝ) ^ Real.sqrt 2 * t ^ ((2 : ℝ) ^ Real.sqrt 2 - 1)
        - Real.sqrt 2 ^ ((2 : ℝ) ^ t) * Real.log (Real.sqrt 2) *
          ((2 : ℝ) ^ t) * Real.log 2 < 0 := deriv_expr_neg t ht
  rw [h_hasderiv.deriv]
  exact h_expr_neg

end Problems.Minif2f.amc12b_2021_p21
