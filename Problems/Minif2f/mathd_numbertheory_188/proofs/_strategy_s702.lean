import Mathlib
import Problems.Minif2f.mathd_numbertheory_188.Defs

namespace Problems.Minif2f.mathd_numbertheory_188

-- Direct kernel computation: `Nat.gcd 180 168` reduces to `12` by `decide`.
-- No sub-goals — the equality is a closed decidable proposition; leaf-bypass takes it.
theorem s702 : Nat.gcd 180 168 = 12  := by decide

end Problems.Minif2f.mathd_numbertheory_188
