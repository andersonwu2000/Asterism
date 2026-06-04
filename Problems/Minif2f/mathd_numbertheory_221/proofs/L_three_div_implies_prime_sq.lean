-- Decompose `card_divisors = 3 → x = p^2` via prime factorization.
-- Sub 1 (`three_div_implies_fact_eq_single`): `card_divisors = 3` forces
--   the factorization Finsupp to be `Finsupp.single p 2` for a prime `p`.
-- Sub 2 (`pow_two_of_fact_eq_single`): reconstruct `x = p^2` from that
--   factorization (uses `Nat.prod_factorization_pow_eq_self`).
import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs
import Problems.Minif2f.mathd_numbertheory_221.proofs._strategy_s9615

namespace Problems.Minif2f.mathd_numbertheory_221

def three_div_implies_prime_sq := @Problems.Minif2f.mathd_numbertheory_221.s9615

end Problems.Minif2f.mathd_numbertheory_221
