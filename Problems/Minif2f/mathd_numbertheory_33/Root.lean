-- Bounded brute force: `interval_cases n` (using h₀ : n < 398) splits into the
-- 398 finite candidates for n; `omega` discharges each using h₁ : n * 7 % 398 = 1
-- (only n = 57 satisfies 57 * 7 = 399 = 398 + 1, the rest contradict h₁).
-- Leaf-level: no sub-goals — modular arithmetic on a small finite range.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_33.Defs
import Problems.Minif2f.mathd_numbertheory_33.proofs._strategy_s721

namespace Problems.Minif2f.mathd_numbertheory_33

def main := @Problems.Minif2f.mathd_numbertheory_33.s721

end Problems.Minif2f.mathd_numbertheory_33
