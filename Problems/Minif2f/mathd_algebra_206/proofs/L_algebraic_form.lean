-- Factor h₃ = b·(a+b+1) = 0 via the quadratic-in-b form; reduce to two leaves.
-- `b_ne_zero_from_first_eq` rules out the b=0 branch using h₁ and h₂
-- (b=0 ⇒ 6a²=0 ⇒ a=0 ⇒ 2a=b, contradicting h₁). `factor_quadratic_solve`
-- divides h₃ by the non-zero b to recover a+b=-1. Both sub-lemmas are
-- pure ℝ-arithmetic and have strictly smaller hypothesis sets.
import Mathlib
import Problems.Minif2f.mathd_algebra_206.Defs
import Problems.Minif2f.mathd_algebra_206.proofs._strategy_s9437

namespace Problems.Minif2f.mathd_algebra_206

def algebraic_form := @Problems.Minif2f.mathd_algebra_206.s9437

end Problems.Minif2f.mathd_algebra_206
