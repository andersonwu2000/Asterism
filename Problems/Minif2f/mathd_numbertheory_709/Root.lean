-- Decompose: the only n with 0<n, τ(2n)=28, τ(3n)=30 is n = 864.
-- Sub-goal `n_eq_864` does the integer/divisor-count work; we then substitute
-- and close τ(6·864)=35 by `native_decide` (kernel decision per LESSONS).
import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs._strategy_s9316

namespace Problems.Minif2f.mathd_numbertheory_709

def main := @Problems.Minif2f.mathd_numbertheory_709.s9316

end Problems.Minif2f.mathd_numbertheory_709
