-- Decompose by extracting two coefficient identities from the polynomial-equality hypothesis.
-- h_c : c = 7  (from h₁ 0, since -35 = -5*c)
-- h_ab : a * b = 12  (from comparing leading coefficients of h₁)
-- Combine: a*b - 3*c = 12 - 21 = -9 by linarith.
import Mathlib
import Problems.Minif2f.mathd_algebra_140.Defs
import Problems.Minif2f.mathd_algebra_140.proofs._strategy_s638

namespace Problems.Minif2f.mathd_algebra_140

def main := @Problems.Minif2f.mathd_algebra_140.s638

end Problems.Minif2f.mathd_algebra_140
