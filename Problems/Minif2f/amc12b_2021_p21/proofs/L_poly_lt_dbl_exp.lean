-- Sandwich via 4^z: z^3 < 4^z (polynomial-vs-exponential at z>4) and
-- 4^z ≤ √2^(2^z) (since √2^(4z) = 4^z and 4z ≤ 2^z for z ≥ 4).
-- Splits the polynomial-vs-double-exponential gap into a polynomial-vs-
-- single-exponential bound and a clean exponent comparison.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9770

namespace Problems.Minif2f.amc12b_2021_p21

def poly_lt_dbl_exp := @Problems.Minif2f.amc12b_2021_p21.s9770

end Problems.Minif2f.amc12b_2021_p21
