-- Two-step decomp:
-- A. `decompose_n_two_three_coprime`: pure-arithmetic split — any n>0 factors as 2^a * 3^b * r
--    with Coprime r 6 (take a := n.factorization 2, b := n.factorization 3, r := remaining).
-- B. `tau_coprime_part_eq_one`: τ(2n)=28 ∧ τ(3n)=30 forces that 6-coprime part r = 1
--    (the τ analysis: (a+2)(b+1)τ(r)=28, (a+1)(b+2)τ(r)=30 ⇒ τ(r)=1 ⇒ r=1).
-- Combinator: substitute n = 2^a * 3^b in m ∣ n; m coprime to 6 ⇒ coprime to 2^a;
-- so m ∣ 3^b; then m = gcd(m, 3^b) = 1.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs._strategy_s9835

namespace Problems.Minif2f.mathd_numbertheory_709

def coprime_to_six_div_one := @Problems.Minif2f.mathd_numbertheory_709.s9835

end Problems.Minif2f.mathd_numbertheory_709
