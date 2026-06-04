-- Direct leaf proof: introduce binders, split the conjunction with `refine ⟨?_, ?_⟩`,
-- and discharge each component by `linarith` using `h₀ : 2*3 = x - 9` (⟹ x = 15)
-- and `h₁ : 2*-5 = y + 1` (⟹ y = -11). No sub-goals — both arms are visible linear facts.
import Mathlib
import Problems.Minif2f.mathd_algebra_126.Defs
import Problems.Minif2f.mathd_algebra_126.proofs._strategy_s634

namespace Problems.Minif2f.mathd_algebra_126

def main := @Problems.Minif2f.mathd_algebra_126.s634

end Problems.Minif2f.mathd_algebra_126
