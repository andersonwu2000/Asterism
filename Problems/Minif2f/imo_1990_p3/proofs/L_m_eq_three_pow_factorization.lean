-- Every prime factor of `m` is forced to be 3: Odd ⇒ no 2; hypothesis ⇒ no p≥5;
-- so the only prime in [3,5) divides m, hence m = 3 ^ v₃(m) by `prod_factorization_pow_eq_self`.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9730

namespace Problems.Minif2f.imo_1990_p3

def m_eq_three_pow_factorization := @Problems.Minif2f.imo_1990_p3.s9730

end Problems.Minif2f.imo_1990_p3
