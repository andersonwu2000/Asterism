-- Direct: by_contra gives t < 18; interval_cases dispatches t ∈ [1..17] and
-- `simp_all (config := { decide := true })` evaluates Nat.lcm 12 t and ^3 vs ^2
-- numerically for each case, refuting all 17 small candidates.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_629.Defs
import Problems.Minif2f.mathd_numbertheory_629.proofs._strategy_s9468

namespace Problems.Minif2f.mathd_numbertheory_629

def lower_bound_18 := @Problems.Minif2f.mathd_numbertheory_629.s9468

end Problems.Minif2f.mathd_numbertheory_629
