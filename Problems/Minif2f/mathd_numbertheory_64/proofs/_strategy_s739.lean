import Mathlib
import Problems.Minif2f.mathd_numbertheory_64.Defs

namespace Problems.Minif2f.mathd_numbertheory_64

-- Direct decomposition by `IsLeast`: membership (30*39 ≡ 42 [MOD 47]) is `decide`able,
-- and the lower bound follows by `interval_cases` on `x < 39`, each residue ruled out by `decide`.
theorem s739 : IsLeast { x : ℕ | 30 * x ≡ 42 [MOD 47] } 39  := by
  refine ⟨?_, ?_⟩
  · decide
  · intro x hx
    by_contra h
    rw [not_le] at h
    interval_cases x <;> revert hx <;> decide

end Problems.Minif2f.mathd_numbertheory_64
