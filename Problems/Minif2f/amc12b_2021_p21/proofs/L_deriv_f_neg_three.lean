-- Reduce `interior (Ioi 3)` to `Ioi 3`, then split into two strictly simpler analytic facts:
-- h_hasderiv — `HasDerivAt F E(t) t` at every t > 3 (explicit derivative formula).
-- h_expr_neg — the explicit expression E(t) is negative for every t > 3.
-- Combine via `HasDerivAt.deriv` to rewrite `deriv F t = E(t)`, then close with h_expr_neg.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9774

namespace Problems.Minif2f.amc12b_2021_p21

def deriv_f_neg_three := @Problems.Minif2f.amc12b_2021_p21.s9774

end Problems.Minif2f.amc12b_2021_p21
