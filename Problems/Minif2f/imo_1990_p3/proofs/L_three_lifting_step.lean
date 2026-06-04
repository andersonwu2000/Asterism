-- Lift `3^(k+1) ∣ 2^(3^k*m)+1` to `3^(k+2) ∣ 2^(3^(k+1)*m)+1` via cube factorization.
-- Set a := 2^(3^k*m); reduce 2^(3^(k+1)*m) = a^3 (exp_cube_succ), then apply
-- the lifting lemma (lifting_three_pow): 3^(n+1) ∣ a+1 implies 3^(n+2) ∣ a^3+1.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9783

namespace Problems.Minif2f.imo_1990_p3

def three_lifting_step := @Problems.Minif2f.imo_1990_p3.s9783

end Problems.Minif2f.imo_1990_p3
