-- Differentiate `s ↦ s^(2^√2) - √2^(2^s)` at `t > 3` as the difference of
-- two `HasDerivAt` facts; combine via `HasDerivAt.sub`.
-- h_left  — derivative of the polynomial term `s ↦ s^(2^√2)`.
-- h_right — derivative of the exponential term `s ↦ √2^(2^s)`.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9794

namespace Problems.Minif2f.amc12b_2021_p21

def has_deriv_expr := @Problems.Minif2f.amc12b_2021_p21.s9794

end Problems.Minif2f.amc12b_2021_p21
