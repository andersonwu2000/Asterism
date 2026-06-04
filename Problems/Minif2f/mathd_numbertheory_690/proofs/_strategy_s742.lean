import Mathlib
import Problems.Minif2f.mathd_numbertheory_690.Defs

namespace Problems.Minif2f.mathd_numbertheory_690

-- Direct: membership of 314 is `decide`d per conjunct; lower bound unfolds
-- `Nat.ModEq` to `% =` form and discharges via `omega` (handles modular linear
-- arithmetic, deriving a + 1 ≡ 0 mod {3,5,7,9} hence a ≥ 314 from 0 < a).
theorem s742 : IsLeast { a : ℕ | 0 < a ∧ a ≡ 2 [MOD 3] ∧ a ≡ 4 [MOD 5] ∧ a ≡ 6 [MOD 7] ∧ a ≡ 8 [MOD 9] } 314  := by
  refine ⟨⟨?_, ?_, ?_, ?_, ?_⟩, ?_⟩
  · decide
  · decide
  · decide
  · decide
  · decide
  · intro a ⟨ha, h3, h5, h7, h9⟩
    unfold Nat.ModEq at h3 h5 h7 h9
    omega

end Problems.Minif2f.mathd_numbertheory_690
