-- Decompose 89 ≤ v: any positive n with 14n%100=46 and n<89 must equal 39.
-- Since u = least element of S equals 39 (39 ∈ S and any element <89 equals 39),
-- and v ∈ S\{u} forces v ≠ u, suppose v<89 → v=39=u → contradiction.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_13.Defs
import Problems.Minif2f.mathd_numbertheory_13.proofs._strategy_s9343

namespace Problems.Minif2f.mathd_numbertheory_13

def v_ge_89 := @Problems.Minif2f.mathd_numbertheory_13.s9343

end Problems.Minif2f.mathd_numbertheory_13
