import Mathlib
import Problems.Minif2f.mathd_numbertheory_629.Defs
import Problems.Minif2f.mathd_numbertheory_629.proofs.L_lower_bound_18

namespace Problems.Minif2f.mathd_numbertheory_629

-- IsLeast S 18 splits into membership (18 ∈ S) and lower-bound universal.
-- Membership is a finite arithmetic check (lcm 12 18 = 36, 36^3 = 46656 = 216^2)
-- closed inline by `decide`. The lower-bound universal is delegated as a single
-- Backward sub-goal `lower_bound_18` over `t : ℕ` with the two hypotheses.
theorem s9386 : IsLeast { t : ℕ | 0 < t ∧ Nat.lcm 12 t ^ 3 = (12 * t) ^ 2 } 18  := by
  refine ⟨⟨by decide, by decide⟩, ?_⟩
  intro t ht
  exact lower_bound_18 t ht.1 ht.2

end Problems.Minif2f.mathd_numbertheory_629
