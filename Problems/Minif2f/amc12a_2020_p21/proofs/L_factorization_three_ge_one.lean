-- Lower bound 1 ≤ n.factorization 3 via prime-divides-iff-one-le-factorization recipe.
-- Sub-goals: (1) 3 ∣ n (the divisibility content) and (2) n ≠ 0 (factorization is
-- well-defined). Combined with `(Nat.Prime.pow_dvd_iff_le_factorization _ _).mp`
-- applied to the canonical `3 ∣ n` form (defeq to `3 ^ 1 ∣ n`).
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9798

namespace Problems.Minif2f.amc12a_2020_p21

def factorization_three_ge_one := @Problems.Minif2f.amc12a_2020_p21.s9798

end Problems.Minif2f.amc12a_2020_p21
