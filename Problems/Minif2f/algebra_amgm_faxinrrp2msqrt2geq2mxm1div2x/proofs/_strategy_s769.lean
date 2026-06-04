import Mathlib
import Problems.Minif2f.algebra_amgm_faxinrrp2msqrt2geq2mxm1div2x.Defs
import Problems.Minif2f.algebra_amgm_faxinrrp2msqrt2geq2mxm1div2x.proofs.L_amgm_x_plus_inv_2x

namespace Problems.Minif2f.algebra_amgm_faxinrrp2msqrt2geq2mxm1div2x

-- Decomposes via the AM-GM-style lemma `x + 1/(2x) ≥ √2` for x > 0.
-- Parent goal `2 - √2 ≥ 2 - x - 1/(2x)` is a direct linarith consequence
-- after introducing `x` and the hypothesis `x > 0`.
theorem s769 : ∀ x > 0, 2 - Real.sqrt 2 ≥ 2 - x - 1 / (2 * x)  := by
  intro x hx
  have h_amgm : x + 1 / (2 * x) ≥ Real.sqrt 2 := amgm_x_plus_inv_2x x hx
  linarith

end Problems.Minif2f.algebra_amgm_faxinrrp2msqrt2geq2mxm1div2x
