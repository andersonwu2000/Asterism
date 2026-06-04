-- Split into (A) support claim from divisibility and (B) generic product formula.
-- A: m ∣ 5*10! = 2^8·3^4·5^3·7 forces m.factorization.support ⊆ {2,3,5,7}.
-- B: For support ⊆ {2,3,5,7}, the generic factorization-product identity
--    (with m ≠ 0 derived internally from m ∣ 5*10!) gives the formula.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9797

namespace Problems.Minif2f.amc12a_2020_p21

def factorization_form_of_dvd_5_mul_10_fact := @Problems.Minif2f.amc12a_2020_p21.s9797

end Problems.Minif2f.amc12a_2020_p21
