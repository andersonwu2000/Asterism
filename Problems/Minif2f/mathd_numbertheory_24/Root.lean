-- Direct decidable computation: the sum ∑ k ∈ Icc 1 9, 11^k reduces to a concrete
-- natural number, and `% 100 = 59` is checked by kernel reduction via `decide`.
-- No decomposition needed — this is a closed numerical statement with no free
-- variables, so leaf-bypass is the cheapest route.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_24.Defs
import Problems.Minif2f.mathd_numbertheory_24.proofs._strategy_s711

namespace Problems.Minif2f.mathd_numbertheory_24

def main := @Problems.Minif2f.mathd_numbertheory_24.s711

end Problems.Minif2f.mathd_numbertheory_24
