import Mathlib
import Problems.Minif2f.mathd_numbertheory_629.Defs

namespace Problems.Minif2f.mathd_numbertheory_629

-- Direct: by_contra gives t < 18; interval_cases dispatches t ∈ [1..17] and
-- `simp_all (config := { decide := true })` evaluates Nat.lcm 12 t and ^3 vs ^2
-- numerically for each case, refuting all 17 small candidates.
theorem s9468 : ∀ t : ℕ, 0 < t → Nat.lcm 12 t ^ 3 = (12 * t) ^ 2 → 18 ≤ t  := by
  intro t ht hlcm
  by_contra h
  have h' : t < 18 := Nat.lt_of_not_le h
  interval_cases t <;> simp_all (config := { decide := true })

end Problems.Minif2f.mathd_numbertheory_629
