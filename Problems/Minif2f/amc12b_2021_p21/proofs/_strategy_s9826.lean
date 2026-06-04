import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_deriv_g_expr_neg_one_sqrt2
import Problems.Minif2f.amc12b_2021_p21.proofs.L_has_deriv_g_one_sqrt2

namespace Problems.Minif2f.amc12b_2021_p21
-- Reduce `interior (Icc 1 √2) = Ioo 1 √2`, then split deriv negativity into two simpler facts:
-- h_hasderiv — `HasDerivAt g E(t) t` at every t ∈ Ioo 1 √2 with the explicit derivative
--   `E(t) = 2^t·log 2·log √2 − 2^√2·t⁻¹` (sum/product rule on `2^s` and `log s`).
-- h_expr_neg — that explicit expression `E(t)` is negative on the same interval (one-variable
--   analytic inequality where the `−2^√2/t` term dominates the small `2^t·log 2·log √2`).
-- Combine via `HasDerivAt.deriv` to rewrite `deriv g t = E(t)`, then close with `h_expr_neg`.
theorem s9826 :
    ∀ t ∈ interior (Set.Icc (1:ℝ) (Real.sqrt 2)),
      deriv (fun t : ℝ => (2:ℝ)^t * Real.log (Real.sqrt 2)
              - (2:ℝ)^Real.sqrt 2 * Real.log t) t < 0  := by
  intro t ht
  rw [interior_Icc] at ht
  have h_hasderiv := has_deriv_g_one_sqrt2 t ht
  have h_expr_neg := deriv_g_expr_neg_one_sqrt2 t ht
  rw [h_hasderiv.deriv]
  exact h_expr_neg

end Problems.Minif2f.amc12b_2021_p21
