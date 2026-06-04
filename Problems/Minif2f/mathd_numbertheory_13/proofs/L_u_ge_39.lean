-- Direct leaf: from `u ∈ S` extract `0 < u ∧ 14*u%100 = 46`; `omega` handles the
-- mod-50 residue argument (the smallest positive n with 14n%100=46 is n=39).
import Mathlib
import Problems.Minif2f.mathd_numbertheory_13.Defs
import Problems.Minif2f.mathd_numbertheory_13.proofs._strategy_s9476

namespace Problems.Minif2f.mathd_numbertheory_13

def u_ge_39 := @Problems.Minif2f.mathd_numbertheory_13.s9476

end Problems.Minif2f.mathd_numbertheory_13
